// Actual browser, synthetic API only: no native app activation.
import assert from 'node:assert/strict';import {readFile,mkdir,writeFile} from 'node:fs/promises';import {createHash} from 'node:crypto';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');const folder=process.argv[2];await mkdir(folder,{recursive:true});
const browser=await chromium.launch({...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});const page=await browser.newPage({viewport:{width:393,height:851},isMobile:true,hasTouch:true});
await page.addInitScript(()=>{localStorage.setItem('deck-mode','apps');localStorage.setItem('deck-power-save','false');window.setInterval=()=>0;});
const app={id:'test-app',kind:'app',app:'test-app',label:'시험 앱'},text={id:'test-text',kind:'text',text:'synthetic',enter:false,label:'시험 문구'};
const state={buttons:[app,text],preferences:{macSound:false},metrics:{},clipboard:{count:0,enabled:false},ai:{slots:[],sources:[]}};
let result={status:'verified',message:'앱이 맨 앞으로 활성화된 것을 확인했습니다.'},httpStatus=200,runs=0;
await page.route('**/*',async route=>{const path=new URL(route.request().url()).pathname;
 if(path==='/api/run'){runs++;return route.fulfill({status:httpStatus,json:result});}
 if(path.startsWith('/api/')){assert.equal(route.request().method(),'GET');return route.fulfill({json:({'/api/state':state,'/api/apps':{apps:[]},'/api/diagnostics':{}})[path]||{}});}
 const file={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[path];if(!file)return route.fulfill({status:404,body:''});
 return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html',body:await readFile('web/'+file)});
});
try{
 await page.goto('http://deck.test/');await page.locator('#dashboard').waitFor({state:'visible'});
 await page.locator('.run-button[data-id="test-app"]').click();await page.waitForFunction(()=>!running);assert.equal(runs,1);assert.equal(await page.locator('#toast').isHidden(),true);
 const path=`${folder}/macOS_Chromium_mobile_synthetic_app-verified-no-toast_${Date.now()}.png`;await page.screenshot({path});const bytes=await readFile(path);
 result={status:'accepted',message:'앱 실행은 접수됐지만 맨 앞 활성화는 확인하지 못했습니다.'};await page.locator('.run-button[data-id="test-app"]').click();await page.waitForFunction(()=>!running);assert.match(await page.locator('#toast').textContent(),/활성화는 확인하지 못했습니다/);
 httpStatus=503;result={error:'자동화 권한을 확인하세요.'};await page.locator('.run-button[data-id="test-app"]').click();await page.waitForFunction(()=>!running);assert.equal(await page.locator('#toast').textContent(),'자동화 권한을 확인하세요.');
 httpStatus=200;result={status:'verified',message:'시험 문구 확인 완료'};await page.evaluate(()=>setMode('text'));await page.locator('.run-button[data-id="test-text"]').click();await page.waitForFunction(()=>!running);assert.match(await page.locator('#toast').textContent(),/시험 문구 확인 완료/);assert.equal(runs,4);
 await writeFile('artifacts/app-success-toast-evidence.json',JSON.stringify({synthetic:true,physicalDevice:false,nativeExecutions:0,interceptedRunRequests:runs,checks:['app verified toast hidden','app accepted guidance retained','failure permission guidance retained','non-app verified guidance retained'],screenshot:{path,sha256:createHash('sha256').update(bytes).digest('hex'),width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)}},null,2)+'\n');console.log('PASS app success toast only');
}finally{await browser.close();}
