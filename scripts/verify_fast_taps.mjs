// Real WebKit, all API intercepted. No native input, trash, or clipboard operation.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';import {createHash} from 'node:crypto';
const {webkit}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const folder=process.argv[2];if(!folder)throw Error('Screenshot folder required');
const browser=await webkit.launch(),context=await browser.newContext({viewport:{width:1366,height:1024}});
await context.addInitScript(()=>{
 window.setInterval=()=>0;localStorage.setItem('deck-mode','text');window.runStarts=[];window.runReplies=[];
 const original=window.fetch;window.fetch=async function(path,options){if(path==='/api/run')runStarts.push({at:performance.now(),...JSON.parse(options.body)});const response=await original(path,options);if(path==='/api/run'){const parse=response.json.bind(response);response.json=async()=>{const value=await parse();runReplies.push(performance.now());return value;};}return response;};
});
const page=await context.newPage(),pending=[],requests=[],errors=[],unexpected=[];page.on('pageerror',e=>errors.push(e.message));
const state={buttons:[...['one','two'].map(id=>({id,label:'합성 문구 '+id,kind:'text',text:id,enter:false})),...['a','b','c'].map(id=>({id,label:'합성 앱 '+id,kind:'app',app:id})),{id:'trash',label:'합성 휴지통',kind:'trash'}],metrics:{},clipboard:{count:0},preferences:{macSound:false}};
await page.route('**/api/**',async route=>{const path=new URL(route.request().url()).pathname;
 if(path==='/api/run'){requests.push(route.request().postDataJSON());pending.push(route);return;}
 const values={'/api/state':state,'/api/apps':{apps:['a','b','c'].map(id=>({id,name:'합성 '+id}))},'/api/diagnostics':{pid:999999,name:'합성 대상 · 실제 맥 실행 없음',focusedWindowReadable:true},'/api/system':{}};
 if(path==='/api/icon')return route.fulfill({status:404,body:''});
 if(path in values)return route.fulfill({json:values[path]});unexpected.push(path);await route.abort();
});
const tile=id=>page.locator(`.run-button[data-id="${id}"]`);
async function mode(value){await page.locator(`[data-mode=${value}]`).click();}
async function sent(n){for(let i=0;i<100&&requests.length<n;i++)await page.waitForTimeout(10);assert.equal(requests.length,n);}
async function reply(json={message:'합성 완료',status:'sent'},status=200){const n=await page.evaluate(()=>runReplies.length);assert.ok(pending.length);await pending.shift().fulfill({status,json});await page.waitForFunction(n=>runReplies.length>n,n);}
async function idle(){await page.waitForFunction(()=>!running);}
const evidence={kind:'WebKit + synthetic API only',checks:[]};
try{
 await page.goto((process.env.DECK_TEST_URL||'http://127.0.0.1:8765'));await page.locator('#dashboard').waitFor({state:'visible'});await page.waitForFunction(()=>!refreshBusy);
 await tile('one').click();await sent(1);await tile('two').click();assert.equal(requests.length,1);assert.match(await page.locator('#toast').textContent(),/현재 명령.*확인 중/);
 await reply();assert.equal(await page.evaluate(()=>running),false,'Response completed, but command is still locked');
 await tile('two').click();await sent(2);const elapsed=await page.evaluate(()=>runStarts[1].at-runReplies[0]);assert.ok(elapsed<350,`Next explicit tap delayed ${elapsed}ms`);evidence.nextTapAfterReplyMs=elapsed;await reply();await idle();evidence.checks.push('busy extra non-app tap explains; no queue; next tap under 350ms');
 // Active identity stays disabled across a rerender; one final busy screenshot.
 await tile('one').click();await sent(3);await mode('apps');await mode('text');assert.equal(await tile('one').isDisabled(),true);assert.equal(await tile('one').getAttribute('aria-busy'),'true');await tile('two').click();assert.equal(requests.length,3);
 await mkdir(folder,{recursive:true});const png=`${folder}/macOS-WebKit_iPad-size_busy_SYNTHETIC_${Date.now()}.png`;await page.screenshot({path:png,fullPage:true});const bytes=await readFile(png);evidence.screenshot={path:png,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20),sha256:createHash('sha256').update(bytes).digest('hex')};
 await reply();await idle();assert.equal(await tile('one').isDisabled(),false);evidence.checks.push('rerender busy identity and immediate release');
 await mode('apps');await tile('a').click();await sent(4);await tile('b').click();await tile('c').click();assert.equal(requests.length,4);await reply();await sent(5);assert.equal(requests[4].id,'c');await reply();await idle();evidence.checks.push('app first + last only');
 await tile('a').click();await sent(6);await tile('b').click();await page.evaluate(()=>window.dispatchEvent(new Event('offline')));assert.equal(await page.evaluate(()=>pendingApp),null);await page.evaluate(()=>refresh());
 await reply({error:'OLD ERROR MUST NOT REPLACE NEW STATE'},500);await idle();assert.equal(requests.length,6);assert.doesNotMatch(await page.locator('#toast').textContent(),/OLD ERROR/);assert.doesNotMatch(await page.locator('#target-status').textContent(),/전환 대기/);evidence.checks.push('disconnect cancels pending app; reconnect no replay; stale error suppressed');
 // Ordinary failure releases immediately and does not retry.
 await mode('text');await tile('one').click();await sent(7);await reply({error:'합성 실패'},500);assert.equal(await page.evaluate(()=>running),false);assert.match(await page.locator('#toast').textContent(),/합성 실패/);await tile('two').click();await sent(8);await reply();await idle();
 await mode('system');await tile('trash').click();await sent(9);await reply({confirmationRequired:true,confirmationId:'nonce1',expiresIn:3,message:'합성 확인'});assert.equal(await tile('trash').getAttribute('class').then(s=>s.includes('confirm-trash')),true);
 await tile('trash').click();await sent(10);assert.equal(requests[9].confirmationId,'nonce1');await reply();await idle();
 await page.waitForTimeout(1200);await tile('trash').click();await sent(11);assert.equal(requests[10].confirmationId,undefined);await reply({confirmationRequired:true,confirmationId:'nonce2',expiresIn:3,message:'합성 확인2'});
 await page.waitForTimeout(1900);assert.equal(await tile('trash').getAttribute('class').then(s=>s.includes('confirm-trash')),true,'old expiry cleared new confirmation');assert.equal(await page.evaluate(()=>confirmations.get('trash')?.id),'nonce2');
 await page.waitForTimeout(1200);assert.equal(await page.evaluate(()=>confirmations.has('trash')),false);await tile('trash').click();await sent(12);assert.equal(requests[11].confirmationId,undefined);
 await mode('apps');await mode('system');await reply({confirmationRequired:true,confirmationId:'stale',expiresIn:3,message:'합성 늦은 확인'});assert.equal(await page.locator('.confirm-trash').count(),0);assert.equal(await page.evaluate(()=>confirmations.size),0);
 evidence.checks.push('trash first/second nonce, expired nonce absent, old timer does not clear new arm, stale render response ignored');
 assert.equal(new Set(requests.map(r=>r.requestId)).size,requests.length);assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);evidence.runRequestCount=requests.length;evidence.uniqueRequestIds=true;evidence.result='PASS';await writeFile('artifacts/phase4-7-evidence.json',JSON.stringify(evidence,null,2)+'\n');console.log(JSON.stringify(evidence));
}finally{await browser.close();}
