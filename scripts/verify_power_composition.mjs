// Focused missing-compositionend regression. No insertText, no native inputs.
import assert from 'node:assert/strict';import {mkdir,readFile,writeFile} from 'node:fs/promises';import {createHash} from 'node:crypto';
const {chromium,webkit}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');const folder=process.argv[2];await mkdir(folder,{recursive:true});const results=[];
for(const engine of ['chromium','webkit']){
 const browser=await(engine==='chromium'?chromium.launch({...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})}):webkit.launch()),page=await browser.newPage({viewport:{width:393,height:851},isMobile:true,hasTouch:true});await page.clock.install();await page.addInitScript(()=>window.addEventListener('compositionend',e=>e.stopImmediatePropagation(),true));
 const calls=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',route=>{const path=new URL(route.request().url()).pathname;calls.push(path);const data={'/api/state':{buttons:[{id:'test',kind:'text',label:'시험',text:'보존할 한글 👋',enter:false}],preferences:{},metrics:{},clipboard:{count:0}},'/api/apps':{apps:[]},'/api/diagnostics':{}};assert.ok(path in data,path);return route.fulfill({json:data[path]});});
 const settle=()=>new Promise(r=>setTimeout(r,60));const advance=async ms=>{await page.clock.runFor(ms);await settle();};
 try{
  await page.goto((process.env.DECK_TEST_URL||'http://127.0.0.1:8765'));await settle();await page.locator('[data-mode=text]').tap();await page.locator('#edit').tap();await page.locator('.run-button').tap();await page.locator('#button-text').focus();
  // Explicitly drop compositionend after a real Chromium composition start.
  if(engine==='chromium'){const cdp=await page.context().newCDPSession(page);await cdp.send('Input.imeSetComposition',{text:'한',selectionStart:1,selectionEnd:1});}
  else await page.evaluate(()=>{powerComposing=true;if(typeof powerCompositionTarget!=='undefined')powerCompositionTarget=document.querySelector('#button-text');});
  assert.equal(await page.evaluate(()=>powerComposing),true);await advance(31000);assert.equal(await page.locator('#power-overlay').evaluate(e=>e.open),false);
  const value=await page.locator('#button-text').inputValue();await page.locator('#button-label').focus();await settle();assert.equal(await page.evaluate(()=>powerComposing),false,'blur must release stale composition state');assert.equal(await page.locator('#button-text').inputValue(),value);
  await advance(30001);assert.equal(await page.locator('#power-overlay').evaluate(e=>e.open),true);await page.touchscreen.tap(100,200);await settle();assert.equal(await page.locator('#button-text').inputValue(),value);
  // Isolate a missed end at visibility loss; no second CDP composition attempt.
  await page.locator('#button-text').focus();await page.evaluate(()=>{powerComposing=true;powerCompositionTarget=document.querySelector('#button-text');Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});assert.equal(await page.evaluate(()=>powerComposing),false,'hidden must clear suspended composition');
  await page.clock.setSystemTime(new Date(Date.now()+3600000));await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));});assert.equal(await page.locator('#power-overlay').evaluate(e=>e.open),true);await page.touchscreen.tap(100,200);await settle();assert.equal(await page.locator('#button-text').inputValue(),value);
  // Returning to actual composing input re-arms the guard, not a permanent timeout bypass.
  if(engine==='chromium'){await page.locator('#button-text').focus();const cdp=await page.context().newCDPSession(page);await cdp.send('Input.imeSetComposition',{text:'글',selectionStart:1,selectionEnd:1});assert.equal(await page.evaluate(()=>powerComposing),true);await advance(31000);assert.equal(await page.locator('#power-overlay').evaluate(e=>e.open),false);await page.locator('#button-label').focus();}
  await settle();if(await page.locator('#power-overlay').evaluate(e=>e.open)){await page.touchscreen.tap(100,200);await settle();}assert.equal(await page.locator('#edit-dialog').evaluate(e=>e.open),true);let screenshot=null;if(engine==='chromium'){const path=`${folder}/macOS_Chromium_mobile_IME-blur-preserved_${Date.now()}.png`;await page.screenshot({path});const b=await readFile(path);screenshot={path,sha256:createHash('sha256').update(b).digest('hex')};}
  assert.deepEqual(errors,[]);assert.equal(calls.some(p=>p==='/api/run'||p==='/api/buttons'),false);results.push({engine,pass:true,composition:engine==='chromium'?'CDP start plus deliberately dropped end':'synthetic stale flag',visibility:'synthetic hidden/visible events',valuePreserved:true,executionPosts:0,screenshot});
 }finally{await browser.close();}
}
await writeFile('artifacts/power-composition-evidence.json',JSON.stringify({physicalIME:false,results},null,2)+'\n');console.log('PASS focused composition lifecycle');
