// Synthetic activity metadata, actual Chromium mobile layout; no native/API mutations.
import assert from 'node:assert/strict';import {mkdir,readFile,writeFile} from 'node:fs/promises';import {createHash} from 'node:crypto';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const folder=process.argv[2];await mkdir(folder,{recursive:true});
const browser=await chromium.launch({...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
const page=await browser.newPage({viewport:{width:393,height:851},isMobile:true,hasTouch:true});
await page.addInitScript(()=>{localStorage.setItem('deck-mode','ai');localStorage.setItem('deck-power-save','false');window.setInterval=()=>0;});
const row=(id,title,time,state='working')=>({id,taskName:title,project:'시험 프로젝트',provider:'codex',lastActivityAt:time,state,readOnly:true});
const a=row('orca:synthetic-a','장바구니 오류 수정',1794747000),b=row('orca:synthetic-b','새 화면 접근성 점검',1794746900,'input-required');
const state={buttons:[],preferences:{macSound:false},metrics:{},clipboard:{count:0,enabled:false},ai:{slots:Array.from({length:12},(_,slot)=>({slot,state:'unregistered'})),sources:[],activity:{rows:[a,b],status:'ok',total:2}}};
let posts=0,offline=false,details=0;const screenshots=[];
await page.route('**/api/**',route=>{const request=route.request();if(request.method()!=='GET'){posts++;return route.fulfill({status:500,json:{error:'mutations forbidden'}});}const path=new URL(request.url()).pathname;if(path.includes('/ai/detail')||path.includes('/ai/reply'))details++;
 if(offline)return route.abort();const values={'/api/state':state,'/api/apps':{apps:[]},'/api/diagnostics':{}};assert.ok(path in values);return route.fulfill({json:values[path]});});
async function capture(label){const path=`${folder}/macOS_Chromium_mobile_synthetic_${label}_${Date.now()}.png`;await page.screenshot({path});const bytes=await readFile(path);screenshots.push({path,sha256:createHash('sha256').update(bytes).digest('hex'),width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)});}
try{
 await page.goto((process.env.DECK_TEST_URL||'http://127.0.0.1:8765'));await page.locator('#dashboard').waitFor({state:'visible'});
 assert.equal(await page.locator('#slots .slot').count(),2);assert.equal(await page.locator('#slots .slot').first().getAttribute('data-activity-id'),a.id);
 await page.locator('#slots').scrollIntoViewIfNeeded();await capture('recent-active');
 await page.locator(`[data-activity-id="${a.id}"]`).click();assert.equal(await page.locator('#activity-title').textContent(),a.taskName);
 state.ai.activity.rows=[b,a];await page.evaluate(()=>refresh());assert.equal(await page.locator('#activity-dialog').getAttribute('data-source-id'),a.id);assert.equal(await page.locator('#activity-title').textContent(),a.taskName);
 state.ai.activity.rows=[b];await page.evaluate(()=>refresh());assert.match(await page.locator('#activity-status').textContent(),/목록에 없음/);assert.equal(await page.locator('#activity-title').textContent(),a.taskName);
 offline=true;await page.evaluate(()=>refresh());assert.match(await page.locator('#activity-status').textContent(),/연결 끊김/);assert.equal(await page.locator('#slots .slot').getAttribute('data-state'),'disconnected');
 offline=false;state.ai.activity.rows=[a,b];await page.evaluate(()=>refresh());assert.equal(await page.locator('#activity-title').textContent(),a.taskName);await capture('readonly-exact-identity');
 await page.locator('#activity-dialog .close-dialog').click();state.ai.activity={rows:[],status:'no_signal',total:0};await page.evaluate(()=>refresh());assert.equal(await page.locator('#slots .slot').count(),0);assert.match(await page.locator('.activity-empty').textContent(),/완료 상태를 뜻하지/);
 state.ai.activity={rows:[],status:'ok',total:0};await page.evaluate(()=>refresh());assert.match(await page.locator('.activity-empty').textContent(),/작업이 없습니다/);
 await page.locator('#manual-ai summary').click();await page.locator('#manual-ai-slot').selectOption('3');await page.locator('#manual-ai-open').click();assert.match(await page.locator('#ai-title').textContent(),/AI 04/);
 assert.equal(posts,0);assert.equal(details,0);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await writeFile('artifacts/orca-activity-ui-evidence.json',JSON.stringify({synthetic:true,physicalDevice:false,posts,detailAndReplyRequests:details,checks:['under 12 without placeholders','exact identity across reorder/removal','offline and reconnect','empty versus no signal','manual settings retained','no horizontal overflow'],screenshots},null,2)+'\n');console.log('PASS mobile activity identity/offline/no mutations');
}finally{await browser.close();}
