// Synthetic browser policy test; no native approval and no audible playback.
import assert from 'node:assert/strict';
const {webkit}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await webkit.launch();const context=await browser.newContext();
await context.addInitScript(()=>{
 window.testAudio={starts:0,resumes:0};
 window.AudioContext=class {state='suspended';currentTime=0;destination={};async resume(){this.state='running';testAudio.resumes++;}createOscillator(){return {frequency:{},connect(){},start(){testAudio.starts++;},stop(){}};}createGain(){return {gain:{},connect(){}};}};
});
const page=await context.newPage();let state;
async function tick(){await page.waitForFunction(()=>!refreshBusy);await page.evaluate(()=>refresh());}
try{
 await page.goto((process.env.DECK_TEST_URL||'http://127.0.0.1:8765'));await page.locator('#pair-code').fill(process.env.DECK_CODE);await page.locator('#pair-form button').click();await page.locator('#dashboard').waitFor({state:'visible'});
 state=await page.evaluate(async()=>await (await fetch('/api/state')).json());state.ai.epoch='notification-policy-fixture';state.ai.slots=[{slot:0,id:'test',state:'input-required',transition:'old',revision:1}];
 await page.route('**/api/state',r=>r.fulfill({json:state}));await page.reload();await page.locator('#dashboard').waitFor({state:'visible'});
 assert.equal(await page.evaluate(()=>testAudio.starts),0);
 await page.locator('#tablet-sound').click();assert.equal(await page.evaluate(()=>testAudio.starts),1);
 await tick();assert.equal(await page.evaluate(()=>testAudio.starts),1);
 state.ai.slots[0].transition='new';state.ai.slots[0].revision=2;await tick();assert.equal(await page.evaluate(()=>testAudio.starts),2);
 await tick();assert.equal(await page.evaluate(()=>testAudio.starts),2);
 await page.evaluate(()=>connection(false));state.ai.slots[0].transition='disconnected';await tick();assert.equal(await page.evaluate(()=>testAudio.starts),2);
 await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));await page.waitForTimeout(100);state.ai.slots[0].transition='background-return';await page.evaluate(()=>{notificationBaseline=true;return refresh();});assert.equal(await page.evaluate(()=>testAudio.starts),2);
 await page.reload();await page.locator('#dashboard').waitFor({state:'visible'});assert.equal(await page.evaluate(()=>testAudio.starts),0);assert.equal(await page.evaluate(()=>testAudio.resumes),0);
 // Enabled preference does not auto-resume audio after reload. Gesture resumes and plays test tone.
 await page.locator('#tablet-sound').click();assert.equal(await page.evaluate(()=>testAudio.resumes),1);
 console.log('PASS synthetic notification policy: initial/repeat/reconnect/background/reload/gesture; actual listening not tested');
}finally{await browser.close();}
