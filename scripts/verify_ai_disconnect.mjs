// Real WebKit + production assets. Every API response is synthetic; no native calls.
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const {webkit}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const directory=process.argv[2];if(!directory)throw Error('Screenshot folder required');await mkdir(directory,{recursive:true});
const browser=await webkit.launch();const context=await browser.newContext({viewport:{width:1366,height:1024}});
await context.addInitScript(()=>{
  window.setInterval=()=>0;localStorage.setItem('deck-mode','ai');
  window.audioStarts=0;window.AudioContext=class{state='suspended';currentTime=0;destination={};async resume(){this.state='running';}createGain(){return {gain:{},connect(){}};}createOscillator(){return {frequency:{},connect(){},start(){audioStarts++;},stop(){}};}};
});
const page=await context.newPage(),errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
const state={buttons:[],metrics:{},clipboard:{count:0},preferences:{macSound:false},ai:{epoch:'synthetic-disconnect',sources:[],slots:Array.from({length:12},(_,slot)=>({slot,id:'fixture:'+slot,label:'합성 시험 세션 '+(slot+1),state:slot===0?'input-required':slot===1?'working':'unregistered',revision:1,transition:slot===0?'old-transition':null}))}};
const image='data:image/svg+xml;base64,'+Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="700" height="180"><rect width="700" height="180" fill="#272c31"/><text x="35" y="95" fill="white" font-size="24">SYNTHETIC CAPTURE - NO NATIVE WINDOW</text></svg>').toString('base64');
let holdDetail=false,holdReply=false,holdState=false,pendingDetail=[],pendingReply=[],pendingState=[];
await page.route('**/api/**',async route=>{
 const url=new URL(route.request().url()),path=url.pathname;requests.push({path,method:route.request().method()});
 if(path==='/api/state'){if(holdState)await new Promise(r=>pendingState.push(r));return route.fulfill({json:state});}
 if(path==='/api/apps')return route.fulfill({json:{apps:[{id:'fixture',name:'Fixture'}]}});
 if(path==='/api/diagnostics')return route.fulfill({json:{name:'합성 시험',pid:999999,bundleId:'test',focusedWindowReadable:true}});
 if(path==='/api/ai/detail'){
  const slot=Number(url.searchParams.get('slot'));const detail={...state.ai.slots[slot],nonce:'test-nonce-'+requests.length,image,capturedAt:Date.now()/1000};
  if(holdDetail)await new Promise(r=>pendingDetail.push(r));return route.fulfill({json:detail});
 }
 if(path==='/api/ai/reply'){if(holdReply)await new Promise(r=>pendingReply.push(r));return route.fulfill({json:{message:'LATE SYNTHETIC REPLY RESULT'}});}
 throw Error('Unexpected API: '+path);
});
const manifest=[],stamp=Date.now();
async function shot(name){const path=`${directory}/macOS-WebKit_iPad-size_${name}_SYNTHETIC_${stamp}.png`;await page.screenshot({path,fullPage:true});const b=await readFile(path);manifest.push({path,width:b.readUInt32BE(16),height:b.readUInt32BE(20),sha256:createHash('sha256').update(b).digest('hex')});}
async function tick(){await page.waitForFunction(()=>!refreshBusy);await page.evaluate(()=>refresh());}
async function expectNoProof(){assert.equal(await page.evaluate(()=>aiProof),null);assert.equal(await page.locator('[data-reply]:enabled').count(),0);}
async function offline(){await page.evaluate(()=>window.dispatchEvent(new Event('offline')));await expectNoProof();assert.equal(await page.locator('[data-state=disconnected]').count(),12);assert.equal(await page.locator('#slots .slot').nth(1).evaluate(el=>getComputedStyle(el).animationName),'none');}
async function capture(){await page.locator('#ai-capture').click();await page.waitForFunction(()=>aiProof!==null);}
async function waitPending(list){for(let n=0;n<100&&!list.length;n++)await page.waitForTimeout(10);assert.ok(list.length);}
try{
 await page.goto((process.env.DECK_TEST_URL||'http://127.0.0.1:8765'));await page.locator('#dashboard').waitFor({state:'visible'});await page.waitForFunction(()=>!refreshBusy);await page.locator('#tablet-sound').click();
 await page.locator('#slots .slot').first().click();await capture();await shot('ai_connected_detail');
 const snapshot=await page.evaluate(()=>JSON.stringify(aiState));
 holdDetail=true;await page.locator('#ai-capture').click();await waitPending(pendingDetail);await offline();assert.equal(await page.evaluate(()=>JSON.stringify(aiState)),snapshot);
 pendingDetail.shift()();await page.waitForTimeout(100);await expectNoProof();assert.match(await page.locator('#ai-image-note').textContent(),/마지막 캡처.*연결 끊김/);await shot('ai_disconnected_detail');
 holdDetail=false;await tick();await expectNoProof();assert.equal(await page.locator('#slots .slot').first().getAttribute('data-state'),'input-required');assert.equal(await page.evaluate(()=>audioStarts),1);assert.match(await page.locator('#ai-detail-note').textContent(),/연결 복구/);assert.match(await page.locator('#ai-image-note').textContent(),/새 확인 필요/);await shot('ai_reconnected_requires_new_detail');
 // Pending reply cannot overwrite disconnected/reopened detail, and is never retried.
 await capture();holdReply=true;await page.locator('[data-reply=enter]').click();await waitPending(pendingReply);await offline();await tick();pendingReply.shift()();await page.waitForTimeout(100);await expectNoProof();assert.doesNotMatch(await page.locator('#ai-detail-note').textContent(),/LATE/);
 // Same-slot close/reopen and different-slot selection invalidate old capture generations.
 for(const slot of [0,1]){
  holdDetail=true;await page.locator('#ai-capture').click();await waitPending(pendingDetail);await page.locator('#ai-dialog .close-dialog').click();await page.locator('#slots .slot').nth(slot).click();pendingDetail.shift()();await page.waitForTimeout(100);await expectNoProof();assert.equal(await page.locator('#ai-image').isVisible(),false);
 }
 // A snapshot requested before disconnect cannot reconnect the UI when it arrives late.
 holdState=true;await page.evaluate(()=>{void refresh();});await waitPending(pendingState);await offline();pendingState.shift()();await page.waitForFunction(()=>!refreshBusy);assert.equal(await page.evaluate(()=>connected),false);holdState=false;await tick();await expectNoProof();
 assert.equal(requests.filter(r=>r.path==='/api/ai/reply').length,1);assert.equal(requests.filter(r=>r.path==='/api/run').length,0);assert.equal(await page.evaluate(()=>audioStarts),1);assert.deepEqual(errors,[]);
 await writeFile('artifacts/phase4-1-screenshot-manifest.json',JSON.stringify(manifest,null,2)+'\n');
 console.log('PASS: offline proof/animation, late detail/reply/snapshot, close/reopen and slot generation, reconnect no replay; 1 intercepted synthetic reply; 0 native requests; PNG 3');
}finally{await browser.close();}
