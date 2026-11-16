// Test-only clipboard guard. Original bytes stay in this process's memory, never stdout/disk.
import AppKit
struct Item: Equatable { let types:[NSPasteboard.PasteboardType]; let data:[Data] }
struct Snapshot: Equatable {let items:[Item];let aliases:[NSPasteboard.PasteboardType:Data]}
struct GuardFailure: Error {}
let selfTest=CommandLine.arguments.contains("--self-test")
let board=selfTest ? NSPasteboard.withUniqueName() : NSPasteboard.general
func snapshot() throws -> Snapshot {
    let start=board.changeCount
    let items=board.pasteboardItems ?? []
    var result=[Item]()
    for item in items {
        var bytes=[Data]()
        for type in item.types {
            guard !type.rawValue.lowercased().contains("promise"),let data=item.data(forType:type) else {throw GuardFailure()}
            bytes.append(data)
        }
        result.append(Item(types:item.types,data:bytes))
    }
    let known=Set(result.flatMap{$0.types})
    var aliases=[NSPasteboard.PasteboardType:Data]()
    for type in Set(board.types ?? []).subtracting(known) {
        // AppKit synthesizes this legacy alias from the item's UTF-8 string.
        guard type.rawValue=="NSStringPboardType",known.contains(.string),let data=board.data(forType:type) else {throw GuardFailure()}
        aliases[type]=data
    }
    guard start==board.changeCount else {throw GuardFailure()}
    return Snapshot(items:result,aliases:aliases)
}
func restore(_ original:Snapshot, _ copied:Snapshot, _ count:Int) throws -> Bool {
    guard board.changeCount==count,try snapshot()==copied else {throw GuardFailure()}
    // Build objects before touching the board, then check ownership again.
    let objects=original.items.map { item -> NSPasteboardItem in
        let object=NSPasteboardItem()
        for (type,data) in zip(item.types,item.data) {object.setData(data,forType:type)}
        return object
    }
    guard board.changeCount==count else {throw GuardFailure()}
    let cleared=board.clearContents()
    guard board.changeCount==cleared else {throw GuardFailure()}
    guard objects.isEmpty || board.writeObjects(objects) else {throw GuardFailure()}
    return try snapshot()==original
}
func emit(_ value:[String:Any]) {
    print(String(data:try! JSONSerialization.data(withJSONObject:value,options:.sortedKeys),encoding:.utf8)!)
    fflush(stdout)
}
if selfTest {
    defer {board.releaseGlobally()}
    let first=NSPasteboardItem();first.setString("synthetic",forType:.string);first.setData(Data([0,255,4]),forType:NSPasteboard.PasteboardType("test.binary"))
    let second=NSPasteboardItem();second.setData(Data([8,0,9]),forType:NSPasteboard.PasteboardType("test.second"))
    board.clearContents();assert(board.writeObjects([first,second]))
    let original=try! snapshot()
    board.clearContents();board.setString("test copy",forType:.string)
    let copied=try! snapshot();let owned=board.changeCount
    assert(try! restore(original,copied,owned));assert(try! snapshot()==original)
    board.clearContents();board.setString("copied again",forType:.string)
    let stale=try! snapshot();let staleCount=board.changeCount
    board.clearContents();board.setString("new user copy",forType:.string)
    var rejected=false
    do {_ = try restore(original,stale,staleCount)} catch {rejected=true}
    assert(rejected);assert(board.string(forType:.string)=="new user copy")
    let promise=NSPasteboardItem();promise.setData(Data(),forType:NSPasteboard.PasteboardType("test.promise"));board.clearContents();board.writeObjects([promise])
    rejected=false;do {_ = try snapshot()}catch{rejected=true};assert(rejected)
    emit(["ok":true,"multiItemMultiTypeBinaryRoundTrip":true,"newerCopyNotOverwritten":true,"promiseRejected":true,"generalClipboardTouched":false]);exit(0)
}
let initialCount=board.changeCount
var original=Snapshot(items:[],aliases:[:])
do { original=try snapshot();guard initialCount==board.changeCount else {throw GuardFailure()};emit(["ok":true,"snapshotComplete":true]) }
catch {emit(["ok":false,"reason":"Unreadable, promised, non-item type or concurrent clipboard change; no writes"]);exit(1)}
var ownedCount:Int?;var copied:Snapshot?;var armed=false
while let line=readLine() {
    do {
        let request=try JSONSerialization.jsonObject(with:Data(line.utf8)) as! [String:String]
        switch request["command"] {
        case "arm":
            guard !armed,board.changeCount==initialCount,try snapshot()==original else {throw GuardFailure()}
            armed=true;emit(["ok":true])
        case "copied":
            // Accept exactly one new owner, matching only the known public test text.
            guard armed,ownedCount==nil,board.changeCount==initialCount+1 else {throw GuardFailure()}
            let current=try snapshot()
            guard board.string(forType:.string)==request["text"],board.changeCount==initialCount+1 else {throw GuardFailure()}
            copied=current;ownedCount=board.changeCount;emit(["ok":true,"testTextMatches":true])
        case "check":
            guard let count=ownedCount,board.changeCount==count,try snapshot()==copied else {throw GuardFailure()}
            emit(["ok":true])
        case "restore":
            if board.changeCount==initialCount,try snapshot()==original {emit(["ok":true,"allItemsTypesBytesEqual":true,"restorationNeeded":false]);exit(0)}
            guard let count=ownedCount,board.changeCount==count,try snapshot()==copied else {throw GuardFailure()}
            let equal=try restore(original,copied!,count)
            emit(["ok":equal,"allItemsTypesBytesEqual":equal,"restorationNeeded":true]);exit(equal ? 0:1)
        default:throw GuardFailure()
        }
    } catch {emit(["ok":false,"reason":"Clipboard ownership/data changed or guard failed; no further writes attempted"])}
}
// EOF never silently restores a potentially newer user's clipboard.
