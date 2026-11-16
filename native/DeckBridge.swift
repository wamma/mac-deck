import Foundation
import AppKit
import ApplicationServices
import CoreAudio
import IOKit.graphics

struct BridgeError: Error { let message: String }
func fail(_ message: String) throws -> Never { throw BridgeError(message: message) }
func attr(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success ? value : nil
}
func focusedWindow(_ pid: pid_t) -> AXUIElement? {
    guard let value = attr(AXUIElementCreateApplication(pid), kAXFocusedWindowAttribute), CFGetTypeID(value) == AXUIElementGetTypeID() else { return nil }
    return (value as! AXUIElement)
}
func windowIdentity(_ pid: pid_t, _ window: AXUIElement) -> [String: Any] {
    var position=CGPoint.zero, size=CGSize.zero
    var number: UInt32=0
    if let p=attr(window,kAXPositionAttribute), let z=attr(window,kAXSizeAttribute),
       CFGetTypeID(p)==AXValueGetTypeID(), CFGetTypeID(z)==AXValueGetTypeID(),
       AXValueGetValue(p as! AXValue,.cgPoint,&position), AXValueGetValue(z as! AXValue,.cgSize,&size),
       let windows=CGWindowListCopyWindowInfo(.optionAll,kCGNullWindowID) as? [[String:Any]] {
        let matches=windows.filter { info in
            guard info[kCGWindowOwnerPID as String] as? Int == Int(pid),
                  let raw=info[kCGWindowBounds as String] as? NSDictionary,
                  let bounds=CGRect(dictionaryRepresentation:raw) else { return false }
            return abs(bounds.origin.x-position.x)<1 && abs(bounds.origin.y-position.y)<1 && abs(bounds.width-size.width)<1 && abs(bounds.height-size.height)<1
        }
        if matches.count==1 { number=matches[0][kCGWindowNumber as String] as? UInt32 ?? 0 }
    }
    return ["pid":Int(pid),"windowId":number,"documentURL":attr(window,kAXDocumentAttribute) as? String ?? ""]
}
func matchesExpected(_ actual: [String:Any], _ expected: [String:Any]) -> Bool {
    guard let pid=expected["pid"] as? Int, pid>0, let window=expected["windowId"] as? UInt32,window>0,
          let document=expected["documentURL"] as? String, let expectedURL=URL(string:document),expectedURL.isFileURL,
          let actualDocument=actual["documentURL"] as? String,let actualURL=URL(string:actualDocument),actualURL.isFileURL else { return false }
    return actual["pid"] as? Int==pid && actual["windowId"] as? UInt32==window && actualURL.standardizedFileURL.resolvingSymlinksInPath()==expectedURL.standardizedFileURL.resolvingSymlinksInPath()
}
func terminalFailureMessage(errorNumber: Int? = nil, wrongApp: Bool = false, missingWindow: Bool = false) -> String {
    let retry="확인 후 웹의 ‘등록 창 확인’을 직접 눌러 다시 시도하세요. 자동으로 재시도하지 않습니다."
    let settings="시스템 설정 → 개인정보 보호 및 보안 → 자동화에서 서버를 실행한 앱의 Terminal 제어 허용을 확인하세요."
    if wrongApp { return "등록 세션이 있는 macOS Terminal 창과 탭을 맥에서 전면에 두세요. " + retry }
    if missingWindow || errorNumber == -1728 || errorNumber == -1719 { return "Terminal 활성 창 또는 선택 탭을 찾지 못했습니다. 등록 세션의 창과 탭을 전면에 두세요. " + retry }
    switch errorNumber {
    case -1743: return "Terminal 자동화 제어가 허용되지 않았습니다 (-1743). " + settings + " " + retry
    case -1712: return "Terminal 자동화 응답 시간이 초과되었습니다 (-1712). 맥의 자동화 요청 창 또는 Terminal 응답을 확인하세요. 권한 거절로 확정된 상태는 아닙니다. " + settings + " " + retry
    default:
        let code=errorNumber.map { " (오류 \($0))" } ?? ""
        return "Terminal 탭 TTY를 읽지 못했습니다" + code + ". 등록 세션의 활성 창과 탭을 확인하세요. " + retry
    }
}
func terminalTTY() throws -> String {
    guard NSWorkspace.shared.frontmostApplication?.bundleIdentifier=="com.apple.Terminal" else { try fail(terminalFailureMessage(wrongApp:true)) }
    var error: NSDictionary?
    let script=NSAppleScript(source:"tell application \"Terminal\" to get tty of selected tab of front window")
    let result=script?.executeAndReturnError(&error)
    guard error==nil,let tty=result?.stringValue,!tty.isEmpty else {
        try fail(terminalFailureMessage(errorNumber:(error?[NSAppleScript.errorNumber] as? NSNumber)?.intValue))
    }
    return tty
}
func verifySessionProcess(_ expected: [String:Any]) throws {
    guard let pid=expected["pid"] as? Int,pid>0,let fingerprint=expected["fingerprint"] as? String,
          let tty=expected["tty"] as? String,tty.hasPrefix("/dev/ttys"),fingerprint.count<1000 else { try fail("등록 세션 프로세스 식별자가 없습니다.") }
    let process=Process(),output=Pipe();process.executableURL=URL(fileURLWithPath:"/bin/ps")
    process.arguments=["-p",String(pid),"-o","lstart=,tty=,comm="];process.standardOutput=output;process.standardError=FileHandle.nullDevice
    try process.run();let data=output.fileHandleForReading.readDataToEndOfFile();process.waitUntilExit()
    guard process.terminationStatus==0,String(data:data,encoding:.utf8)?.trimmingCharacters(in:.whitespacesAndNewlines)==fingerprint else { try fail("세션 프로세스가 종료되었거나 재시작되어 동작을 차단했습니다.") }
    guard try terminalTTY()==tty else { try fail("등록 세션과 현재 Terminal 탭의 TTY가 달라 동작을 차단했습니다.") }
}
func matchesSessionProof(_ expected: [String:Any],_ proof: [String:Any],_ now: Double) -> Bool {
    guard let session=expected["sessionId"] as? String,!session.isEmpty,proof["session"] as? String==session,
          let updated=proof["updatedAt"] as? Double,updated<=now+1,now-updated<30 else { return false }
    if expected["requireQuestion"] as? Bool == true {
        guard proof["state"] as? String=="input-required",let question=expected["question"] as? String,!question.isEmpty,proof["question"] as? String==question else { return false }
    }
    return true
}
func verifyExpected(_ target: (pid_t,AXUIElement), _ expected: [String:Any]?) throws {
    if let expected=expected {
        if let process=expected["terminalProcess"] as? [String:Any] {
            let actual=windowIdentity(target.0,target.1)
            guard actual["pid"] as? Int==expected["pid"] as? Int,let number=expected["windowId"] as? UInt32,number>0,actual["windowId"] as? UInt32==number else { try fail("등록 Terminal 창이 바뀌어 동작을 차단했습니다.") }
            try verifySessionProcess(process)
            guard let path=expected["sessionProofPath"] as? String,
                  let data=try? Data(contentsOf:URL(fileURLWithPath:path)),data.count<10000,
                  let proof=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any],
                  matchesSessionProof(expected,proof,Date().timeIntervalSince1970) else { try fail("세션·질문 식별 증거가 바뀌었거나 만료되어 동작을 차단했습니다.") }
        } else if !matchesExpected(windowIdentity(target.0,target.1),expected) {
            try fail("고정한 시험 문서의 PID·창 ID·문서 URL이 일치하지 않아 입력을 차단했습니다.")
        }
    }
}
func inspect() -> [String: Any] {
    let app = NSWorkspace.shared.frontmostApplication
    let window = app.flatMap { focusedWindow($0.processIdentifier) }
    var result: [String:Any] = ["accessibilityTrusted": AXIsProcessTrusted(), "screenCaptureGranted": CGPreflightScreenCaptureAccess(),
            "pid": app?.processIdentifier ?? 0, "bundleId": app?.bundleIdentifier ?? "", "name": app?.localizedName ?? "",
            "focusedWindowReadable": window != nil, "windowTitle": window.flatMap { attr($0,kAXTitleAttribute) as? String } ?? ""]
    if let app=app,let window=window { result.merge(windowIdentity(app.processIdentifier,window)){_,new in new} }
    return result
}
func inputTarget(_ expected: [String:Any]? = nil) throws -> (pid_t, AXUIElement) {
    guard AXIsProcessTrusted() else { try fail("손쉬운 사용 권한이 없습니다. 서버를 실행한 앱과 deck-bridge 권한을 확인하세요.") }
    guard let app = NSWorkspace.shared.frontmostApplication,
          !["com.apple.loginwindow","com.apple.ScreenSaver.Engine"].contains(app.bundleIdentifier ?? ""),
          app.activationPolicy == .regular,
          let window = focusedWindow(app.processIdentifier) else {
        if NSWorkspace.shared.frontmostApplication?.bundleIdentifier=="com.apple.Terminal" { try fail(terminalFailureMessage(missingWindow:true)) }
        try fail("일반 앱의 활성 창을 확인하지 못했습니다. 화면 잠금 또는 AX 접근을 확인하세요. 키를 보내지 않았습니다.")
    }
    let target=(app.processIdentifier,window)
    try verifyExpected(target,expected)
    return target
}
func verify(_ target: (pid_t, AXUIElement), _ expected: [String:Any]? = nil) throws {
    guard NSWorkspace.shared.frontmostApplication?.processIdentifier == target.0,
          let window = focusedWindow(target.0), CFEqual(window,target.1) else {
        try fail("대상 앱 또는 창이 바뀌어 전송을 중단했습니다. 일부 입력되었을 수 있으므로 자동 재시도하지 않습니다.")
    }
    try verifyExpected(target,expected)
}
func key(_ code: CGKeyCode, _ flags: CGEventFlags, _ target: (pid_t, AXUIElement), text: String? = nil, expected: [String:Any]? = nil) throws {
    try verify(target,expected)
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false) else { try fail("키 이벤트를 생성하지 못했습니다.") }
    down.flags=flags;up.flags=flags
    if let text = text {
        let units=Array(text.utf16)
        units.withUnsafeBufferPointer { buffer in
            down.keyboardSetUnicodeString(stringLength: units.count, unicodeString: buffer.baseAddress!)
            up.keyboardSetUnicodeString(stringLength: units.count, unicodeString: buffer.baseAddress!)
        }
    }
    down.postToPid(target.0);up.postToPid(target.0)
    Thread.sleep(forTimeInterval: 0.012)
}
func volumeDevice() throws -> AudioDeviceID {
    var address=AudioObjectPropertyAddress(mSelector:kAudioHardwarePropertyDefaultOutputDevice,mScope:kAudioObjectPropertyScopeGlobal,mElement:kAudioObjectPropertyElementMain)
    var device=AudioDeviceID(0),size=UInt32(MemoryLayout<AudioDeviceID>.size)
    guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject),&address,0,nil,&size,&device)==noErr,device != 0 else { try fail("기본 오디오 출력 장치를 찾지 못했습니다.") }
    return device
}
func volumeAddress(_ selector: AudioObjectPropertySelector, _ channel: UInt32=0) -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector:selector,mScope:kAudioDevicePropertyScopeOutput,mElement:channel)
}
func writable(_ device: AudioDeviceID, _ address: inout AudioObjectPropertyAddress) -> Bool {
    var value: DarwinBoolean=false
    return AudioObjectHasProperty(device,&address) && AudioObjectIsPropertySettable(device,&address,&value)==noErr && value.boolValue
}
func volumeChannels(_ device: AudioDeviceID) -> [UInt32] {
    var main=volumeAddress(kAudioDevicePropertyVolumeScalar)
    if writable(device,&main) { return [0] }
    return [UInt32(1),UInt32(2)].filter { channel in var a=volumeAddress(kAudioDevicePropertyVolumeScalar,channel);return writable(device,&a) }
}
func volumeStatus() -> [String:Any] {
    do {
        let device=try volumeDevice(),channels=volumeChannels(device)
        var values=[Float32]()
        for channel in channels {
            var a=volumeAddress(kAudioDevicePropertyVolumeScalar,channel),value=Float32(0),size=UInt32(MemoryLayout<Float32>.size)
            if AudioObjectGetPropertyData(device,&a,0,nil,&size,&value)==noErr && value.isFinite && (0...1).contains(value) { values.append(value) }
        }
        var a=volumeAddress(kAudioDevicePropertyMute),mute=UInt32(0),size=UInt32(MemoryLayout<UInt32>.size)
        let muteSupported=writable(device,&a) && AudioObjectGetPropertyData(device,&a,0,nil,&size,&mute)==noErr
        let supported = !channels.isEmpty && values.count==channels.count
        return ["supported":supported,"deviceId":device,"value":supported ? Int((values.reduce(0,+)/Float32(values.count)*100).rounded()) : NSNull(),"muted":muteSupported ? mute != 0 : NSNull(),"muteSupported":muteSupported,"message":supported ? "맥 기본 출력 장치" : "이 출력 장치는 소프트웨어 음량 조절을 지원하지 않습니다."]
    } catch { return ["supported":false,"muteSupported":false,"value":NSNull(),"message":"기본 출력 장치를 읽지 못했습니다."] }
}
func brightnessTarget() -> (CGDirectDisplayID,io_service_t,Float)? {
    var displays=[CGDirectDisplayID](repeating:0,count:16),count=UInt32(0)
    guard CGGetOnlineDisplayList(16,&displays,&count) == .success else { return nil }
    let builtins=displays.prefix(Int(count)).filter { CGDisplayIsBuiltin($0) != 0 }
    guard builtins.count==1,let display=builtins.first else { return nil }
    var iterator=io_iterator_t(0)
    guard IOServiceGetMatchingServices(kIOMainPortDefault,IOServiceMatching("IODisplayConnect"),&iterator)==KERN_SUCCESS else { return nil }
    defer { IOObjectRelease(iterator) }
    var matches=[(CGDirectDisplayID,io_service_t,Float)]()
    var service=IOIteratorNext(iterator)
    while service != 0 {
        guard let raw=IODisplayCreateInfoDictionary(service,0) else { IOObjectRelease(service);service=IOIteratorNext(iterator);continue }
        let info=raw.takeRetainedValue() as NSDictionary
        var value=Float(0)
        if (info["DisplayVendorID"] as? UInt32)==CGDisplayVendorNumber(display),
           (info["DisplayProductID"] as? UInt32)==CGDisplayModelNumber(display),
           (info["DisplaySerialNumber"] as? UInt32 ?? 0)==CGDisplaySerialNumber(display),
           IODisplayGetFloatParameter(service,0,kIODisplayBrightnessKey as CFString,&value)==kIOReturnSuccess, value.isFinite, (0...1).contains(value) {
            matches.append((display,service,value))
        } else { IOObjectRelease(service) }
        service=IOIteratorNext(iterator)
    }
    if matches.count==1 { return matches[0] }
    for match in matches { IOObjectRelease(match.1) }
    return nil
}
func brightnessStatus() -> [String:Any] {
    guard let target=brightnessTarget() else { return ["supported":false,"value":NSNull(),"message":"밝기 API를 지원하는 맥 내장 화면이 없습니다. 외부 화면은 모니터에서 조절하세요."] }
    defer { IOObjectRelease(target.1) }
    return ["supported":true,"displayId":target.0,"value":Int((target.2*100).rounded()),"message":"맥 내장 화면"]
}
func systemStatus() -> [String:Any] { ["volume":volumeStatus(),"brightness":brightnessStatus()] }
func systemControl(_ request: [String:Any]) throws -> [String:Any] {
    guard let operation=request["operation"] as? String else { try fail("시스템 동작이 없습니다.") }
    let allowed=["volume_up","volume_down","volume_set","mute_toggle","brightness_up","brightness_down","brightness_set"]
    guard allowed.contains(operation) else { try fail("지원하지 않는 시스템 동작입니다.") }
    if operation.hasSuffix("_set") {
        guard let value=request["value"] as? Int,(0...100).contains(value),CFGetTypeID(request["value"]! as AnyObject) != CFBooleanGetTypeID() else { try fail("값은 0~100 정수여야 합니다.") }
    }
    if operation.hasPrefix("brightness") {
        guard let target=brightnessTarget() else { try fail("이 맥 화면의 밝기 조절은 지원되지 않습니다.") }
        defer { IOObjectRelease(target.1) }
        if let expected=request["expectedIdentity"] { guard let id=expected as? UInt32,id==target.0 else { try fail("시험 대상 화면이 바뀌어 변경을 차단했습니다.") } }
        let value=operation=="brightness_set" ? Float(request["value"] as! Int)/100 : min(1,max(0,target.2+(operation=="brightness_up" ? 0.1 : -0.1)))
        guard IODisplaySetFloatParameter(target.1,0,kIODisplayBrightnessKey as CFString,value)==kIOReturnSuccess else { try fail("실제 화면 밝기를 변경하지 못했습니다.") }
        let after=brightnessStatus()
        let verified=after["displayId"] as? UInt32==target.0 && abs((after["value"] as? Int ?? -999)-Int((value*100).rounded()))<=2
        return ["status":verified ? "verified":"accepted","message":verified ? "맥 내장 화면 밝기 변경을 재조회로 확인했습니다.":"밝기 명령은 접수됐지만 실제 값은 확인하지 못했습니다.","system":systemStatus()]
    }
    let device=try volumeDevice(),before=volumeStatus()
    if let expected=request["expectedIdentity"] { guard let id=expected as? UInt32,id==device else { try fail("시험 대상 오디오 장치가 바뀌어 변경을 차단했습니다.") } }
    guard before["deviceId"] as? UInt32==device else { try fail("오디오 출력 장치가 바뀌었습니다. 다시 확인하세요.") }
    var verified=false
    if operation=="mute_toggle" {
        var address=volumeAddress(kAudioDevicePropertyMute)
        guard before["muteSupported"] as? Bool==true,let muted=before["muted"] as? Bool else { try fail("이 출력 장치는 음소거 조절을 지원하지 않습니다.") }
        var value=UInt32(muted ? 0:1)
        guard AudioObjectSetPropertyData(device,&address,0,nil,UInt32(MemoryLayout<UInt32>.size),&value)==noErr else { try fail("음소거 변경을 처리하지 못했습니다.") }
        Thread.sleep(forTimeInterval:0.05)
        let after=volumeStatus();verified=after["deviceId"] as? UInt32==device && after["muted"] as? Bool == !muted
    } else {
        guard before["supported"] as? Bool==true,let current=before["value"] as? Int else { try fail("이 출력 장치는 음량 조절을 지원하지 않습니다.") }
        let level=operation=="volume_set" ? request["value"] as! Int : min(100,max(0,current+(operation=="volume_up" ? 10 : -10)))
        for channel in volumeChannels(device) {
            var address=volumeAddress(kAudioDevicePropertyVolumeScalar,channel),value=Float32(level)/100
            guard AudioObjectSetPropertyData(device,&address,0,nil,UInt32(MemoryLayout<Float32>.size),&value)==noErr else { try fail("음량 변경 중 오류가 발생했습니다. 일부 채널만 변경되었을 수 있습니다.") }
        }
        Thread.sleep(forTimeInterval:0.05)
        let after=volumeStatus();verified=after["deviceId"] as? UInt32==device && abs((after["value"] as? Int ?? -999)-level)<=1
    }
    return ["status":verified ? "verified":"accepted","message":verified ? "맥의 실제 음량 설정을 재조회로 확인했습니다.":"명령은 접수됐지만 실제 음량 설정은 확인하지 못했습니다.","system":systemStatus()]
}
func handle(_ request: [String: Any]) throws -> [String: Any] {
    switch request["action"] as? String {
    case "inspect": return inspect()
    case "terminal-target":
        guard let process=request["process"] as? [String:Any] else { try fail("세션 프로세스가 없습니다.") }
        guard NSWorkspace.shared.frontmostApplication?.bundleIdentifier=="com.apple.Terminal" else { try fail(terminalFailureMessage(wrongApp:true)) }
        let target=try inputTarget()
        try verifySessionProcess(process)
        var mapping=windowIdentity(target.0,target.1);mapping["terminalProcess"]=process
        guard let number=mapping["windowId"] as? UInt32,number>0 else { try fail("Terminal 창 ID를 확인하지 못했습니다.") }
        return ["mapping":mapping]
    case "check-target":
        guard let expected=request["expected"] as? [String:Any] else { try fail("등록 창 식별자가 필요합니다.") }
        guard CGPreflightScreenCaptureAccess() else { try fail("화면 기록 권한이 없습니다.") }
        let target=try inputTarget(expected)
        try verify(target,expected)
        return ["verified":true]
    case "system-status": return systemStatus()
    case "system": return try systemControl(request)
    case "activate":
        guard let path=request["path"] as? String else { try fail("앱 경로가 없습니다.") }
        let url=URL(fileURLWithPath:path)
        let config=NSWorkspace.OpenConfiguration();config.activates=true
        var launched: NSRunningApplication?;var finished=false
        NSWorkspace.shared.openApplication(at:url,configuration:config) { app,error in launched=app;finished=true }
        let deadline=Date().addingTimeInterval(4)
        while !finished && Date()<deadline { RunLoop.current.run(until:Date().addingTimeInterval(0.05)) }
        guard let app=launched else { try fail("앱 실행을 확인하지 못했습니다.") }
        app.activate(options: [])
        while NSWorkspace.shared.frontmostApplication?.processIdentifier != app.processIdentifier && Date()<deadline {
            RunLoop.current.run(until:Date().addingTimeInterval(0.05))
        }
        let verified=NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier
        return ["status":verified ? "verified" : "accepted", "pid":app.processIdentifier,
                "message":verified ? "앱이 맨 앞으로 활성화된 것을 확인했습니다." : "앱 실행은 접수됐지만 맨 앞 활성화는 확인하지 못했습니다.", "target":inspect()]
    case "shortcut", "text":
        if request["expected"] != nil && !(request["expected"] is [String:Any]) { try fail("잘못된 고정 대상입니다.") }
        let expected=request["expected"] as? [String:Any]
        let target=try inputTarget(expected)
        let targetName=NSWorkspace.shared.frontmostApplication?.localizedName ?? "확인한 앱"
        if request["action"] as? String == "shortcut" {
            guard let code=request["code"] as? UInt16, let modifiers=request["modifiers"] as? [String] else { try fail("잘못된 키 요청입니다.") }
            var flags: CGEventFlags=[]
            for modifier in modifiers {
                switch modifier { case "command": flags.insert(.maskCommand); case "option":flags.insert(.maskAlternate);case "control":flags.insert(.maskControl);case "shift":flags.insert(.maskShift);default:try fail("잘못된 보조 키입니다.") }
            }
            try key(code,flags,target,expected:expected)
        } else {
            guard let text=request["text"] as? String, !text.isEmpty, text.unicodeScalars.count<=1000, let enter=request["enter"] as? Bool else { try fail("잘못된 텍스트 요청입니다.") }
            // Data arrives as JSON, never source code. No clipboard mutation.
            var chunk=""
            let deadline=Date().addingTimeInterval(6)
            for scalar in text.unicodeScalars {
                if chunk.utf16.count + String(scalar).utf16.count > 20 && !chunk.isEmpty {
                    guard Date()<deadline else { try fail("텍스트 전송 시간이 초과되어 중단했습니다. 일부 입력되었을 수 있습니다. 자동 재시도하지 않습니다.") }
                    try key(0,[],target,text:chunk,expected:expected);chunk=""
                }
                chunk.append(String(scalar))
            }
            if !chunk.isEmpty { try key(0,[],target,text:chunk,expected:expected) }
            if enter { try key(36,[],target,expected:expected) }
        }
        return ["status":"sent","pid":target.0,"message":"\(targetName) (PID \(target.0)) 활성 창으로 키를 전송했습니다. 앱의 입력 결과는 자동 확인되지 않았습니다."]
    default: try fail("지원하지 않는 네이티브 작업입니다.")
    }
}
do {
    let data=FileHandle.standardInput.readDataToEndOfFile()
    guard let request=try JSONSerialization.jsonObject(with:data) as? [String: Any] else { try fail("JSON 객체가 필요합니다.") }
    let result=try handle(request)
    FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject:result,options:[.sortedKeys]))
} catch {
    let message=(error as? BridgeError)?.message ?? "네이티브 요청을 처리하지 못했습니다."
    FileHandle.standardOutput.write(try! JSONSerialization.data(withJSONObject:["error":message]))
    exit(1)
}
