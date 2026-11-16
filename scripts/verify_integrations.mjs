import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const {webkit}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const directory=process.argv[2];if(!directory)throw Error('Screenshot directory required');await mkdir(directory,{recursive:true});
const browser=await webkit.launch();const context=await browser.newContext({viewport:{width:1366,height:1024}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const root=(process.env.DECK_TEST_URL||'http://127.0.0.1:8765'),manifest=[],stamp=Date.now();
async function capture(name){const path=`${directory}/macOS-WebKit_${name}_${stamp}.png`;await page.screenshot({path,fullPage:true});const bytes=await readFile(path);manifest.push({path,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20),sha256:createHash('sha256').update(bytes).digest('hex')});}
try{
 await page.goto(root);await page.locator('#pair-code').fill(process.env.DECK_CODE);await page.locator('#pair-form button').click();await page.locator('#dashboard').waitFor({state:'visible'});await page.locator('[data-mode=ai]').click();
 await page.waitForFunction(()=>document.querySelector('#codex-status').textContent==='실제 계정 한도');
 await page.waitForFunction(()=>document.querySelector('#slots .slot').dataset.state==='working');
 const real=await page.evaluate(async()=>await (await fetch('/api/state')).json());
 await capture('iPad-size_landscape_ai_actual-event_light');
 await page.locator('#slots .slot').first().click();await page.locator('#ai-capture').click();await page.locator('#ai-detail-note').filter({hasText:'연결을 증명'}).waitFor();await capture('iPad-size_landscape_ai_mapping-unverified_light');await page.locator('#ai-dialog .close-dialog').click();
 await page.locator('#weather-settings').click();await page.locator('#weather-city').fill('Seoul');await page.locator('#weather-search').click();await page.locator('#weather-results button').first().waitFor({timeout:15000});await capture('iPad-size_landscape_weather_real-city-search');await page.locator('#weather-dialog .close-dialog').click();
 await page.locator('[data-mode=text]').click();await capture('iPad-size_landscape_text_preset-choice');
 // Exercise presets in isolated HTTP state test; do not modify the user's button array here.
 await page.locator('[data-mode=ai]').click();await page.locator('#theme').click();await page.setViewportSize({width:1024,height:1366});await capture('iPad-size_portrait_ai_actual-event_dark');
 await page.setViewportSize({width:390,height:844});await capture('phone-size_ai_actual-event_dark');
 // Explicitly synthetic API fixture only; never inserted into the live server.
 const synthetic=structuredClone(real);synthetic.ai.epoch='synthetic-browser-test';synthetic.ai.slots=Array.from({length:12},(_,n)=>({slot:n,id:'test:'+n,label:'합성 상태 '+n,state:['working','idle','completed','input-required','offline','unregistered'][n%6],revision:1,transition:n%6===3?'fixture-transition-'+n:null}));synthetic.usage.claude={status:'error',windows:[],message:'합성 오류 검증 · 공급원 연결 실패'};
 await page.route('**/api/state',route=>route.fulfill({json:synthetic}));await page.reload();await page.locator('#dashboard').waitFor({state:'visible'});await page.waitForFunction(()=>document.querySelectorAll('[data-state="input-required"]').length===2);await capture('phone-size_ai_SYNTHETIC_transitions-error_dark');
 await page.setViewportSize({width:1366,height:1024});await page.locator('#theme').click();await capture('iPad-size_landscape_ai_SYNTHETIC_states_light');
 await context.setOffline(true);await page.evaluate(()=>window.dispatchEvent(new Event('offline')));await capture('iPad-size_landscape_ai_offline_light');
 assert.deepEqual(errors,[]);await writeFile('artifacts/phase4-screenshot-manifest.json',JSON.stringify(manifest,null,2)+'\n');
 const evidence={actualEvent:{source:real.ai.slots[0].source,provider:real.ai.slots[0].provider,state:real.ai.slots[0].state,sessionSuffix:real.ai.slots[0].id.slice(-8)},actualQuota:real.usage.codex,actualCitySearch:true,screenshots:manifest.length,browserErrors:errors,platform:'WebKit iPad-size / phone-size; no physical iPad'};
 await writeFile('artifacts/phase4-browser-evidence.json',JSON.stringify(evidence,null,2)+'\n');console.log(JSON.stringify(evidence));
}finally{await browser.close();}
