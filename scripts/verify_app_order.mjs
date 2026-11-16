// Real read-only UI/state checks after authorized config save. Never send /api/run.
import assert from 'node:assert/strict';import {execFileSync} from 'node:child_process';import {mkdir,readFile,writeFile} from 'node:fs/promises';import {createHash} from 'node:crypto';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');const folder=process.argv[2];await mkdir(folder,{recursive:true});
const code=process.env.DECK_CODE;if(!code)throw Error('Set DECK_CODE for your isolated test server');
const browser=await chromium.launch({...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})}),context=await browser.newContext({viewport:{width:1280,height:900},hasTouch:true}),page=await context.newPage();await context.addInitScript(()=>{localStorage.setItem('deck-mode','apps');localStorage.setItem('deck-theme','dark');localStorage.setItem('deck-power-save','false');});let execution=0,pairings=0;
await page.route('**/api/**',route=>{const path=new URL(route.request().url()).pathname;if(route.request().method()==='POST'){if(path==='/api/pair')pairings++;else{execution++;return route.abort();}}return route.continue();});
async function pair(){await page.locator('#pair-screen').waitFor({state:'visible'});await page.locator('#pair-code').fill(code);await page.locator('#pair-form button[type=submit]').click();await page.locator('#dashboard').waitFor({state:'visible'});}
async function order(){return page.locator('.run-button').evaluateAll(es=>es.map(e=>e.dataset.id));}
try{
 await page.goto((process.env.DECK_TEST_URL||'http://127.0.0.1:8765'));await pair();const ids=await page.evaluate(async()=>{const s=await(await fetch('/api/state')).json();return s.buttons.filter(b=>b.kind==='app').map(b=>b.id);});assert.deepEqual(await order(),ids);
 await page.reload();await page.locator('#dashboard').waitFor({state:'visible'});assert.deepEqual(await order(),ids);
 await context.clearCookies();await page.reload();await pair();assert.deepEqual(await order(),ids);assert.equal(pairings,2);assert.equal(execution,0);
 await page.waitForFunction(()=>[...document.querySelectorAll('.tile-icon img')].every(i=>i.complete));await page.waitForTimeout(180);const path=`${folder}/macOS_Chromium_live_app-order_dark_${Date.now()}.png`;await page.screenshot({path,fullPage:true});const b=await readFile(path);
 await writeFile('artifacts/app-order-browser-evidence.json',JSON.stringify({actualAPI:true,physicalGalaxy:false,appCount:ids.length,reloadOrderPreserved:true,rePairOrderPreserved:true,pairings,executionRequests:execution,screenshot:{path,sha256:createHash('sha256').update(b).digest('hex'),width:b.readUInt32BE(16),height:b.readUInt32BE(20)}},null,2)+'\n');console.log('PASS actual saved app order after reload and re-pair');
}finally{await browser.close();}
