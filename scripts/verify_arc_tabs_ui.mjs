import assert from 'node:assert/strict';import {readFile,writeFile,mkdir} from 'node:fs/promises';import {createHash} from 'node:crypto';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');const folder=process.argv[2];await mkdir(folder,{recursive:true});
const browser=await chromium.launch({...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});const page=await browser.newPage({viewport:{width:393,height:851},isMobile:true,hasTouch:true});
await page.addInitScript(()=>{localStorage.setItem('deck-mode','apps');localStorage.setItem('deck-power-save','false');window.setInterval=()=>0;});
const bundle='company.thebrowser.Browser',buttons=[{id:'arc',kind:'app',app:'arc-app',label:'내 브라우저'},{id:'other',kind:'app',app:'other-app',label:'Arc'}];
const state={buttons,preferences:{},metrics:{},clipboard:{count:0},ai:{slots:[],sources:[]}};
const tabs=Array.from({length:97},(_,i)=>({id:'t'+i,title:i===0?'아주 긴 시험 제목 '.repeat(20):'합성 탭 '+i,domain:'site'+i+'.example.com'}));
let response={status:'ok',windows:[{id:'w1',tabs:tabs.slice(0,50)},{id:'w2',tabs:tabs.slice(50)}]},accepted=false,delay=false,pending=[],reads=0,runs=0,unexpected=0;
await page.route('**/*',async route=>{const path=new URL(route.request().url()).pathname;
 if(path==='/api/run'){runs++;const body=route.request().postDataJSON();return route.fulfill({json:{status:accepted?'accepted':'verified',message:accepted?'활성화 미확인':'앱이 맨 앞으로 활성화된 것을 확인했습니다.',target:{bundleId:body.id==='arc'?bundle:'other.bundle',name:'Synthetic',pid:123}}});}
 if(path==='/api/arc/tabs'){assert.equal(route.request().method(),'GET');reads++;if(delay){pending.push(route);return;}return route.fulfill({json:response});}
 if(path.startsWith('/api/')){if(route.request().method()!=='GET')unexpected++;return route.fulfill({json:({'/api/state':state,'/api/apps':{apps:[]},'/api/diagnostics':{}})[path]||{}});}
 const file={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[path];if(!file)return route.fulfill({status:404,body:''});return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html',body:await readFile('web/'+file)});
});
const click=async id=>{await page.locator(`.run-button[data-id="${id}"]`).click();await page.waitForFunction(()=>!running);};
const release=async()=>{for(const route of pending.splice(0))await route.fulfill({json:response}).catch(()=>{});};
try{
 await page.goto('http://deck.test/');await page.locator('#dashboard').waitFor({state:'visible'});assert.equal(reads,0);
 accepted=true;await click('arc');assert.equal(reads,0);assert.equal(await page.locator('#arc-tabs-panel').isHidden(),true);assert.match(await page.locator('#toast').textContent(),/미확인/);
 await page.evaluate(()=>{clearTimeout(toastTimer);document.querySelector('#toast').hidden=true;});accepted=false;await click('other');assert.equal(reads,0);await click('arc');assert.equal(await page.locator('#toast').isHidden(),true);await page.waitForFunction(()=>document.querySelectorAll('.arc-tab').length===97);assert.equal(reads,1);
 assert.equal(await page.locator('#arc-tabs-list h3').count(),2);assert.equal(await page.locator('#arc-tabs-list button,#arc-tabs-list a').count(),0);
 await page.locator('#arc-tabs-search').fill('site96');assert.equal(await page.locator('.arc-tab').count(),1);await page.locator('#arc-tabs-search').fill('');
 assert.ok(await page.locator('#arc-tabs-list').evaluate(el=>el.scrollHeight>el.clientHeight));await page.locator('#arc-tabs-list').evaluate(el=>el.scrollTop=el.scrollHeight);await page.locator('#arc-tabs-list').evaluate(el=>el.scrollTop=0);
 await page.evaluate(()=>{document.querySelector('#toast').hidden=true;});await page.locator('#arc-tabs-panel').scrollIntoViewIfNeeded();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const path=`${folder}/macOS_Chromium_mobile_synthetic_Arc-97-tabs_${Date.now()}.png`;await page.screenshot({path});const bytes=await readFile(path);
 response={status:'ok',windows:[]};await page.locator('#arc-tabs-refresh').click();await page.waitForFunction(()=>!document.querySelector('#arc-tabs-refresh').disabled);assert.match(await page.locator('#arc-tabs-list').textContent(),/열린 탭이 없습니다/);
 for(const status of ['permission','timeout']){response={status,windows:[],message:'합성 '+status};await page.locator('#arc-tabs-refresh').click();await page.waitForFunction(()=>!document.querySelector('#arc-tabs-refresh').disabled);assert.equal(await page.locator('#arc-tabs-note').textContent(),'합성 '+status);}
 response={status:'ok',windows:[{id:'w',tabs}]};delay=true;
 for(const cancel of ['other','mode','disconnect','sleep']){
  await page.evaluate(()=>{powerSleeping=false;connection(true);setMode('apps');});await click('arc');await page.waitForFunction(()=>document.querySelector('#arc-tabs-note').textContent.includes('읽는 중'));
  if(cancel==='other')await click('other');else if(cancel==='mode')await page.evaluate(()=>setMode('text'));else if(cancel==='disconnect')await page.evaluate(()=>connection(false));else await page.evaluate(()=>{powerEnabled=true;lastInputAt=0;powerPointers.clear();powerKeys.clear();checkPowerSave();});
  await release();assert.equal(await page.locator('#arc-tabs-panel').isHidden(),true);assert.equal(await page.locator('.arc-tab').count(),0);
 }
 assert.equal(unexpected,0);await writeFile('artifacts/arc-tabs-ui-evidence.json',JSON.stringify({synthetic:true,physicalDevice:false,nativeExecutions:0,interceptedActivations:runs,tabReads:reads,unexpectedMutations:unexpected,checks:['bundle ID not label','accepted does not open','97 tabs grouped/search/scroll/long title','empty/permission/timeout','other app/mode/offline/sleep discard late response','no tab action controls'],screenshot:{path,sha256:createHash('sha256').update(bytes).digest('hex'),width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)}},null,2)+'\n');console.log('PASS Arc readonly mobile panel');
}finally{await browser.close();}
