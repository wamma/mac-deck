// Focused editing checks. APIs synthetic; Chromium CDP touch, WebKit DOM TouchEvents.
import assert from 'node:assert/strict';import {readFile,writeFile,mkdir} from 'node:fs/promises';import {createHash} from 'node:crypto';
const {webkit,chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');const folder=process.argv[2];await mkdir(folder,{recursive:true});const evidence=[];
for(const engine of ['webkit','chromium']){
 const browser=await(engine==='webkit'?webkit.launch():chromium.launch({...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})}));
 const context=await browser.newContext({viewport:engine==='webkit'?{width:768,height:1024}:{width:393,height:851},isMobile:true,hasTouch:true});await context.addInitScript(()=>window.setInterval=()=>0);const page=await context.newPage(),cdp=engine==='chromium'?await context.newCDPSession(page):null;
 const state={buttons:Array.from({length:12},(_,i)=>[{id:'a'+i,label:'시험 앱 '+i,kind:'app',app:'app'},...(i%3===0?[{id:'s'+i,label:'다른 모드 '+i,kind:'shortcut',key:'s',modifiers:['command']}]:[])]).flat(),preferences:{macSound:false},metrics:{},clipboard:{count:0}};
 const original=structuredClone(state.buttons),calls=[],errors=[];let failSave=false;page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{const path=new URL(route.request().url()).pathname,body=route.request().method()==='POST'?route.request().postDataJSON():null;calls.push({path,body});
  if(path==='/api/buttons'){if(failSave)return route.fulfill({status:500,json:{error:'합성 저장 실패'}});state.buttons=body.buttons;return route.fulfill({json:{ok:true}});}
  if(path==='/api/icon')return route.fulfill({status:404,body:''});
  const data={'/api/state':state,'/api/apps':{apps:[{id:'app',name:'시험 앱'}]},'/api/diagnostics':{name:'합성 대상 · 실행 없음',pid:999999,focusedWindowReadable:true},'/api/system':{}};
  if(path in data)return route.fulfill({json:data[path]});throw Error('Unexpected API '+path);
 });
 const tile=id=>page.locator(`.run-button[data-id=${id}]`),saves=()=>calls.filter(c=>c.path==='/api/buttons').length;
 async function point(id){const r=await tile(id).boundingBox();return{x:r.x+r.width/2,y:r.y+r.height/2};}
 async function touch(type,p){
  if(cdp)return cdp.send('Input.dispatchTouchEvent',{type:{start:'touchStart',move:'touchMove',end:'touchEnd',cancel:'touchCancel'}[type],touchPoints:['end','cancel'].includes(type)?[]:[{...p,id:1}]});
  await page.evaluate(({type,p})=>{if(type==='start')window.testTouchTarget=document.elementFromPoint(p.x,p.y);const target=window.testTouchTarget;const t={identifier:1,target,clientX:p.x,clientY:p.y,pageX:p.x+scrollX,pageY:p.y+scrollY};const event=new Event('touch'+type,{bubbles:true,cancelable:true});Object.defineProperties(event,{touches:{value:['end','cancel'].includes(type)?[]:[t]},changedTouches:{value:[t]}});target.dispatchEvent(event);},{type,p});
 }
 async function hold(id){const p=await point(id);await touch('start',p);await page.waitForTimeout(470);return p;}
 async function resetTop(){await page.evaluate(()=>scrollTo(0,0));}
 try{
  await page.goto((process.env.DECK_TEST_URL||'http://127.0.0.1:8765'));await page.locator('#dashboard').waitFor({state:'visible'});await page.locator('#edit').tap();await resetTop();assert.equal(await page.locator('.reorder,.drag-handle').count(),0,'Separate arrows/grip must be removed');
  await tile('a0').tap();await page.locator('#edit-dialog').waitFor({state:'visible'});await page.locator('#edit-dialog .close-dialog').tap();
  let p=await hold('a0');assert.equal(await page.locator('.dragging').count(),1);let q=await point('a2');await touch('move',q);assert.equal(await page.locator('.drop-target').count(),1);await touch('end',q);await page.waitForFunction(()=>!reorderSaving);assert.equal(saves(),1);assert.deepEqual(state.buttons.filter(b=>b.kind==='app').slice(0,3).map(b=>b.id),['a1','a2','a0']);
  assert.deepEqual(state.buttons.filter(b=>b.kind!=='app'),original.filter(b=>b.kind!=='app'));assert.deepEqual(state.buttons.map((b,i)=>b.kind!=='app'?i:null).filter(i=>i!==null),original.map((b,i)=>b.kind!=='app'?i:null).filter(i=>i!==null));
  // A compatibility click after the drag must not open the editor or execute a command.
  await tile('a0').dispatchEvent('click',{detail:1});assert.equal(await page.locator('#edit-dialog').isVisible(),false);
  await page.reload();await page.locator('#dashboard').waitFor({state:'visible'});assert.deepEqual(await page.locator('.run-button').evaluateAll(es=>es.map(e=>e.dataset.id)),state.buttons.filter(b=>b.kind==='app').map(b=>b.id));await page.locator('#edit').tap();await resetTop();
  const n=saves();p=await point('a1');await touch('start',p);await touch('move',{x:p.x,y:p.y-45});await page.waitForTimeout(470);await touch('end',{x:p.x,y:p.y-45});assert.equal(await page.locator('.dragging').count(),0);assert.equal(saves(),n);await resetTop();
  // Chromium additionally exercises its real browser pan recognizer and scroll position.
  let panScroll=null;if(cdp){const a=await point('a2'),startY=await page.evaluate(()=>scrollY);await touch('start',a);for(let i=1;i<=8;i++){await touch('move',{x:a.x,y:a.y-i*15});await page.waitForTimeout(20);}await touch('end',a);await page.waitForTimeout(250);panScroll=await page.evaluate(()=>scrollY);assert.ok(panScroll>startY,'Before hold, native touch scrolling must remain possible');await resetTop();}
  p=await hold('a1');await touch('cancel',p);assert.equal(await page.locator('.dragging,.drop-target').count(),0);assert.equal(saves(),n);
  p=await hold('a1');await page.evaluate(()=>document.querySelector('.dragging .tile').dispatchEvent(new PointerEvent('pointercancel',{bubbles:true,pointerId:1,pointerType:'touch'})));await touch('end',p);assert.equal(saves(),n);
  p=await hold('a1');await touch('move',{x:2,y:2});await touch('end',{x:2,y:2});assert.equal(saves(),n);
  p=await hold('a1');await page.locator('[data-mode=text]').dispatchEvent('click');await touch('end',p);assert.equal(await page.locator('.dragging,.drop-target').count(),0);assert.equal(saves(),n);await page.locator('[data-mode=apps]').tap();await resetTop();
  p=await hold('a1');await page.evaluate(()=>window.dispatchEvent(new Event('offline')));await touch('end',p);assert.equal(saves(),n);assert.equal(await page.locator('.dragging,.drop-target').count(),0);await page.evaluate(()=>refresh());
  failSave=true;p=await hold('a1');q=await point('a2');await touch('move',q);await touch('end',q);await page.waitForFunction(()=>!reorderSaving);assert.equal(saves(),n+1);assert.match(await page.locator('#toast').textContent(),/저장 실패/);assert.equal(state.buttons.filter(b=>b.kind==='app')[0].id,'a1');failSave=false;
  await tile('a1').focus();await page.keyboard.press('Alt+ArrowRight');await page.waitForFunction(()=>!reorderSaving);assert.equal(saves(),n+2);
  await resetTop();p=await hold('a2');q=await point('a0');await touch('move',q);const path=`${folder}/macOS_${engine}_${engine==='webkit'?'iPad-size_DOM-touch':'mobile_CDP-touch'}_long-press_${Date.now()}.png`;await page.screenshot({path,fullPage:false});await touch('cancel',q);
  const bytes=await readFile(path);assert.equal(calls.filter(c=>c.path==='/api/run').length,0);assert.deepEqual(errors,[]);evidence.push({engine,result:'PASS',touch:cdp?'Browser CDP touch including native pan':'DOM TouchEvents in WebKit; OS gesture arbitration unverified',panScroll,saveRequests:saves(),runRequests:0,checks:['short tap edit','400ms hold drag/drop','visible-only order persisted/reloaded','post-drag click blocked','pre-hold movement cancels','touchcancel/pointercancel','outside drop','mode/offline cleanup','save failure retains order','Alt+Arrow reorder'],screenshot:{path,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20),sha256:createHash('sha256').update(bytes).digest('hex')}});
 }finally{await browser.close();}
}
await writeFile('artifacts/long-press-evidence.json',JSON.stringify({userReportedGalaxyConnection:true,independentPhysicalGalaxyTest:false,results:evidence},null,2)+'\n');console.log(JSON.stringify(evidence));
