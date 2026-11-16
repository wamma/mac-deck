'use strict';
const $ = s => document.querySelector(s);
const icons = {
  speaker:'<path d="M3 9h4l5-4v14l-5-4H3zM16 8c3 2 3 6 0 8m3-11c5 4 5 10 0 14"/>',
  bell:'<path d="M5 17h14l-2-4V9a5 5 0 0 0-10 0v4zM10 21h4"/>',
  monitor:'<rect x="3" y="3" width="18" height="13" rx="2"/><path d="M12 16v5m-4 0h8"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  cpu:'<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3"/>',
  ram:'<rect x="3" y="7" width="18" height="10" rx="2"/><path d="M6 10h1m3 0h1m3 0h1m3 0h1M6 13h1m3 0h1m3 0h1m3 0h1M6 17v3m4-3v3m4-3v3m4-3v3"/>',
  battery:'<path d="M7 7H4v10h3m10-10h3v10h-3m5-7v4M13 4l-4 9h5l-3 7"/>',
  clipboard:'<rect x="5" y="5" width="14" height="16" rx="2"/><rect x="9" y="2" width="6" height="5" rx="1"/><path d="M9 12h6m-6 4h6"/>',
  copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V3H3v13h5"/>',
  capture:'<path d="M8 3H4v4m12-4h4v4M4 17v4h4m12-4v4h-4"/>',
  select:'<path d="M4 8V4h4m8 0h4v4M4 16v4h4m12-4v4h-4M11 4h2M4 11v2m16-2v2m-9 7h2"/><path d="m9 9 8 4-4 1-1 4z"/>',
  undo:'<path d="M4 5v6h6M4 11c3-8 16-6 16 2 0 5-7 8-11 4"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  save:'<path d="M4 3h13l4 4v14H3V3zm3 0v6h9V3M7 21v-8h10v8"/>',
  switch:'<path d="M5 6h15m-4-4 4 4-4 4M19 18H4m4-4-4 4 4 4"/>',
  brain:'<path d="M12 5c-3-5-8-1-6 2-5 1-4 7-1 8-2 5 4 8 7 4m0-14c3-5 8-1 6 2 5 1 4 7 1 8 2 5-4 8-7 4zm-6 2 2 2m11 6-3-1M5 15l3-1"/>',
  keyboard:'<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M5 9h1m3 0h1m3 0h1m3 0h1M5 12h1m3 0h1m3 0h1m3 0h1M7 16h10"/>',
  app:'<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M3 9h18M8 9v12"/>',
  edit:'<path d="m14 4 6 6M4 20l5-1L21 7l-4-4L5 15z"/>',
  moon:'<path d="M20 15a9 9 0 0 1-11-11A9 9 0 1 0 20 15Z"/>',
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
  plus:'<path d="M12 4v16M4 12h16"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
  disconnect:'<path d="M12 3v9m-5-7a9 9 0 1 0 10 0"/>'
};
function icon(name) { const box=document.createElement('span'); box.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]||icons.keyboard}</svg>`; return box.firstChild; }
document.querySelectorAll('[data-icon]').forEach(el=>el.replaceChildren(icon(el.dataset.icon)));
for(let i=1;i<=12;i++)$('#manual-ai-slot').append(new Option('AI '+String(i).padStart(2,'0'),String(i-1)));
$('#manual-ai-open').onclick=()=>openAI(Number($('#manual-ai-slot').value));
let selectedActivityId=null,selectedActivitySnapshot=null;
let arcGeneration=0,arcController=null,arcWindows=[];
const symbols={command:'⌘',option:'⌥',control:'⌃',shift:'⇧',enter:'↵',tab:'⇥',space:'Space',escape:'Esc',backspace:'⌫',delete:'⌦',up:'↑',down:'↓',left:'←',right:'→'};
let aiState={slots:[],sources:[]},selectedSlot=0,aiProof=null,notificationBaseline=true,notificationEpoch=null,connectionGeneration=0,aiGeneration=0,aiSnapshotAt=null,aiCaptureAt=null;
const seenTransitions=new Set();
let mode='apps', systemState=null, pendingApp=null, activeActionId=null, targetGeneration=0, renderGeneration=0;
try{const saved=localStorage.getItem('deck-mode');if(['apps','system','ai','text'].includes(saved))mode=saved;}catch{}
let buttons=[], apps=[], clipboard={enabled:false,items:[]}, editing=false, editId=null, connected=false, running=false, configSignature='', clipSignature='', toastTimer, refreshBusy=false;
let powerSleeping=false,powerEnabled=true,powerTimer,lastInputAt=Date.now(),powerComposing=false,powerCompositionTarget=null,powerWakeClickUntil=0;
const powerPointers=new Set(),powerKeys=new Set(),wakePointers=new Set(),wakeKeys=new Set();
function keyLabel(b){return b.modifiers.map(m=>symbols[m]).join('')+(symbols[b.key]||b.key.toUpperCase());}
function uid(){return Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join('');}
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6500);}
function connection(ok){const wasConnected=connected;connected=ok;if(ok&&!wasConnected)invalidateAIDetail('연결 복구 · 응답하려면 새 상세를 확인하세요.');if(!ok){closeArcTabs();cancelTileDrag();connectionGeneration++;invalidateAIDetail('연결 끊김 · 새 상세 확인 전에는 응답할 수 없습니다.');renderAISlots();notificationBaseline=true;pendingApp=null;targetGeneration++;confirmations.clear();$('#target-status').textContent='연결 끊김 · 활성 앱 확인 불가';$('#volume-note').textContent='연결 끊김 · 마지막 확인값';$('#brightness-note').textContent='연결 끊김 · 상태 다시 확인 필요';}$('#connection').classList.toggle('offline',!ok);$('#connection span').textContent=ok?'맥 연결됨':'연결 끊김 · 다시 확인 중';syncActionButtons();if(!ok)document.querySelectorAll('.system-action,#volume-slider,#brightness-slider').forEach(el=>el.disabled=true);}
function syncActionButtons(){document.querySelectorAll('.run-button').forEach(tile=>{const busy=running&&tile.dataset.id===activeActionId;tile.disabled=!editing&&(!connected||busy);tile.setAttribute('aria-busy',String(busy));});}
async function api(path,body){
  let response;
  try { response=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(12000)}); }
  catch {connection(false);throw Error('맥과 연결되지 않습니다. 서버와 Wi-Fi를 확인하세요. 실행 요청은 자동으로 재전송하지 않습니다.');}
  const data=await response.json();
  if(response.status===401&&path!='/api/pair'&&!powerSleeping) showPair();
  if(!response.ok) throw Error(data.error||'요청을 처리하지 못했습니다.');
  return data;
}
function showPair(){document.querySelectorAll('dialog[open]').forEach(d=>d.close());$('#dashboard').hidden=true;$('#pair-screen').hidden=false;connection(false);}
function showDashboard(){$('#pair-screen').hidden=true;$('#dashboard').hidden=false;connection(true);}
async function refresh(){
  if(refreshBusy||powerSleeping||document.hidden)return;refreshBusy=true;const generation=connectionGeneration;
  try{
    const state=await api('/api/state');if(generation!==connectionGeneration)return;
    if(!apps.length){apps=(await api('/api/apps')).apps;}
    if(generation!==connectionGeneration)return;showDashboard();
    const signature=JSON.stringify(state.buttons);
    if(signature!==configSignature){buttons=state.buttons;configSignature=signature;renderButtons();}
    updateMetrics(state);updateIntegrations(state);applyMode();await refreshTarget();if(mode==='system')await refreshSystem();$('#warning').hidden=!state.warning;$('#warning').textContent=state.warning||'';
    if($('#clipboard-dialog').open)await refreshClipboard();
  }catch(error){if(!$('#dashboard').hidden)connection(false);}
  finally{refreshBusy=false;}
}
function updateMetrics(state){
  const m=state.metrics;
  for(const key of ['cpu','ram','battery']){const value=m[key];$('#'+key).textContent=value??'—';$('#'+key+'-bar').value=value??0;}
  $('#charging').textContent=m.battery==null?'배터리 없음':m.charging?'전원 연결':'배터리 사용';
  $('#memory-total').textContent=m.memory_total?`${m.memory_total} GB`:'';
  $('#clip-count').textContent=state.clipboard.count;
  $('#mac-sound').setAttribute('aria-pressed',!!state.preferences?.macSound);
}
function renderButtons(){
  cancelTileDrag();
  renderGeneration++;confirmations.clear();
  $('#buttons').replaceChildren();$('#capture-slot').replaceChildren();$('#paste-slot').replaceChildren();
  // Preserve the source panel's prominent capture / clipboard / paste row.
  const visible=buttons.filter(b=>buttonMode(b)===mode);
  $('#mode-empty').hidden=visible.length>0||mode==='ai';$('#mode-empty').textContent=mode==='apps'?'아직 등록한 앱이 없습니다. 편집에서 앱을 추가하세요.':mode==='text'?'자주 쓰는 문구와 사이트를 버튼으로 추가하세요.':'시스템 단축키를 추가할 수 있습니다.';
  for(const b of visible){const index=buttons.findIndex(item=>item.id===b.id);
    const wrap=document.createElement('div');wrap.className='tile-wrap';wrap.dataset.id=b.id;
    const tile=document.createElement('button');tile.className='tile run-button';tile.dataset.id=b.id;tile.disabled=!connected&&!editing;tile.title=b.kind==='shortcut'?`${b.label} · ${keyLabel(b)}`:b.label;
    const image=document.createElement('span');image.className='tile-icon';
    if(b.kind==='app'){
      const img=document.createElement('img');img.alt='';img.src='/api/icon?id='+encodeURIComponent(b.app);img.addEventListener('error',()=>image.replaceChildren(icon('app')),{once:true});image.append(img);
    }else image.append(icon(b.kind==='trash'?'trash':icons[b.id]?b.id:'keyboard'));
    const corner=document.createElement('span');corner.className='tile-corner';corner.textContent=b.kind==='shortcut'?keyLabel(b):b.kind==='text'?(b.enter?'Text ↵':'Text'):b.kind==='trash'?'2× · 3s':'↗';
    const label=document.createElement('span');label.className='tile-label';label.textContent=b.label;
    tile.append(image,corner,label);tile.onclick=()=>editing?(reorderSaving?toast('순서를 저장 중입니다. 잠시 기다려 주세요.'):openEditor(b)):execute(b,tile);wrap.append(tile);
    if(editing){
      tile.setAttribute('aria-keyshortcuts','Alt+ArrowLeft Alt+ArrowRight');
      tile.title=b.label+' · 길게 눌러 이동 · Alt+방향키로 순서 이동';
      tile.oncontextmenu=event=>event.preventDefault();
      tile.addEventListener('touchstart',event=>{if(event.touches.length===1)beginTileDrag(event.touches[0],tile,wrap,'touch');else cancelTileDrag();},{passive:true});
      tile.onpointerdown=event=>{if(event.pointerType!=='touch'&&event.button===0)beginTileDrag(event,tile,wrap,event.pointerId);};
      tile.onkeydown=event=>{if(event.altKey&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();moveVisibleButton(b.id,['ArrowLeft','ArrowUp'].includes(event.key)?-1:1);}};
    }
    const fixed=mode==='system'&&index<2;
    (fixed?$(index===0?'#capture-slot':'#paste-slot'):$('#buttons')).append(wrap);
  }
  // The first two configured buttons occupy the two prominent slots in saved order.
  for(const selector of ['#capture-slot','#paste-slot'])$(selector).hidden=!$(selector).children.length;
  if(mode!=='ai'&&(editing||!visible.length)){const add=document.createElement('button');add.className='tile add-tile';const label=document.createElement('span');label.className='tile-label';label.textContent='버튼 추가';add.append(icon('plus'),label);add.onclick=()=>openEditor();$('#buttons').append(add);}
  syncActionButtons();
}
const confirmations=new Map();
async function execute(b,tile){
  if(!connected)return;
  if(b.kind==='app')closeArcTabs();
  if(running){if(b.kind==='app'&&b.id!==activeActionId){targetGeneration++;pendingApp={b,tile};$('#target-status').textContent=b.label+' 전환 대기…';}else toast('현재 명령을 확인 중입니다. 완료 후 다시 눌러주세요.');return;}
  running=true;activeActionId=b.id;const generation=++targetGeneration,renderVersion=renderGeneration;syncActionButtons();
  if(b.kind==='app')$('#target-status').textContent=b.label+' 전면 전환 확인 중…';
  else toast(b.label+' · 명령을 확인 중입니다.');
  const armed=confirmations.get(b.id);confirmations.delete(b.id);
  if(armed){tile.classList.remove('confirm-trash');tile.querySelector('.tile-label').textContent=b.label;}
  try{
    const result=await api('/api/run',{id:b.id,requestId:uid(),...(armed?{confirmationId:armed.id}:{})});
    if(result.confirmationRequired&&(!tile.isConnected||renderVersion!==renderGeneration||generation!==targetGeneration||!connected))return;
    if(connected&&!pendingApp&&generation===targetGeneration&&renderVersion===renderGeneration&&!(b.kind==='app'&&result.status==='verified'))toast(b.label+' · '+result.message);
    if(b.kind==='app'&&result.status==='verified'&&result.target?.bundleId==='company.thebrowser.Browser'&&connected&&!pendingApp&&generation===targetGeneration&&renderVersion===renderGeneration&&mode==='apps'&&!powerSleeping)openArcTabs();
    if(result.target&&connected&&!pendingApp&&generation===targetGeneration&&renderVersion===renderGeneration)updateTarget(result.target);
    if(result.confirmationRequired){
      const value={id:result.confirmationId};confirmations.set(b.id,value);tile.classList.add('confirm-trash');
      tile.querySelector('.tile-label').textContent='다시 누르면 비우기 · 3초';
      setTimeout(()=>{if(confirmations.get(b.id)!==value)return;confirmations.delete(b.id);toast('휴지통 확인 시간이 만료되었습니다.');tile.classList.remove('confirm-trash');tile.querySelector('.tile-label').textContent=b.label;},result.expiresIn*1000);
    }
  }catch(error){if(connected&&!pendingApp&&generation===targetGeneration&&renderVersion===renderGeneration)toast(error.message);}
  finally{
    running=false;activeActionId=null;syncActionButtons();
    const next=pendingApp;pendingApp=null;const queued=next&&buttons.find(button=>button.id===next.b.id&&button.kind==='app');
    if(queued&&connected)execute(queued,document.querySelector(`.run-button[data-id="${queued.id}"]`)||next.tile);else refreshTarget();
  }
}
let tileDrag=null,reorderSaving=false,suppressTileClickUntil=0;
function cancelTileDrag(){
  if(!tileDrag)return;
  clearTimeout(tileDrag.timer);if(tileDrag.active)suppressTileClickUntil=performance.now()+700;
  tileDrag.tile.removeAttribute('aria-grabbed');tileDrag.wrap.classList.remove('dragging');
  document.querySelectorAll('.drop-target').forEach(el=>el.classList.remove('drop-target'));tileDrag=null;
}
function beginTileDrag(point,tile,wrap,pointer){
  cancelTileDrag();if(!editing||!connected||reorderSaving)return;
  suppressTileClickUntil=0;
  const drag={tile,wrap,pointer,x:point.clientX,y:point.clientY,mode,active:false,target:null};tileDrag=drag;
  drag.timer=setTimeout(()=>{if(tileDrag!==drag||!tile.isConnected||!editing||!connected)return;drag.active=true;wrap.classList.add('dragging');tile.setAttribute('aria-grabbed','true');toast('이동할 버튼 위에 놓으세요.');},400);
}
function moveTileDrag(point,event){
  const drag=tileDrag;if(!drag)return;
  if(!drag.active){if(Math.hypot(point.clientX-drag.x,point.clientY-drag.y)>8){suppressTileClickUntil=performance.now()+700;cancelTileDrag();}return;}
  // Registered non-passive before the gesture: cancel the first move after holding.
  // Pre-hold motion is never prevented, so the browser can take over scrolling.
  if(event.cancelable)event.preventDefault();else {cancelTileDrag();return;}
  const target=document.elementFromPoint(point.clientX,point.clientY)?.closest('.tile-wrap');
  document.querySelectorAll('.drop-target').forEach(el=>el.classList.remove('drop-target'));
  drag.target=target&&target!==drag.wrap&&buttons.some(b=>b.id===target.dataset.id&&buttonMode(b)===drag.mode)?target.dataset.id:null;
  if(drag.target)target.classList.add('drop-target');
  if(point.clientY>innerHeight-45)window.scrollBy(0,12);else if(point.clientY<45)window.scrollBy(0,-12);
}
function finishTileDrag(point,event){
  const drag=tileDrag;if(!drag)return;
  if(drag.active){moveTileDrag(point,event);if(event.cancelable)event.preventDefault();}
  const target=tileDrag?.target,active=drag.active;cancelTileDrag();
  if(active&&target&&editing&&connected&&mode===drag.mode)reorderVisible(drag.wrap.dataset.id,target,drag.mode);
}
// Touch scrolling remains enabled from touchstart. Only an activated hold cancels touchmove.
document.addEventListener('touchmove',event=>{if(tileDrag?.pointer==='touch'){if(event.touches.length!==1)cancelTileDrag();else moveTileDrag(event.touches[0],event);}},{passive:false});
document.addEventListener('touchend',event=>{if(tileDrag?.pointer==='touch'&&event.changedTouches[0])finishTileDrag(event.changedTouches[0],event);},{passive:false});
document.addEventListener('touchcancel',cancelTileDrag);
document.addEventListener('pointermove',event=>{if(tileDrag&&tileDrag.pointer===event.pointerId)moveTileDrag(event,event);});
document.addEventListener('pointerup',event=>{if(tileDrag&&tileDrag.pointer===event.pointerId)finishTileDrag(event,event);});
document.addEventListener('pointercancel',cancelTileDrag);
document.addEventListener('pointerdown',()=>{if(!tileDrag)suppressTileClickUntil=0;},true);
document.addEventListener('click',event=>{if(event.detail!==0&&performance.now()<suppressTileClickUntil){event.preventDefault();event.stopImmediatePropagation();}},true);
document.addEventListener('scroll',()=>{if(tileDrag&&!tileDrag.active)cancelTileDrag();},true);
document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelTileDrag();});window.addEventListener('blur',cancelTileDrag);
async function reorderVisible(id,target,selectedMode){
  if(reorderSaving||!editing||!connected)return;
  const visible=buttons.filter(b=>buttonMode(b)===selectedMode),from=visible.findIndex(b=>b.id===id),to=visible.findIndex(b=>b.id===target);
  if(from<0||to<0||from===to)return;
  visible.splice(to,0,visible.splice(from,1)[0]);let index=0;
  const next=buttons.map(b=>buttonMode(b)===selectedMode?visible[index++]:b);reorderSaving=true;
  try{await saveButtons(next);toast('버튼 순서를 저장했습니다.');}
  catch(error){toast('순서 저장 실패 · '+error.message);}
  finally{reorderSaving=false;}
}
async function saveButtons(next){await api('/api/buttons',{buttons:next});buttons=next;configSignature=JSON.stringify(next);renderButtons();}
async function moveButton(index,offset){const next=buttons.slice();[next[index],next[index+offset]]=[next[index+offset],next[index]];try{await saveButtons(next);}catch(error){toast(error.message);}}
function openEditor(button){
  editId=button?.id||null;$('#editor-title').textContent=button?'버튼 편집':'버튼 추가';$('#button-label').value=button?.label||'';$('#button-kind').value=button?.kind||(mode==='apps'?'app':mode==='text'?'text':'shortcut');
  const select=$('#button-app');select.replaceChildren();
  for(const app of apps){const option=document.createElement('option');option.value=app.id;option.textContent=app.name;select.append(option);}
  if(button?.kind==='app'){
    if(!apps.some(a=>a.id===button.app)){const option=document.createElement('option');option.value=button.app;option.textContent='설치되지 않은 앱';select.append(option);}
    select.value=button.app;
  }
  $('#button-key').value=button?.key||'c';$('#button-text').value=button?.text||'';$('#button-enter').checked=button?.enter||false;$('#button-urls').value=(button?.urls||[]).join('\n');
  document.querySelectorAll('.modifier-options input').forEach(input=>input.checked=(button?.modifiers||['command']).includes(input.value));
  $('#delete-button').hidden=!button;$('#editor-error').textContent='';toggleFields();$('#edit-dialog').showModal();
}
function toggleFields(){const kind=$('#button-kind').value;for(const name of ['app','shortcut','text','urls','trash'])$('#'+name+'-fields').hidden=name!==kind;$('#button-app').disabled=kind!=='app';}
$('#button-kind').onchange=toggleFields;
for(const key of [...'abcdefghijklmnopqrstuvwxyz0123456789','enter','space','tab','escape','backspace','delete','up','down','left','right','home','end','pageup','pagedown',...Array.from({length:12},(_,i)=>'f'+(i+1))]){const option=document.createElement('option');option.value=key;option.textContent=symbols[key]||key.toUpperCase();$('#button-key').append(option);}
$('#button-form').onsubmit=async event=>{
  event.preventDefault();const submit=event.submitter;submit.disabled=true;
  const b={id:editId||uid(),label:$('#button-label').value.trim(),kind:$('#button-kind').value};
  if(b.kind==='app')b.app=$('#button-app').value;
  else if(b.kind==='text'){b.text=$('#button-text').value;b.enter=$('#button-enter').checked;}
  else if(b.kind==='urls')b.urls=$('#button-urls').value.split('\n').map(s=>s.trim()).filter(Boolean);
  else if(b.kind==='shortcut'){b.key=$('#button-key').value;b.modifiers=[...document.querySelectorAll('.modifier-options input:checked')].map(i=>i.value);}
  const next=editId?buttons.map(item=>item.id===editId?b:item):[...buttons,b];
  try{await saveButtons(next);$('#edit-dialog').close();setMode(buttonMode(b));toast('버튼을 저장했습니다.');}catch(error){$('#editor-error').textContent=error.message;}finally{submit.disabled=false;}
};
$('#delete-button').onclick=async()=>{try{await saveButtons(buttons.filter(b=>b.id!==editId));$('#edit-dialog').close();toast('버튼을 삭제했습니다.');}catch(error){$('#editor-error').textContent=error.message;}};
$('#edit').onclick=()=>{editing=!editing;$('#edit').setAttribute('aria-pressed',editing);$('#edit>span:last-child').textContent=editing?'완료':'편집';$('#dashboard').classList.toggle('editing',editing);$('#footer-help').textContent=editing?'짧게 눌러 편집 · 길게 눌러 이동 · 키보드 Alt+방향키':'같은 Wi-Fi · 단축키는 맥의 현재 활성 앱에 전달됩니다';renderButtons();};
function renderClipboard(){
  const list=$('#clipboard-items');list.replaceChildren();const query=$('#clip-search').value.toLocaleLowerCase();const items=clipboard.items.filter(i=>i.text.toLocaleLowerCase().includes(query));
  $('#drawer-count').textContent=clipboard.items.length;$('#toggle-collection').textContent=clipboard.enabled?'수집 일시정지':'수집 시작';$('#clear-clipboard').disabled=!clipboard.items.length;
  $('#clip-note').textContent=clipboard.error||'수집을 켠 이후의 텍스트만 기록합니다. 서버 종료 시 기록이 지워집니다.';
  if(!items.length){const empty=document.createElement('div');empty.className='empty';const text=document.createElement('div');text.textContent=query?'검색 결과가 없습니다.':clipboard.enabled?'새로 복사한 텍스트가 여기에 쌓입니다.':'아직 기록이 없습니다. 수집 시작을 누른 뒤 맥에서 텍스트를 복사해 보세요.';empty.append(icon('clipboard'),text);list.append(empty);}
  for(const item of items){
    const row=document.createElement('article');row.className='clip-item';const copy=document.createElement('button');copy.className='clip-copy';copy.title='맥 클립보드에 다시 복사';
    const text=document.createElement('pre');text.textContent=item.text;const date=document.createElement('small');date.textContent=new Date(item.time*1000).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'})+' · '+item.text.length.toLocaleString()+'자';copy.append(text,date);
    copy.onclick=async()=>{try{await api('/api/clipboard',{action:'copy',id:item.id});toast('맥 클립보드에 복사했습니다.');}catch(error){toast(error.message);}};
    const remove=document.createElement('button');remove.className='icon-button';remove.setAttribute('aria-label','클립보드 항목 삭제');remove.append(icon('trash'));remove.onclick=()=>clipboardAction({action:'delete',id:item.id});row.append(copy,remove);list.append(row);
  }
}
async function refreshClipboard(){if(powerSleeping)return;const generation=connectionGeneration,data=await api('/api/clipboard');if(powerSleeping||generation!==connectionGeneration)return;const signature=JSON.stringify(data);clipboard=data;if(signature!==clipSignature){clipSignature=signature;renderClipboard();}}
async function openClipboard(){try{await refreshClipboard();renderClipboard();$('#clipboard-dialog').showModal();}catch(error){toast(error.message);}}
async function clipboardAction(body){try{await api('/api/clipboard',body);await refreshClipboard();await refresh();}catch(error){toast(error.message);}}
$('#open-clipboard').onclick=openClipboard;$('#clip-search').oninput=renderClipboard;
$('#toggle-collection').onclick=()=>clipboardAction({action:'enabled',enabled:!clipboard.enabled});
$('#clear-clipboard').onclick=()=>{if(confirm('클립보드 기록을 모두 삭제할까요? 맥의 현재 클립보드는 유지됩니다.'))clipboardAction({action:'clear'});};
$('#pair-form').onsubmit=async event=>{event.preventDefault();const submit=event.submitter;submit.disabled=true;$('#pair-error').textContent='';try{await api('/api/pair',{code:$('#pair-code').value.trim(),deviceName:$('#device-name').value.trim()||'Browser'});$('#pair-code').value='';configSignature='';await refresh();}catch(error){$('#pair-error').textContent=error.message;}finally{submit.disabled=false;}};
function setTheme(dark){document.body.classList.toggle('dark',dark);$('#theme').replaceChildren(icon(dark?'sun':'moon'));$('#theme').setAttribute('aria-label',dark?'라이트 모드로 전환':'다크 모드로 전환');document.querySelector('meta[name=theme-color]').content=dark?'#10110f':'#eeede8';try{localStorage.setItem('deck-theme',dark?'dark':'light');}catch{}}
try{setTheme(localStorage.getItem('deck-theme')==='dark');}catch{setTheme(false);}
$('#theme').onclick=()=>setTheme(!document.body.classList.contains('dark'));
$('#help').onclick=()=>$('#help-dialog').showModal();$('#connection').onclick=()=>$('#help-dialog').showModal();
$('#logout').onclick=async()=>{try{await api('/api/logout',{});showPair();}catch(error){toast(error.message);}};
document.querySelectorAll('.close-dialog').forEach(button=>button.onclick=()=>button.closest('dialog').close());
document.addEventListener('visibilitychange',()=>{notificationBaseline=true;invalidateAIDetail('화면 복귀 후 상세를 다시 확인하세요.');if(document.hidden){clearPowerComposition();powerPointers.clear();powerKeys.clear();wakePointers.clear();wakeKeys.clear();cancelTileDrag();connectionGeneration++;}else{checkPowerSave();if(!powerSleeping)refresh();}});
window.addEventListener('online',refresh);window.addEventListener('offline',()=>connection(false));
refresh();setInterval(()=>{if(!document.hidden&&!$('#dashboard').hidden)refresh();},4000);

let audioContext, tabletSound=false;
try{tabletSound=localStorage.getItem('deck-tablet-sound')==='true';}catch{}
function soundUI(){const el=$('#tablet-sound');el.setAttribute('aria-pressed',tabletSound);el.title=tabletSound?'태블릿 알림음 켜짐 · 탭하여 오디오 시작/끄기':'태블릿 알림음 꺼짐';}
soundUI();
$('#tablet-sound').onclick=async()=>{
  try{audioContext ||= new (window.AudioContext||window.webkitAudioContext)();const needsUnlock=audioContext.state!=='running';await audioContext.resume();tabletSound=needsUnlock&&tabletSound?true:!tabletSound;localStorage.setItem('deck-tablet-sound',String(tabletSound));soundUI();if(tabletSound){const oscillator=audioContext.createOscillator(),gain=audioContext.createGain();oscillator.connect(gain);gain.connect(audioContext.destination);gain.gain.value=.08;oscillator.frequency.value=880;oscillator.start();oscillator.stop(audioContext.currentTime+.12);}toast('태블릿 알림음 '+(tabletSound?'켜짐 · 시험음 재생':'꺼짐')+' · 새 승인 대기 전환에만 알립니다.');}catch{toast('브라우저 오디오를 시작하지 못했습니다. 화면을 다시 눌러주세요.');}
};
$('#mac-sound').onclick=async()=>{try{const macSound=$('#mac-sound').getAttribute('aria-pressed')!=='true';await api('/api/preferences',{macSound});$('#mac-sound').setAttribute('aria-pressed',macSound);toast('맥 알림음 '+(macSound?'켜짐':'꺼짐')+' · 새 승인 대기 전환에만 알립니다.');}catch(error){toast(error.message);}};

$('#diagnostics').onclick=async()=>{const el=$('#diagnostic-result');el.textContent='진단 중…';try{const d=await api('/api/diagnostics');el.textContent=`손쉬운 사용 ${d.accessibilityTrusted?'허용':'미허용'} · 화면 기록 ${d.screenCaptureGranted?'허용':'미허용'} · 활성 앱 ${d.name||'없음'} (PID ${d.pid}) · 활성 창 AX 조회 ${d.focusedWindowReadable?'성공':'실패'}. 로그인 화면에서는 입력을 차단합니다.`;}catch(error){el.textContent=error.message;}};

function closeArcTabs(){
  arcGeneration++;arcController?.abort();arcController=null;arcWindows=[];
  $('#arc-tabs-panel').hidden=true;$('#arc-tabs-list').replaceChildren();$('#arc-tabs-search').value='';
}
function openArcTabs(){
  $('#arc-tabs-panel').hidden=false;$('#arc-tabs-search').value='';loadArcTabs();
}
function renderArcTabs(){
  const list=$('#arc-tabs-list'),query=$('#arc-tabs-search').value.trim().toLocaleLowerCase();list.replaceChildren();let count=0;
  for(const [index,window] of arcWindows.entries()){
    const tabs=window.tabs.filter(tab=>(tab.title+' '+tab.domain).toLocaleLowerCase().includes(query));if(!tabs.length)continue;
    const section=document.createElement('section'),heading=document.createElement('h3');heading.textContent='창 '+(index+1)+' · '+tabs.length+'개';section.append(heading);
    for(const tab of tabs){const item=document.createElement('div');item.className='arc-tab';const title=document.createElement('strong'),domain=document.createElement('span');title.textContent=tab.title||'제목 없음';domain.textContent=tab.domain;item.append(title,domain);section.append(item);count++;}list.append(section);
  }
  if(!count){const empty=document.createElement('p');empty.textContent=query?'검색 결과가 없습니다.':'열린 탭이 없습니다.';list.append(empty);}
}
async function loadArcTabs(){
  if(!connected||powerSleeping||mode!=='apps'||$('#arc-tabs-panel').hidden)return;
  arcController?.abort();const controller=new AbortController();arcController=controller;const generation=++arcGeneration;
  const current=()=>generation===arcGeneration&&connected&&!powerSleeping&&mode==='apps'&&!$('#arc-tabs-panel').hidden;
  const timer=setTimeout(()=>controller.abort(),10000);$('#arc-tabs-refresh').disabled=true;$('#arc-tabs-note').textContent='Arc 탭을 읽는 중…';arcWindows=[];$('#arc-tabs-list').replaceChildren();
  try{
    const response=await fetch('/api/arc/tabs',{signal:controller.signal});const data=await response.json();if(!current())return;
    if(response.status===401){showPair();return;}
    if(!response.ok)throw Error(data.error||'탭 조회 요청을 처리하지 못했습니다.');
    if(data.status!=='ok'){$('#arc-tabs-note').textContent=data.message||'Arc 탭을 읽지 못했습니다.';return;}
    arcWindows=data.windows||[];const count=arcWindows.reduce((sum,window)=>sum+window.tabs.length,0);
    $('#arc-tabs-note').textContent=arcWindows.length+'개 창 · '+count+'개 탭'+(data.truncated?' · 표시 한도에 도달했습니다.':'')+' · 새로고침할 때만 갱신';renderArcTabs();
  }catch(error){if(current())$('#arc-tabs-note').textContent=controller.signal.aborted?'탭 조회 시간이 초과되었습니다. 직접 새로고침하세요.':error.message||'탭 조회 연결 실패';}
  finally{clearTimeout(timer);if(current())$('#arc-tabs-refresh').disabled=false;if(arcController===controller)arcController=null;}
}
$('#arc-tabs-refresh').onclick=loadArcTabs;$('#arc-tabs-search').oninput=renderArcTabs;

function buttonMode(b){return b.kind==='app'?'apps':['text','urls'].includes(b.kind)?'text':'system';}
function applyMode(){
  const labels={apps:'앱 전환',system:'시스템 제어',ai:'AI 작업',text:'문구·사이트'};
  $('#add-presets').hidden=mode!=='text';$('#mode-title').textContent=labels[mode];$('#system-panel').hidden=mode!=='system';
  document.querySelectorAll('#modes button').forEach(el=>{const selected=el.dataset.mode===mode;el.setAttribute('aria-selected',selected);el.tabIndex=selected?0:-1;});
  document.querySelectorAll('.deck>article').forEach(el=>el.hidden=mode!=='ai');$('#open-clipboard').hidden=mode!=='system';$('#edit').hidden=mode==='ai';
}
function setMode(next){if(!['apps','system','ai','text'].includes(next))return;if(next!=='apps')closeArcTabs();mode=next;try{localStorage.setItem('deck-mode',mode);}catch{}applyMode();renderButtons();if(mode==='system'&&connected)refreshSystem();}
$('#modes').onclick=event=>{const button=event.target.closest('[data-mode]');if(button)setMode(button.dataset.mode);};
$('#modes').onkeydown=event=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(event.key))return;event.preventDefault();const tabs=[...$('#modes').children],index=tabs.findIndex(el=>el.dataset.mode===mode);const next=event.key==='Home'?0:event.key==='End'?3:(index+(event.key==='ArrowRight'?1:3))%4;setMode(tabs[next].dataset.mode);tabs[next].focus();};
async function moveVisibleButton(id,offset){const visible=buttons.filter(b=>buttonMode(b)===mode),index=visible.findIndex(b=>b.id===id),other=visible[index+offset];if(!other)return;await reorderVisible(id,other.id,mode);document.querySelector(`.run-button[data-id="${id}"]`)?.focus();}
function updateTarget(d){const locked=d.bundleId==='com.apple.loginwindow',ready=d.focusedWindowReadable&&!locked;$('#target-status').textContent=locked?'맥 잠금 화면 · 키 입력 차단':`현재 맥: ${d.name||'알 수 없음'} · PID ${d.pid||'—'} · ${ready?'활성 창 확인':'창 조회 미확인'}`;}
async function refreshTarget(){if(running||pendingApp||!connected)return;const generation=targetGeneration;try{const d=await api('/api/diagnostics');if(!running&&!pendingApp&&generation===targetGeneration)updateTarget(d);}catch(error){if(generation===targetGeneration)$('#target-status').textContent='활성 앱 조회 실패 · '+error.message;}}
let systemRefreshBusy=false,systemGeneration=0;
async function refreshSystem(){if(powerSleeping||systemRefreshBusy||running)return;systemRefreshBusy=true;const generation=systemGeneration;try{const data=await api('/api/system');if(!powerSleeping&&generation===systemGeneration&&!running)updateSystem(data);}catch(error){$('#volume-note').textContent=error.message;$('#brightness-note').textContent=error.message;document.querySelectorAll('.system-action,#volume-slider,#brightness-slider').forEach(el=>el.disabled=true);}finally{systemRefreshBusy=false;}}
function updateSystem(data,force=false){systemState=data;for(const type of ['volume','brightness']){const info=data[type]||{supported:false};$('#'+type+'-value').textContent=info.value==null?'—':info.value+'%';$('#'+type+'-note').textContent=info.message||'장치 상태 미확인';const slider=$('#'+type+'-slider');slider.hidden=!info.supported;slider.disabled=!connected||!info.supported;if(force||document.activeElement!==slider)slider.value=info.value??0;document.querySelectorAll(`[data-action^="${type}_"]`).forEach(el=>el.disabled=!connected||!info.supported);}$('#mute-toggle').disabled=!connected||!data.volume?.muteSupported;$('#mute-toggle').textContent=data.volume?.muted?'음소거 해제':'음소거';$('#mute-toggle').setAttribute('aria-pressed',!!data.volume?.muted);}
async function systemCommand(action,value){if(running||!connected)return;running=true;systemGeneration++;document.querySelectorAll('.system-action,#volume-slider,#brightness-slider').forEach(el=>el.disabled=true);try{const result=await api('/api/system',{action,...(value===undefined?{}:{value}),requestId:uid()});if(result.system)updateSystem(result.system,true);toast(result.message);}catch(error){toast(error.message);}finally{running=false;const next=pendingApp;pendingApp=null;if(next&&connected)execute(next.b,next.tile);else await refreshSystem();}}
document.querySelectorAll('.system-action').forEach(el=>el.onclick=()=>systemCommand(el.dataset.action));
for(const type of ['volume','brightness'])$('#'+type+'-slider').onchange=event=>systemCommand(type+'_set',Number(event.target.value));
applyMode();

const stateLabels={working:'작업 중',idle:'대기',completed:'이번 응답 완료','input-required':'응답 필요',offline:'신호 없음',unregistered:'미등록'};
function disableReplies(){document.querySelectorAll('[data-reply]').forEach(b=>b.disabled=true);}
function notifyTablet(){if(powerSleeping||document.hidden)return;
  if(!tabletSound||document.hidden||!audioContext||audioContext.state!=='running')return;
  const oscillator=audioContext.createOscillator(),gain=audioContext.createGain();oscillator.connect(gain);gain.connect(audioContext.destination);gain.gain.value=.08;oscillator.frequency.value=880;oscillator.start();oscillator.stop(audioContext.currentTime+.15);
}
function updateIntegrations(state){
  for(const provider of ['claude','codex']){
    const value=state.usage?.[provider]||{status:'unconfigured',windows:[]};
    $('#'+provider+'-status').textContent=value.stale?'오래된 값':({ok:'실제 계정 한도',loading:'조회 중',unsupported:'미지원',no_signal:'연결 신호 없음',no_limits:'한도 필드 미제공',unconfigured:'연결 필요',error:'조회 실패'}[value.status]||'신호 없음');
    const box=$('#'+provider+'-usage');box.replaceChildren();
    for(const window of value.windows||[]){
      const panel=document.createElement('div'),line=document.createElement('div'),period=document.createElement('span'),number=document.createElement('strong'),bar=document.createElement('progress'),reset=document.createElement('p');line.className='metric-line';
      period.textContent=window.minutes===10080?'주간':window.minutes===300?'5시간':window.minutes?window.minutes+'분':'공급원 기간';number.textContent=window.usedPercent+'%';bar.max=100;bar.value=window.usedPercent;reset.textContent=window.resetsAt?'초기화 '+new Date(window.resetsAt*1000).toLocaleString('ko-KR'):'';line.append(period,number);panel.append(line,bar,reset);box.append(panel);
    }
    if(!box.children.length){const el=document.createElement('strong');el.textContent='—';box.append(el);}
    $('#'+provider+'-source').textContent=(value.message||value.source||'아직 관찰된 값이 없습니다.')+(value.updatedAt?' · '+new Date(value.updatedAt*1000).toLocaleTimeString('ko-KR'):'');
  }
  const weather=state.weather||{};$('#weather-value').textContent=weather.temperature??'—';$('#weather-note').textContent=(weather.location?.name||'위치 미설정')+' · '+(weather.status==='ok'?(weather.stale?'오래된 값 · ':'')+'Open-Meteo · '+new Date(weather.updatedAt*1000).toLocaleTimeString('ko-KR'):(weather.message||'조회 중'));
  aiState=state.ai||{slots:[],sources:[]};
  if(notificationEpoch!==aiState.epoch){notificationEpoch=aiState.epoch;notificationBaseline=true;seenTransitions.clear();}
  (aiState.slots||[]).forEach(row=>{
    if(row.transition&&!seenTransitions.has(row.transition)){
      seenTransitions.add(row.transition);if(!notificationBaseline&&row.state==='input-required')notifyTablet();
    }
  });
  notificationBaseline=false;aiSnapshotAt=Date.now();renderAISlots();
  if(aiProof){const current=aiState.slots[selectedSlot];if(!current||current.id!==aiProof.id||current.revision!==aiProof.revision||current.state!=='input-required'||Date.now()>aiProof.expires){invalidateAIDetail('상태가 바뀌었거나 확인 시간이 만료되었습니다. 창을 다시 확인하세요.');}}
}
function openAI(slot){
  selectedSlot=slot;aiCaptureAt=null;invalidateAIDetail(connected?'창 연결이 확인된 경우에만 해당 창을 캡처합니다.':'연결 끊김 · 마지막 확인값입니다.');$('#ai-image').hidden=true;
  const row=aiState.slots[slot];$('#ai-alias').value=row?.alias||'';$('#ai-settings').open=!row?.id;renderAITask();$('#ai-note').textContent=row?.id?(row.label||'')+' · '+(stateLabels[row.state]||'')+(row.source?' · '+row.source:''):'';
  aiSourceSelection=row?.id||'';$('#ai-search').value='';$('#ai-project').value='';renderAISources();
  $('#ai-capture').disabled=!connected;$('#ai-dialog').showModal();
}
let aiSourceSelection='';
function renderAISources(){
  const sources=aiState.sources||[],project=$('#ai-project').value,query=$('#ai-search').value.trim().toLocaleLowerCase();
  const projects=[...new Set(sources.map(s=>s.cwd).filter(Boolean))].sort();$('#ai-project').replaceChildren(new Option('전체 프로젝트',''));
  for(const path of projects)$('#ai-project').append(new Option(path,path));$('#ai-project').value=projects.includes(project)?project:'';
  const matches=s=>(!project||s.cwd===project)&&[s.taskName,s.project,s.cwd,s.provider,s.id].join(' ').toLocaleLowerCase().includes(query),visible=sources.filter(matches);
  const focusedSource=document.activeElement?.dataset.sourceId,listScroll=$('#ai-source-list').scrollTop;
  const selected=sources.find(s=>s.id===aiSourceSelection);if(selected&&!visible.includes(selected))visible.unshift(selected);
  $('#ai-source').replaceChildren(new Option('작업을 선택하세요 · 아직 등록되지 않습니다',''));$('#ai-source-list').replaceChildren();
  for(const source of visible){const occupied=source.registeredSlot!=null&&source.registeredSlot!==selectedSlot;const text=(source.taskName||source.label)+' · '+(source.project||'프로젝트 미제공')+' · '+stateLabels[source.state]+' · '+source.id.slice(-8)+(occupied?' · AI '+String(source.registeredSlot+1).padStart(2,'0')+'에 등록됨':'');const option=new Option(text,source.id);option.disabled=occupied;$('#ai-source').append(option);const item=document.createElement('button');item.type='button';item.className='source-item';item.dataset.sourceId=source.id;item.setAttribute('role','option');item.setAttribute('aria-selected',String(source.id===aiSourceSelection));item.disabled=occupied;const title=document.createElement('strong');title.textContent=source.taskName||source.label;const detail=document.createElement('span');detail.textContent=(source.project||'프로젝트 미제공')+' · '+source.provider+' · '+stateLabels[source.state]+' · '+source.id.slice(-8)+(occupied?' · AI '+String(source.registeredSlot+1).padStart(2,'0')+'에 등록됨':'');if(!matches(source))detail.textContent+=' · 현재 선택 (필터 밖)';item.append(title,detail);item.onclick=()=>{aiSourceSelection=source.id;renderAISources();};$('#ai-source-list').append(item);}
  if(!visible.length)$('#ai-source-list').textContent='조건에 맞는 작업이 없습니다.';
  $('#ai-source-list').scrollTop=listScroll;if(focusedSource)[...$('#ai-source-list').children].find(el=>el.dataset.sourceId===focusedSource)?.focus({preventScroll:true});
  if(aiSourceSelection&&!selected){const option=new Option('선택한 세션을 현재 목록에서 찾을 수 없습니다',aiSourceSelection);option.disabled=true;$('#ai-source').append(option);}
  $('#ai-source').value=aiSourceSelection;
  const row=aiState.slots[selectedSlot];$('#ai-registration-note').textContent=row?.id?'현재 슬롯: '+(row.taskName||row.label)+' · '+row.id.slice(-8):'현재 슬롯은 미등록입니다. 아래에서 선택한 뒤 등록을 눌러 연결하세요.';
  $('#ai-source-summary').textContent=selected?('선택: '+(selected.taskName||selected.label)+' · '+(selected.cwd||'프로젝트 미제공')+' · '+stateLabels[selected.state]+' · 최근 메타데이터 '+taskTime(selected.updatedAt)+(selected.state==='offline'?' · 현재 활동을 확인할 신호가 없습니다.':'')+' · 등록을 누르기 전까지 슬롯은 바뀌지 않습니다.'):'선택한 작업 없음';
  const info=aiState.discovery||{};$('#ai-discovery-note').textContent='발견 '+sources.length+'개 · 실제 신호가 있는 작업 / 최근 항목 순'+(info.truncated?' · 인덱스 '+info.total+'개 중 최근 '+info.listed+'개와 등록 세션 표시':'')+' · 상태는 순차 확인하며 신호 없음은 완료를 뜻하지 않습니다. Orca 창 연결은 별도 확인이 필요합니다.';
  $('#ai-register').disabled=!connected||!selected||(selected.registeredSlot!=null&&selected.registeredSlot!==selectedSlot);
}
$('#ai-source').onchange=()=>{aiSourceSelection=$('#ai-source').value;renderAISources();};
$('#ai-search').oninput=renderAISources;$('#ai-project').onchange=renderAISources;
function taskTime(value){return value?new Date(value*1000).toLocaleString('ko-KR'):'시각 미제공';}
function taskStatus(row){return !connected?'연결 끊김 · 마지막 확인값':stateLabels[row?.state]||'미등록';}
function renderAITask(){
  const row=aiState.slots[selectedSlot]||{};
  $('#ai-title').textContent=row.id?(row.taskName||'이름 없는 작업'):'AI '+String(selectedSlot+1).padStart(2,'0')+' · 미등록';
  $('#ai-task-status').textContent=taskStatus(row);$('#ai-task-status').dataset.state=connected?row.state:'disconnected';
  $('#ai-task-time').textContent='마지막 상태 변경 '+taskTime(row.stateChangedAt)+(row.stateTimeSource==='hook-received'?' · hook 수신 기준':'');
  const result=row.lastCompleted;
  $('#ai-result-time').textContent=result?taskTime(result.at)+(result.timeSource==='hook-received'?' · hook 수신 기준':''):'관찰된 완료 이력 없음';
  $('#ai-result').textContent=result?(result.title?result.title+' — ':'')+(result.preview||'공급원이 응답 내용을 제공하지 않았습니다.'):'완료를 추정하지 않습니다. 새 완료 신호가 오면 표시합니다.';
  $('#ai-alias-panel').hidden=!row.id;$('#ai-alias-save').disabled=!connected||!row.id;
}
$('#ai-alias-save').onclick=async()=>{
  const slot=selectedSlot,row=aiState.slots[slot],alias=$('#ai-alias').value;
  try{await api('/api/ai/task',{slot,session:row?.id,alias});await refresh();toast('작업 이름을 저장했습니다.');}
  catch(e){toast(e.message);}
};
$('#ai-register').onclick=async()=>{try{await api('/api/ai/register',{slot:selectedSlot,session:$('#ai-source').value});await refresh();$('#ai-dialog').close();toast('세션을 등록했습니다.');}catch(e){$('#ai-detail-note').textContent=e.message;}};
$('#ai-unregister').onclick=async()=>{try{await api('/api/ai/register',{slot:selectedSlot,session:null});await refresh();$('#ai-dialog').close();}catch(e){$('#ai-detail-note').textContent=e.message;}};
function detailCurrent(generation,slot){return connected&&generation===aiGeneration&&slot===selectedSlot&&$('#ai-dialog').open;}
function invalidateAIDetail(message){
  aiGeneration++;aiProof=null;disableReplies();$('#ai-capture').disabled=!connected;
  if(message)$('#ai-detail-note').textContent=message;
  $('#ai-image-note').textContent=aiCaptureAt?'마지막 캡처 '+new Date(aiCaptureAt).toLocaleTimeString('ko-KR')+' · '+(connected?'새 확인 필요':'연결 끊김'):'';
}
function openActivity(id){
  const row=(aiState.activity?.rows||[]).find(row=>row.id===id);if(!row)return;
  selectedActivityId=id;selectedActivitySnapshot={...row};
  invalidateAIDetail();if($('#ai-dialog').open)$('#ai-dialog').close();
  renderActivityDetail();$('#activity-dialog').showModal();
}
function renderActivityDetail(){
  if(!selectedActivityId)return;
  const activity=aiState.activity||{},current=(activity.rows||[]).find(row=>row.id===selectedActivityId);
  const row=current||selectedActivitySnapshot;
  $('#activity-dialog').dataset.sourceId=selectedActivityId;
  $('#activity-title').textContent=row.taskName;
  const fresh=connected&&activity.status==='ok'&&!!current;
  $('#activity-status').dataset.state=fresh?row.state:'disconnected';
  $('#activity-status').textContent=!connected?'연결 끊김 · 마지막 확인값':!current?'현재 작업 중 목록에 없음':activity.status!=='ok'?'조회 실패 · 마지막 확인값':row.state==='input-required'?'응답 필요 · Orca 대기 신호':'작업 중';
  $('#activity-project').textContent=row.project+' · '+row.provider;
  $('#activity-time').textContent='마지막 활동 '+taskTime(row.lastActivityAt)+' · Orca agent 갱신 시각';
  $('#activity-note').textContent=!current?'완료·신호 만료·상위 12개 밖일 수 있습니다. 완료로 추정하지 않습니다.':'읽기 전용 · 자동 등록 및 응답 실행 없음';
}
function renderAISlots(){
  const activity=aiState.activity||{},rows=activity.rows||[];
  const time=aiSnapshotAt?new Date(aiSnapshotAt).toLocaleTimeString('ko-KR'):'아직 없음';
  $('#ai-connection-note').textContent=(!connected?'연결 끊김 · 마지막 확인값':activity.status==='ok'?'Orca 최근 활동순 · '+rows.length+'개'+(activity.total>12?' / 작업 중 '+activity.total+'개':''):activity.status==='degraded'?'Orca 조회 실패 · 마지막 확인값':'Orca 활동 신호 없음')+' · 마지막 확인 '+time+(activity.truncated?' · 공급원 목록 일부만 확인':'');
  const focused=document.activeElement?.dataset.activityId;
  $('#slots').replaceChildren();
  for(const row of rows){
    const el=document.createElement('button');el.className='slot';el.dataset.activityId=row.id;
    el.dataset.state=connected&&activity.status==='ok'?row.state:'disconnected';
    const label=!connected?'연결 끊김':activity.status!=='ok'?'조회 실패 · 마지막 확인값':row.state==='input-required'?'응답 필요':'작업 중';
    for(const [tag,cls,text] of [['strong','task-name',row.taskName],['small','task-project',row.project+' · '+row.provider],['span','task-badge',label],['small','task-changed','마지막 활동 '+taskTime(row.lastActivityAt)]]){const child=document.createElement(tag);child.className=cls;child.textContent=text;el.append(child);}
    el.onclick=()=>openActivity(row.id);$('#slots').append(el);
    if(focused===row.id)el.focus({preventScroll:true});
  }
  if(!rows.length){const note=document.createElement('p');note.className='activity-empty';note.textContent=activity.status==='ok'?'현재 확인된 작업 중인 Orca 작업이 없습니다.':'Orca 활동을 확인할 수 없습니다. 완료 상태를 뜻하지 않습니다.';$('#slots').append(note);}
  $('#ai-capture').disabled=!connected;
  if($('#ai-dialog').open){renderAITask();renderAISources();}
  if($('#activity-dialog').open)renderActivityDetail();
}
$('#activity-dialog').addEventListener('close',()=>{selectedActivityId=null;selectedActivitySnapshot=null;});
$('#ai-dialog').addEventListener('close',()=>invalidateAIDetail());
$('#ai-dialog').addEventListener('cancel',()=>invalidateAIDetail());
$('#ai-capture').onclick=async()=>{
  if(!connected||!$('#ai-dialog').open)return;
  invalidateAIDetail('등록 창 확인 중…');const generation=aiGeneration,slot=selectedSlot;
  const expected=aiState.slots[slot];
  try{
    const detail=await api('/api/ai/detail?slot='+slot);
    if(!detailCurrent(generation,slot))return;
    const current=aiState.slots[slot];
    if(!current||current.id!==expected?.id||detail.id!==current.id||current.revision!==expected.revision||detail.revision<current.revision){invalidateAIDetail('세션·질문이 바뀌었습니다. 상태 갱신 후 상세를 다시 확인하세요.');return;}
    aiState.slots[slot]={...current,revision:detail.revision,state:detail.state};
    $('#ai-image').src=detail.image;$('#ai-image').hidden=false;aiCaptureAt=detail.capturedAt?detail.capturedAt*1000:Date.now();
    $('#ai-image-note').textContent='캡처 확인 '+new Date(aiCaptureAt).toLocaleTimeString('ko-KR');
    aiProof={...detail,expires:Date.now()+9000};$('#ai-detail-note').textContent='고정한 창 캡처 확인 · 10초 이내 1회 응답';
    document.querySelectorAll('[data-reply]').forEach(b=>b.disabled=detail.state!=='input-required'||current.state!=='input-required');
    setTimeout(()=>{if(generation===aiGeneration&&aiProof?.nonce===detail.nonce)invalidateAIDetail('상세 확인 시간이 만료되었습니다. 다시 확인하세요.');},9000);
  }catch(e){if(detailCurrent(generation,slot))$('#ai-detail-note').textContent=e.message;}
};
document.querySelectorAll('[data-reply]').forEach(button=>button.onclick=async()=>{
  const proof=aiProof,slot=selectedSlot,current=aiState.slots[slot];
  if(!proof||!connected||!$('#ai-dialog').open||Date.now()>=proof.expires||current?.id!==proof.id||current?.revision!==proof.revision||current?.state!=='input-required')return;
  invalidateAIDetail('응답 요청 중 · 자동 재전송하지 않습니다.');const generation=aiGeneration;
  try{const result=await api('/api/ai/reply',{slot,revision:proof.revision,nonce:proof.nonce,key:button.dataset.reply,requestId:uid()});if(detailCurrent(generation,slot))$('#ai-detail-note').textContent=result.message||'키 전송 요청 접수 · 대상 앱의 처리 결과는 확인하지 못했습니다.';}
  catch(e){if(detailCurrent(generation,slot))$('#ai-detail-note').textContent=e.message;}
});
$('#add-presets').onclick=async()=>{try{await api('/api/presets',{});await refresh();toast('기본 문구를 추가했습니다. 편집에서 내용을 바꿀 수 있습니다. Enter는 기본 꺼짐입니다.');}catch(e){toast(e.message);}};
$('#weather-settings').onclick=()=>$('#weather-dialog').showModal();
$('#weather-search').onclick=async()=>{const button=$('#weather-search');button.disabled=true;$('#weather-results').replaceChildren();try{const data=await api('/api/weather/search?q='+encodeURIComponent($('#weather-city').value));for(const city of data.cities){const el=document.createElement('button');el.className='secondary';el.textContent=city.name;el.onclick=()=>{$('#weather-name').value=city.name;$('#weather-lat').value=city.latitude;$('#weather-lon').value=city.longitude;};$('#weather-results').append(el);}$('#weather-error').textContent=data.cities.length?'도시를 선택한 뒤 저장하세요.':'검색 결과가 없습니다. 좌표를 직접 입력할 수 있습니다.';}catch(e){$('#weather-error').textContent=e.message;}finally{button.disabled=false;}};
$('#weather-form').onsubmit=async event=>{event.preventDefault();try{await api('/api/weather',{name:$('#weather-name').value,latitude:Number($('#weather-lat').value),longitude:Number($('#weather-lon').value)});$('#weather-dialog').close();await refresh();}catch(e){$('#weather-error').textContent=e.message;}};

// Device-local web power saving. This does not control the OS display or wake lock.
function armPowerTimer(){
  clearTimeout(powerTimer);
  if(powerEnabled&&!powerSleeping)powerTimer=setTimeout(checkPowerSave,Math.max(1,30000-(Date.now()-lastInputAt)));
}
function checkPowerSave(){
  clearTimeout(powerTimer);
  if(!powerEnabled||powerSleeping)return;
  if(Date.now()-lastInputAt<30000){armPowerTimer();return;}
  if(powerPointers.size||powerKeys.size||powerComposing||tileDrag||running||reorderSaving){powerTimer=setTimeout(checkPowerSave,1000);return;}
  powerSleeping=true;connection(false);systemGeneration++;notificationBaseline=true;
  $('#toast').hidden=true;document.documentElement.classList.add('web-power-saving');
  $('#power-overlay').showModal();
}
function wakePowerSave(){
  if(!powerSleeping)return;
  powerSleeping=false;lastInputAt=Date.now();powerWakeClickUntil=performance.now()+800;
  $('#power-overlay').close();document.documentElement.classList.remove('web-power-saving');
  notificationBaseline=true;invalidateAIDetail('웹 절전에서 복귀 · 최신 상태와 새 상세를 확인하세요.');
  armPowerTimer();refresh();
}
function powerInput(event){
  if(!event.isTrusted)return;
  const type=event.type;
  if(type==='pointerdown')powerPointers.add(event.pointerId);
  if(type==='pointerup'||type==='pointercancel')powerPointers.delete(event.pointerId);
  if(type==='keydown')powerKeys.add(event.code);
  if(type==='keyup')powerKeys.delete(event.code);
  if(powerSleeping){
    event.preventDefault();event.stopImmediatePropagation();
    if(type==='pointerdown')wakePointers.add(event.pointerId);
    if(type==='keydown')wakeKeys.add(event.code);
    if(['pointerdown','touchstart','keydown','click'].includes(type))wakePowerSave();
    return;
  }
  if(wakePointers.has(event.pointerId)||wakeKeys.has(event.code)){
    if(type==='pointerup'||type==='pointercancel')wakePointers.delete(event.pointerId);
    if(type==='keyup')wakeKeys.delete(event.code);
    powerWakeClickUntil=performance.now()+800;lastInputAt=Date.now();armPowerTimer();event.preventDefault();event.stopImmediatePropagation();return;
  }
  // Consume the wake gesture's compatibility click and key repeat/release.
  if(performance.now()<powerWakeClickUntil){
    if((type==='pointerdown'&&!powerKeys.size)||(type==='keydown'&&!event.repeat&&!wakeKeys.size)){powerWakeClickUntil=0;}
    else if(['click','touchstart','touchend','pointerup','keydown','keyup'].includes(type)){event.preventDefault();event.stopImmediatePropagation();return;}
  }
  if(type==='compositionstart'||type==='compositionupdate'||(type==='input'&&event.isComposing)){powerComposing=true;powerCompositionTarget=event.target;}
  if(type==='compositionend'||(type==='input'&&event.isComposing===false&&event.target===powerCompositionTarget))clearPowerComposition();
  lastInputAt=Date.now();armPowerTimer();
}
for(const type of ['pointerdown','pointerup','pointercancel','pointermove','touchstart','touchend','click','keydown','keyup','input','wheel','compositionstart','compositionupdate','compositionend'])window.addEventListener(type,powerInput,{capture:true,passive:false});
function clearPowerComposition(){powerComposing=false;powerCompositionTarget=null;}
window.addEventListener('blur',event=>{if(event.target===window||event.target===powerCompositionTarget){clearPowerComposition();armPowerTimer();}},true);
$('#power-overlay').addEventListener('cancel',event=>event.preventDefault());
try{powerEnabled=localStorage.getItem('deck-power-save')!=='false';}catch{}
$('#power-save-enabled').checked=powerEnabled;
$('#power-save-enabled').onchange=()=>{powerEnabled=$('#power-save-enabled').checked;try{localStorage.setItem('deck-power-save',String(powerEnabled));}catch{}lastInputAt=Date.now();armPowerTimer();};
armPowerTimer();

$('#transport-note').textContent=location.protocol==='https:'?'HTTPS 연결 · 브라우저가 인증서를 정상 신뢰하는지 확인하세요.':'HTTP 연결: 전송이 암호화되지 않습니다. LAN에서는 신뢰된 HTTPS를 권장합니다.';
