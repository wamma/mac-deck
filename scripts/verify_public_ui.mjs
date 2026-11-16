// Release UI smoke: every request is intercepted; never contacts a Mac server.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {basename} from 'node:path';
import {createHash} from 'node:crypto';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const folder=process.argv[2]||'artifacts/public-ui';await mkdir(folder,{recursive:true});await mkdir('artifacts',{recursive:true});
const browser=await chromium.launch(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{});
const screenshots=[];let commands=0;
try {
 for(const scheme of ['https','http']) {
  const context=await browser.newContext({viewport:{width:393,height:851},isMobile:true,hasTouch:true});const page=await context.newPage();let paired=false;let submitted;
  await page.addInitScript(()=>{localStorage.setItem('deck-power-save','false');window.setInterval=()=>0;});
  const state={buttons:[{id:'demo-app',kind:'app',app:'demo-app',label:'예시 앱'},{id:'demo-text',kind:'text',text:'Example',enter:false,label:'예시 문구'}],preferences:{macSound:false},metrics:{},clipboard:{count:0,enabled:false},ai:{slots:[],sources:[]},activity:{status:'ok',rows:[]}};
  await page.route('**/*',async route=>{
   const request=route.request(),path=new URL(request.url()).pathname;
   if(path==='/api/pair'){submitted=request.postDataJSON();paired=true;return route.fulfill({json:{ok:true}});}
   if(path.startsWith('/api/')){
    if(request.method()!=='GET'){commands++;return route.fulfill({status:500,json:{error:'Unexpected command in read-only smoke'}});}
    if(!paired)return route.fulfill({status:401,json:{error:'Pair first'}});
    const data={'/api/state':state,'/api/apps':{apps:[]},'/api/diagnostics':{},'/api/system':{}}[path]||{};
    return route.fulfill({json:data});
   }
   const file={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[path];
   if(!file)return route.fulfill({status:404,body:''});
   return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html',body:await readFile('web/'+file)});
  });
  await page.goto(scheme+'://deck.test/');await page.locator('#pair-screen').waitFor({state:'visible'});
  assert.match(await page.locator('#transport-note').textContent(),scheme==='https'?/HTTPS/:/HTTP/);
  assert.match(await page.locator('#pair-form').textContent(),/120초/);assert.match(await page.locator('#pair-form').textContent(),/취소하지 않습니다/);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  const path=`${folder}/Chromium_mobile_synthetic_${scheme}_pairing_${Date.now()}.png`;await page.screenshot({path,fullPage:true});
  const bytes=await readFile(path);screenshots.push({file:basename(path),sha256:createHash('sha256').update(bytes).digest('hex'),width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)});
  await page.locator('#device-name').fill('Fixture phone');await page.locator('#pair-code').fill('fixture-only');await page.locator('#pair-form button[type=submit]').click();await page.locator('#dashboard').waitFor({state:'visible'});
  assert.equal(submitted.deviceName,'Fixture phone');assert.equal(submitted.code,'fixture-only');
  for(const mode of ['apps','system','ai','text']){await page.locator(`[data-mode="${mode}"]`).click();assert.equal(await page.locator(`[data-mode="${mode}"]`).getAttribute('aria-selected'),'true');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);}
  await context.close();
 }
 assert.equal(commands,0);await writeFile('artifacts/public-ui.json',JSON.stringify({synthetic:true,physicalDevice:false,networkRequestsToServer:0,nativeCommands:commands,checks:['pairing instructions','transport notices','device name','four modes without execution','393px overflow'],screenshots},null,2)+'\n');console.log('PASS public mobile synthetic UI; commands 0');
}finally{await browser.close();}
