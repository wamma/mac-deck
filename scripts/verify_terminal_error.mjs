// Real WebKit, synthetic errors only: no native/AppleEvent calls or permission probes.
import assert from 'node:assert/strict';import {readFile,writeFile,mkdir} from 'node:fs/promises';import {createHash} from 'node:crypto';
const {webkit}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const folder=process.argv[2],message=await readFile(process.argv[3],'utf8');if(!folder||!message.includes('-1712'))throw Error('Folder and pure classifier timeout message required');
const browser=await webkit.launch(),context=await browser.newContext({viewport:{width:1366,height:1024}});await context.addInitScript(()=>{window.setInterval=()=>0;localStorage.setItem('deck-mode','ai');});
const page=await context.newPage(),errors=[],unexpected=[];let detailCalls=0;page.on('pageerror',e=>errors.push(e.message));
const state={buttons:[],metrics:{},preferences:{macSound:false},clipboard:{count:0},ai:{sources:[{id:'synthetic',label:'합성 Terminal 권한 오류',state:'idle'}],slots:Array.from({length:12},(_,slot)=>({slot,id:slot===0?'synthetic':null,state:slot===0?'idle':'unregistered',label:'합성 권한 안내',revision:1}))}};
await page.route('**/api/**',async route=>{const path=new URL(route.request().url()).pathname;
 if(path==='/api/ai/detail'){detailCalls++;return route.fulfill({status:503,json:{error:message}});}
 const responses={'/api/state':state,'/api/apps':{apps:[]},'/api/diagnostics':{pid:999999,name:'합성 대상 · OS 조회 없음',focusedWindowReadable:true}};
 if(path in responses)return route.fulfill({json:responses[path]});unexpected.push(path);await route.abort();
});
try{
 await page.goto((process.env.DECK_TEST_URL||'http://127.0.0.1:8765'));await page.locator('#dashboard').waitFor({state:'visible'});await page.locator('#slots .slot').first().click();await page.locator('#ai-capture').click();await page.waitForFunction(()=>document.querySelector('#ai-detail-note').textContent.includes('-1712'));
 assert.equal(await page.locator('#ai-detail-note').textContent(),message);assert.equal(await page.locator('[data-reply]:enabled').count(),0);assert.equal(await page.locator('#ai-image').isVisible(),false);assert.equal(await page.evaluate(()=>aiProof),null);
 await page.waitForTimeout(1500);assert.equal(detailCalls,1);assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);
 await mkdir(folder,{recursive:true});const path=`${folder}/macOS-WebKit_iPad-size_Terminal-timeout_SYNTHETIC_${Date.now()}.png`;await page.screenshot({path,fullPage:true});const bytes=await readFile(path);
 const evidence={result:'PASS',kind:'WebKit + pure classifier synthetic -1712; no native invocation',detailCalls,automaticRetries:0,replyRequests:0,replyButtonsDisabled:true,imageHidden:true,screenshot:{path,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20),sha256:createHash('sha256').update(bytes).digest('hex')}};
 await writeFile('artifacts/phase4-9-evidence.json',JSON.stringify(evidence,null,2)+'\n');console.log(JSON.stringify(evidence));
}finally{await browser.close();}
