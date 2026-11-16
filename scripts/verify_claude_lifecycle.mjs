// One real Claude SessionStart/SessionEnd trial; no user messages or model requests.
// Usage: DECK_CODE=... node scripts/verify_claude_lifecycle.mjs <screenshot-directory>
import {spawn} from 'node:child_process';
import {randomUUID,createHash} from 'node:crypto';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import assert from 'node:assert/strict';
const {webkit}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const folder=process.argv[2],code=process.env.DECK_CODE,root=process.env.DECK_URL||(process.env.DECK_TEST_URL||'http://127.0.0.1:8765');
if(!folder||!code)throw Error('Screenshot directory and DECK_CODE required');
await mkdir(folder,{recursive:true});
const browser=await webkit.launch(),context=await browser.newContext({viewport:{width:1366,height:1024}}),page=await context.newPage();
let child,slot,before,settingsBefore;const id=randomUUID(),session='claude:'+id,bridgePath=resolve('.deck-data/claude-events',createHash('sha256').update(id).digest('hex')+'.json');
const evidence={sessionSuffix:id.slice(-8),launches:0,userMessages:0,modelRequests:0,heartbeatVerified:false,hookEvents:[],screenshots:[]};
const settingsPath=resolve('.claude/settings.local.json');const stamp=Date.now();
async function state(){const r=await context.request.get(root+'/api/state');assert.equal(r.status(),200);return r.json();}
async function post(path,data){const r=await context.request.post(root+path,{data,headers:{Origin:root}});assert.equal(r.status(),200);return r.json();}
async function until(fn,seconds){const deadline=Date.now()+seconds*1000;while(Date.now()<deadline){const value=await fn();if(value)return value;await new Promise(r=>setTimeout(r,100));}throw Error('Observation deadline exceeded; no retry');}
async function bridge(){try{const d=JSON.parse(await readFile(bridgePath,'utf8'));assert.equal(d.session,id);return d;}catch(e){if(e.code==='ENOENT')return null;throw e;}}
async function uiState(expected){
 await page.waitForFunction(()=>!refreshBusy);await page.evaluate(()=>refresh());
 return page.evaluate(({slot,session,expected})=>{const el=document.querySelectorAll('#slots .slot')[slot];return aiState.slots[slot]?.id===session&&el.dataset.state===expected?{state:el.dataset.state,color:getComputedStyle(el).backgroundColor,at:Date.now()/1000}:null;},{slot,session,expected});
}
async function shot(name){const path=join(folder,`macOS-WebKit_iPad-size_Claude_actual_${name}_${stamp}.png`);await page.screenshot({path,fullPage:true});const b=await readFile(path);evidence.screenshots.push({path,width:b.readUInt32BE(16),height:b.readUInt32BE(20),sha256:createHash('sha256').update(b).digest('hex')});}
let failure;
try{
 // All browser, authentication, slot selection and snapshot work precedes the single CLI launch.
 settingsBefore=await readFile(settingsPath);await post('/api/pair',{code});before=await state();slot=before.ai.slots.findIndex(s=>s.id==null);assert.ok(slot>=0,'No empty slot');
 await page.goto(root);await page.locator('#dashboard').waitFor({state:'visible'});await page.locator('[data-mode=ai]').click();await page.waitForFunction(()=>!refreshBusy);
 evidence.browserReadyAt=Date.now()/1000;evidence.slotNumber=slot+1;
 child=spawn('claude',['--print','--input-format','stream-json','--output-format','stream-json','--verbose','--include-hook-events','--no-session-persistence','--session-id',id,'--tools','','--permission-prompts','none','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--setting-sources','project,local','--no-chrome'],{cwd:process.cwd(),stdio:['pipe','pipe','ignore']});
 evidence.launches=1;evidence.cliStartedAt=Date.now()/1000;
 let buffer='';child.stdout.on('data',chunk=>{buffer+=chunk;let cut;while((cut=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,cut);buffer=buffer.slice(cut+1);try{const d=JSON.parse(line);if(d.type==='system'&&['hook_started','hook_response'].includes(d.subtype))evidence.hookEvents.push({subtype:d.subtype,event:d.hook_event,name:d.hook_name});}catch{}}if(buffer.length>1000000)buffer='';});
 const exit=new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',(code,signal)=>resolve({code,signal}));});
 const start=await until(async()=>{const d=await bridge();return d?.state==='idle'?d:null;},20);evidence.startUpdatedAt=start.updatedAt;
 await until(async()=>(await state()).ai.sources.some(s=>s.id===session),10);
 await post('/api/ai/register',{slot,session});
 const apiIdle=await until(async()=>{const s=(await state()).ai.slots[slot];return s.id===session&&s.state==='idle'?{state:s.state,at:Date.now()/1000}:null;},10);
 evidence.apiIdle=apiIdle;evidence.apiIdleElapsedSeconds=apiIdle.at-start.updatedAt;
 evidence.uiIdle=await until(()=>uiState('idle'),10);evidence.uiIdleElapsedSeconds=evidence.uiIdle.at-start.updatedAt;
 assert.ok(evidence.apiIdleElapsedSeconds<30&&evidence.uiIdleElapsedSeconds<30);assert.equal(evidence.uiIdle.color,'rgb(73, 134, 90)');
 await shot('idle_green');evidence.idleScreenshotElapsedSeconds=Date.now()/1000-start.updatedAt;assert.ok(evidence.idleScreenshotElapsedSeconds<30);
 child.stdin.end();evidence.eofAt=Date.now()/1000;
 const end=await until(async()=>{const d=await bridge();return d?.state==='ended'?d:null;},15);evidence.endUpdatedAt=end.updatedAt;
 evidence.apiEnded=await until(async()=>{const s=(await state()).ai.slots[slot];return s.id===session&&s.state==='offline'?{state:s.state,at:Date.now()/1000}:null;},10);
 evidence.uiEnded=await until(()=>uiState('offline'),10);assert.equal(evidence.uiEnded.color,'rgb(148, 151, 142)');await shot('ended_gray');
 evidence.cliExit=await Promise.race([exit,new Promise((_,reject)=>setTimeout(()=>reject(Error('CLI exit timeout')),5000))]);assert.equal(evidence.cliExit.code,0);
 evidence.sameSessionVerified=true;evidence.result='PASS';
}catch(error){failure=error;evidence.result='FAIL';evidence.error=error.message;}
finally{
 if(child&&child.exitCode===null){child.stdin.end();child.kill('SIGTERM');await new Promise(r=>setTimeout(r,1000));if(child.exitCode===null)child.kill('SIGKILL');}
 if(before&&slot!==undefined&&slot>=0){await post('/api/ai/register',{slot,session:before.ai.slots[slot].id});const after=await state();assert.deepEqual(after.ai.slots.map(s=>s.id),before.ai.slots.map(s=>s.id));assert.deepEqual(after.buttons,before.buttons);assert.deepEqual(after.preferences,before.preferences);evidence.slotsButtonsPreferencesRestored=true;}
 if(settingsBefore){assert.deepEqual(await readFile(settingsPath),settingsBefore);evidence.settingsUnchanged=true;}
 await browser.close();await writeFile('artifacts/phase4-2b-evidence.json',JSON.stringify(evidence,null,2)+'\n');
}
console.log(JSON.stringify({result:evidence.result,sessionSuffix:evidence.sessionSuffix,apiIdleElapsedSeconds:evidence.apiIdleElapsedSeconds,uiIdleElapsedSeconds:evidence.uiIdleElapsedSeconds,idleScreenshotElapsedSeconds:evidence.idleScreenshotElapsedSeconds,cliExit:evidence.cliExit,restored:evidence.slotsButtonsPreferencesRestored}));
if(failure)throw failure;
