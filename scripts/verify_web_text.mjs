// Real HTTP and real native input; only the enclosing test Mac pins the dedicated target.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const config=JSON.parse(await readFile(process.argv[2],'utf8'));
const browser=await chromium.launch({...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),headless:true});
const context=await browser.newContext({viewport:{width:1366,height:1024}}),page=await context.newPage();
const evidence={runRequests:[]};
page.on('request',r=>{if(r.url().endsWith('/api/run'))evidence.runRequests.push(r.postDataJSON());});
async function get(path){const r=await context.request.get(config.root+path);assert.equal(r.status(),200);return r.json();}
async function add(label,kind,fill){await page.locator('#edit').click();await page.locator('.add-tile').click();await page.locator('#button-label').fill(label);await page.locator('#button-kind').selectOption(kind);await fill();await page.locator('#button-form button[type=submit]').click();await page.locator('#edit-dialog').waitFor({state:'hidden'});await page.locator('#edit').click();}
async function run(label){await page.waitForFunction(()=>!running);const response=page.waitForResponse(r=>r.url().endsWith('/api/run')&&r.request().method()==='POST');await page.locator('.run-button').filter({hasText:label}).click();const r=await response;const body=await r.json();assert.equal(r.status(),200,JSON.stringify(body));return body;}
try{
 await page.goto(config.root);await page.locator('#pair-code').fill(config.code);await page.locator('#pair-form button').click();await page.locator('#dashboard').waitFor({state:'visible'});
 await page.locator('[data-mode=apps]').click();await add('4-5 시험 TextEdit','app',async()=>{const opts=await page.locator('#button-app option').evaluateAll(es=>es.map(e=>({id:e.value,name:e.textContent})));await page.locator('#button-app').selectOption(opts.find(a=>a.name==='TextEdit').id);});
 if(config.clipboardMode){
   for(const [label,key,modifiers] of [['전체선택','a',['command']],['복사','c',['command']],['선택끝','right',[]],['붙여넣기','v',['command']],['저장','s',['command']]]){
     await add('4-6 시험 '+label,'shortcut',async()=>{await page.locator('#button-key').selectOption(key);for(const box of await page.locator('.modifier-options input').all())await box.uncheck();for(const modifier of modifiers)await page.locator('.modifier-options input[value='+modifier+']').check();});
   }
 }else{
 await add('4-5 시험 문구','text',async()=>{await page.locator('#button-text').fill(config.text);await page.locator('#button-enter').check();});
 await add('4-5 시험 저장','shortcut',async()=>{await page.locator('#button-key').selectOption('s');for(const box of await page.locator('.modifier-options input').all())await box.uncheck();await page.locator('.modifier-options input[value=command]').check();});
 }
 const before=await get('/api/state'),disk=JSON.parse(await readFile(config.config,'utf8'));assert.deepEqual(disk.buttons,before.buttons);assert.deepEqual(disk.preferences,before.preferences);
 await page.reload();await page.locator('#dashboard').waitFor({state:'visible'});const after=await get('/api/state');assert.deepEqual(after.buttons,before.buttons);assert.deepEqual(after.preferences,before.preferences);evidence.buttonsPersistedAndReloaded=true;
 await page.locator('[data-mode=apps]').click();evidence.activation=await run('4-5 시험 TextEdit');assert.equal(evidence.activation.status,'verified');const d=await get('/api/diagnostics');for(const k of ['pid','windowId','documentURL'])assert.equal(d[k],config.expected[k]);evidence.foreground={pid:d.pid,windowId:d.windowId,documentURL:d.documentURL};
 if(config.clipboardMode){
   await page.locator('[data-mode=system]').click();evidence.actions=[];
   for(const label of ['전체선택','복사','선택끝','붙여넣기','저장'])evidence.actions.push({action:label,response:await run('4-6 시험 '+label)});
   assert.equal(evidence.runRequests.length,6);
 }else{
 await page.locator('[data-mode=text]').click();evidence.text=await run('4-5 시험 문구');
 await page.locator('[data-mode=system]').click();evidence.save=await run('4-5 시험 저장');assert.equal(evidence.runRequests.length,3); }
 evidence.result='PASS';
}catch(e){evidence.result='FAIL';evidence.error=e.message;throw e;}finally{await writeFile(config.result,JSON.stringify(evidence,null,2));await browser.close();}
