// Actual UI app activation + fixed dedicated-document verifier; explicit manual validation.
import assert from 'node:assert/strict';import {execFileSync} from 'node:child_process';import {readFile,writeFile,mkdir,mkdtemp} from 'node:fs/promises';import {tmpdir} from 'node:os';import {join} from 'node:path';import {createHash} from 'node:crypto';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const code=process.env.DECK_CODE,folder=process.argv[2];if(!code||!folder)throw Error('DECK_CODE and screenshot folder required');
const initial=JSON.parse(await readFile(process.env.DECK_NATIVE_FIXTURE,'utf8'));
assert.ok(initial.accessibilityTrusted&&initial.focusedWindowReadable&&!['com.apple.loginwindow','com.apple.ScreenSaver.Engine'].includes(initial.bundleId));
const root=(process.env.DECK_TEST_URL||'http://127.0.0.1:8765'),browser=await chromium.launch({...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),headless:true}),context=await browser.newContext({viewport:{width:1366,height:1024}}),page=await context.newPage();
const directory=await mkdtemp(join(tmpdir(),'mac-deck-native-')),document=join(directory,'Deck-Safe-Verification.txt');await writeFile(document,'');await mkdir(folder,{recursive:true});
const evidence={initial,document,textEditAlreadyRunning:!!execFileSync('/bin/ps',['-axo','comm='],{encoding:'utf8'}).split('\n').find(s=>s.endsWith('/TextEdit')),newAppLaunchVerified:false,screenshots:[]};let before,expected;
async function get(path){const r=await context.request.get(root+path);assert.equal(r.status(),200);return r.json();}
async function post(path,data){const r=await context.request.post(root+path,{data,headers:{Origin:root}});assert.equal(r.status(),200);return r.json();}
function python(source,args=[]){return JSON.parse(execFileSync('python3',['-c',source,...args],{encoding:'utf8'}));}
function clipboardCount(){return Number(execFileSync('/usr/bin/osascript',['-l','JavaScript','-e','ObjC.import("AppKit"); $.NSPasteboard.generalPasteboard.changeCount'],{encoding:'utf8'}).trim());}
let failed;
try{
 await post('/api/pair',{code});before=await get('/api/state');await page.goto(root);await page.locator('#dashboard').waitFor({state:'visible'});await page.locator('[data-mode=apps]').click();
 execFileSync('/usr/bin/open',['-g','-a','TextEdit',document]);execFileSync('/usr/bin/open',['-b',initial.bundleId]);
 await page.locator('#edit').click();await page.locator('.add-tile').click();await page.locator('#button-label').fill('전용 안전문서 검증 TextEdit');const options=await page.locator('#button-app option').evaluateAll(els=>els.map(e=>({id:e.value,name:e.textContent})));const app=options.find(a=>a.name==='TextEdit');assert.ok(app);await page.locator('#button-app').selectOption(app.id);await page.locator('#button-form button[type=submit]').click();await page.locator('#edit-dialog').waitFor({state:'hidden'});await page.locator('#edit').click();
 const response=page.waitForResponse(r=>r.url().endsWith('/api/run')&&r.request().method()==='POST');await page.locator('.run-button').filter({hasText:'전용 안전문서 검증 TextEdit'}).click();evidence.activation=await(await response).json();
 const d=await get('/api/diagnostics');evidence.foregroundAfter={pid:d.pid,bundleId:d.bundleId,windowId:d.windowId,documentURL:d.documentURL,focusedWindowReadable:d.focusedWindowReadable};
 assert.equal(evidence.activation.status,'verified');assert.equal(d.bundleId,'com.apple.TextEdit');assert.ok(d.focusedWindowReadable&&d.windowId);
 const canonical=python('import pathlib,json,sys;print(json.dumps(pathlib.Path(sys.argv[1]).resolve().as_uri()))',[document]);assert.equal(d.documentURL,canonical);
 expected={pid:d.pid,windowId:d.windowId,documentURL:canonical};const prepared=join(directory,'prepared.json');await writeFile(prepared,JSON.stringify({testDocument:document,expected}));
 evidence.clipboardChangeCountBefore=clipboardCount();
 evidence.safeVerifier=JSON.parse(execFileSync('python3',['scripts/verify_native.py','--prepared',prepared],{encoding:'utf8'}));
 evidence.clipboardChangeCountAfter=clipboardCount();evidence.clipboardChangeCountUnchanged=evidence.clipboardChangeCountBefore===evidence.clipboardChangeCountAfter;
 // Window-specific capture only; native helper rechecks the pinned document before/after.
 const capture=python('import json,sys;from deck.macos import Mac;m=Mac(".deck-data");print(json.dumps(m.capture_registered(json.loads(sys.argv[1]))))',[JSON.stringify(expected)]);
 const png=join(folder,'macOS_TextEdit_dedicated-safe-document_'+Date.now()+'.png');const bytes=Buffer.from(capture.image.split(',')[1],'base64');await writeFile(png,bytes);evidence.screenshots.push({path:png,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20),sha256:createHash('sha256').update(bytes).digest('hex')});
 assert.equal(evidence.safeVerifier.textInput,'PASS');assert.equal(evidence.safeVerifier.shortcut,'PASS');assert.equal(evidence.safeVerifier.clipboardTextUnchanged,true);assert.equal(evidence.clipboardChangeCountUnchanged,true);evidence.result='PASS';
}catch(error){failed=error;evidence.result='FAIL';evidence.error=error.message;}
finally{
 if(expected&&evidence.safeVerifier?.saveDispatch){try{evidence.closeDocument=python('import json,sys;from deck.macos import Mac;print(json.dumps(Mac(".deck-data").shortcut("w",["command"],expected=json.loads(sys.argv[1]))))',[JSON.stringify(expected)]);}catch{evidence.closeDocument='not confirmed; no fallback input';}}
 if(before){await post('/api/buttons',{buttons:before.buttons});const after=await get('/api/state');assert.deepEqual(after.buttons,before.buttons);assert.deepEqual(after.preferences,before.preferences);evidence.buttonsPreferencesRestored=true;}
 execFileSync('/usr/bin/open',['-b',initial.bundleId]);const restored=await get('/api/diagnostics');evidence.foregroundRestored=restored.pid===initial.pid&&restored.bundleId===initial.bundleId;evidence.restoredForeground={pid:restored.pid,bundleId:restored.bundleId};
 await browser.close();await writeFile('artifacts/phase4-4-evidence.json',JSON.stringify(evidence,null,2)+'\n');
}
console.log(JSON.stringify({result:evidence.result,activation:evidence.activation?.status,safeInput:evidence.safeVerifier?.textInput,saved:evidence.safeVerifier?.shortcut,clipboardUnchanged:evidence.clipboardChangeCountUnchanged,restored:evidence.foregroundRestored,error:evidence.error}));if(failed)throw failed;
