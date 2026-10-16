import './core.js';
import {PvpEngine} from './pvp.js';
const C=globalThis.PogoCore, ALARM='pogo-search', STOP_ALARM='pogo-stop';
let enginePromise, cycleBusy=false, deliveryBusy=false, cancellationEpoch=0, historyQueue=Promise.resolve();
const get=keys=>chrome.storage.local.get(keys);
const set=value=>chrome.storage.local.set(value);
const filterSignature=filters=>JSON.stringify(Object.entries(filters||{}).sort(([a],[b])=>a.localeCompare(b)));
async function init() {
  await chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'}).catch(()=>{});
  // Content scripts only need the trainer code; secrets stay in trusted extension pages.
  await chrome.storage.session.setAccessLevel({accessLevel:'TRUSTED_AND_UNTRUSTED_CONTEXTS'});
  const s=await get('settings');if(!s.settings)await set({settings:{...C.defaults},history:[],seen:{},run:{running:false},status:'Sẵn sàng'});
  await chrome.storage.session.set({trainerCode:s.settings?.trainerCode||''});
}
async function engine() {
  if(!enginePromise)enginePromise=fetch(chrome.runtime.getURL('data/pvpoke.json')).then(r=>r.json()).then(d=>new PvpEngine(d));
  return enginePromise;
}
async function page(tabId,type,extra={}) {
  try{
    const result=await chrome.tabs.sendMessage(tabId,{type,...extra});
    if(!result?.ok)throw Error(result?.error||'Trang không phản hồi.');return result.value;
  }catch(error){
    if(!/Receiving end does not exist|Could not establish connection/i.test(error.message))throw error;
    // Reconnect an already-open page after installing/reloading the extension.
    await chrome.scripting.executeScript({target:{tabId},func:()=>{
      if(globalThis.__pogoMonitorListener){try{chrome.runtime.onMessage.removeListener(globalThis.__pogoMonitorListener);}catch{}}
      globalThis.__pogoMonitorInstalled=false;
    }});
    await chrome.scripting.executeScript({target:{tabId},files:['core.js','content.js']});
    const result=await chrome.tabs.sendMessage(tabId,{type,...extra});
    if(!result?.ok)throw Error(result?.error||'Không kết nối được trang.');return result.value;
  }
}
async function findTab(open=false) {
  const {targetTabId}=await get('targetTabId');
  if(targetTabId){
    const t=await chrome.tabs.get(targetTabId).catch(()=>null);
    if(t?.url?.startsWith('https://pogocoordinates.com/search'))return t;
    // Login can return to the homepage. Leave OAuth/callback pages alone.
    if(t?.status!=='loading'&&/^https:\/\/pogocoordinates\.com\/?(?:[?#].*)?$/.test(t?.url||''))
      return chrome.tabs.update(t.id,{url:'https://pogocoordinates.com/search'});
  }
  const tabs=await chrome.tabs.query({url:'https://pogocoordinates.com/search*'});
  const t=tabs.find(t=>t.active)||tabs[0];
  if(t){await set({targetTabId:t.id});return t;}
  if(!open)return null;
  const created=await chrome.tabs.create({url:'https://pogocoordinates.com/search'});await set({targetTabId:created.id});return created;
}
async function focusSite() {
  const t=await findTab(true);await chrome.tabs.update(t.id,{active:true});await chrome.windows.update(t.windowId,{focused:true});return t.id;
}
async function keepAwake(run) {
  chrome.power.requestKeepAwake('system');
  await chrome.tabs.update(run.tabId,{autoDiscardable:false});
}
async function pause(reason='Đã dừng') {
  cancellationEpoch++;
  const {run}=await get('run');
  await chrome.alarms.clear(ALARM);await chrome.alarms.clear(STOP_ALARM);
  await set({run:{running:false},status:reason,nextSearchAt:null});
  chrome.power.releaseKeepAwake();
  if(run?.tabId)await chrome.tabs.update(run.tabId,{autoDiscardable:run.autoDiscardable!==false}).catch(()=>{});
}
async function start() {
  await init();const {settings}=await get('settings');const s=C.validateSettings(settings),t=await findTab(true);
  let state;try{state=await page(t.id,'PAGE_STATE');}catch{await focusSite();throw Error('Trang đang mở. Đăng nhập rồi bấm Đồng bộ lại.');}
  if(!state.loggedIn){await focusSite();throw Error('Hãy đăng nhập PoGo Coordinates trên tab vừa mở.');}
  if(!state.unlocked)throw Error('Cần nhập mã bạn bè trước khi chạy.');
  const {run:previousRun}=await get('run');
  const now=Date.now(),run={running:true,id:crypto.randomUUID(),tabId:t.id,startedAt:now,
    autoDiscardable:previousRun?.running&&previousRun.tabId===t.id?previousRun.autoDiscardable!==false:t.autoDiscardable!==false,
    filterSignature:filterSignature(state.filters),endsAt:s.durationMinutes?now+s.durationMinutes*60000:null};
  await set({settings:s,run,status:'Đang tìm…',nextSearchAt:now});
  await keepAwake(run);
  await chrome.alarms.create(ALARM,{periodInMinutes:s.intervalSeconds/60,delayInMinutes:s.intervalSeconds/60});
  if(run.endsAt)await chrome.alarms.create(STOP_ALARM,{when:run.endsAt});
  void cycle(false);return run;
}
async function activeRun(id) {
  if(!id)return true;const {run}=await get('run');return run?.running&&run.id===id&&(!run.endsAt||Date.now()<run.endsAt);
}
async function cycle(manual=false) {
  if(cycleBusy)return {skipped:true};cycleBusy=true;
  const epoch=cancellationEpoch;
  let runId=null;
  try{
    const {settings:raw,run}=await get(['settings','run']);
    if(!manual&&!run?.running)return;
    if(run?.running&&run.endsAt&&Date.now()>=run.endsAt){await pause('Đã hết thời gian chạy.');return;}
    const settings=C.validateSettings(raw),t=manual?await findTab(false):await chrome.tabs.get(run.tabId).catch(()=>null);
    if(!t||!t.url?.startsWith('https://pogocoordinates.com/search'))throw Error('Tab Search đã đóng hoặc chuyển trang.');
    runId=run?.running?run.id:null;
    if(run?.running)await keepAwake(run);
    if(t.status==='loading')throw Error('Trang Search đang tải.');
    if(!manual&&run.filterSignature){
      const current=await page(t.id,'PAGE_STATE');
      if(current.ready===false)throw Error('Trang Search đang tải.');
      if(!current.loggedIn)throw Error('Bạn cần đăng nhập PoGo Coordinates.');
      if(filterSignature(current.filters)!==run.filterSignature)
        throw Error('Bộ lọc trên web đã đổi hoặc trang đã tải lại. Đồng bộ và Bắt đầu lại.');
    }
    await set({status:'Đang bấm Search và đọc kết quả…'});
    const result=await page(t.id,'PAGE_SEARCH');
    if(epoch!==cancellationEpoch||!await activeRun(runId))return;
    const pvp=result.mode==='pvp'?await engine():null, matched=[],warnings=[];
    const skipped={expired:0,pvp:0,duplicate:0,coords:0};
    for(const spawn of result.spawns){
      if(spawn.ttlSeconds===0){skipped.expired++;continue;}
      let ranking=null;
      if(pvp){
        const outcome=pvp.evaluate(spawn,settings,result.league,result.includeEvolutions);
        if(outcome.error)warnings.push(outcome.error);
        if(!outcome.matches.length){skipped.pvp++;continue;}ranking=outcome.matches[0];
      }
      if(epoch!==cancellationEpoch||!await activeRun(runId))return;
      try{
        const detailed=await page(t.id,'PAGE_COORDS',{index:spawn.index,spawn});
        if(!detailed.ttlSeconds){skipped.expired++;continue;}
        const key=C.eventKey(detailed), {seen={}}=await get('seen');
        if(seen[key]>Date.now()){skipped.duplicate++;continue;}
        matched.push({id:crypto.randomUUID(),key,spawn:detailed,pvp:ranking,mode:result.mode,filters:result.filters,
          createdAt:Date.now(),webStatus:settings.webAlerts?'pending':'disabled',
          discordStatus:settings.discordEnabled?'pending':'disabled',attempts:0,nextRetryAt:0});
      }catch(e){skipped.coords++;warnings.push(e.message);}
    }
    if(epoch!==cancellationEpoch||!await activeRun(runId))return;
    const {seen={}}=await get('seen');
    const now=Date.now(),clean=Object.fromEntries(Object.entries(seen).filter(([,until])=>until>now));
    for(const event of matched)clean[event.key]=now+(event.spawn.ttlSeconds+60)*1000;
    await mutateHistory(history=>[...matched,...history].slice(0,300));
    const reasons=[skipped.pvp?`${skipped.pvp} không đạt ngưỡng PvP (IV Top ${settings.ivTop}, PvPoke Top ${settings.speciesTop})`:null,
      skipped.duplicate?`${skipped.duplicate} đã báo`:null,skipped.expired?`${skipped.expired} hết hạn`:null,
      skipped.coords?`${skipped.coords} lỗi lấy tọa độ`:null].filter(Boolean);
    await set({seen:clean,lastSearchAt:now,
      nextSearchAt:run?.running?now+settings.intervalSeconds*1000:null,
      status:`${result.mode.toUpperCase()}: ${result.spawns.length} kết quả, ${matched.length} thông báo mới.${!result.spawns.length?' Web không trả về Pokémon đạt bộ lọc.':''}${reasons.length?' Bỏ qua: '+reasons.join('; ')+'.':''}${warnings.length?' '+[...new Set(warnings)].slice(0,2).join(' '):''}`});
    if(settings.webAlerts&&matched.length){
      try{await page(t.id,'PAGE_ALERT',{events:matched});await updateEvents(matched.map(e=>e.id),{webStatus:'shown'});}
      catch{await updateEvents(matched.map(e=>e.id),{webStatus:'failed'});}
    }
    await deliverDiscord();return {count:result.spawns.length,matched:matched.length};
  }catch(error){
    if(epoch!==cancellationEpoch)return;
    // Retry only known transient failures. Authentication, changed filters and
    // ambiguous site errors still require attention; never reload lost filters.
    const transient=/^Trang Search đang tải\.$|^Search quá 45 giây\.$|^Nút Search đang bận\.$|^Một lượt tìm kiếm khác đang chạy\.$|message port closed|message channel closed|frame was removed|tab was discarded|Receiving end does not exist|Could not establish connection/i.test(error.message);
    if(!manual&&transient&&await activeRun(runId)){
      const {settings}=await get('settings');
      await set({status:`Đang chờ thử lại: ${error.message}`,nextSearchAt:Date.now()+settings.intervalSeconds*1000});
      return;
    }
    // Do not silently loop when authentication, selectors or permissions fail.
    await pause(`Đã dừng: ${error.message}`);
    if(/đăng nhập|login|sign in/i.test(error.message))await focusSite().catch(()=>{});
    if(manual)throw error;
  }finally{cycleBusy=false;}
}
function mutateHistory(fn) {
  const task=historyQueue.then(async()=>{
    const {history=[]}=await get('history');await set({history:fn(history)});
  });
  historyQueue=task.catch(()=>{});return task;
}
async function updateEvents(ids,patch) {
  await mutateHistory(history=>history.map(e=>ids.includes(e.id)?{...e,...patch}:e));
}
async function postWebhook(url,payload,attachment=null) {
  C.validateWebhook(url);
  let body=JSON.stringify(payload),headers={'Content-Type':'application/json'};
  if(attachment){
    body=new FormData();body.append('payload_json',JSON.stringify({...payload,attachments:[{id:0,filename:'pokemon-result.json'}]}));
    body.append('files[0]',new Blob([JSON.stringify(attachment,null,2)],{type:'application/json'}),'pokemon-result.json');headers={};
  }
  const response=await fetch(`${url}?wait=true`,{method:'POST',headers,body,signal:AbortSignal.timeout(15000)});
  if(response.status===429){const d=await response.json().catch(()=>({}));return {retryAfter:Math.max(1000,Math.ceil(Number(d.retry_after||5)*1000))};}
  if(!response.ok)throw Error(`Discord HTTP ${response.status}`);
  return {sent:true};
}
async function deliverDiscord() {
  if(deliveryBusy)return;deliveryBusy=true;
  try{
    const {settings,history=[]}=await get(['settings','history']);if(!settings?.discordEnabled)return;
    for(const event of history.filter(e=>e.discordStatus==='pending'&&e.nextRetryAt<=Date.now()).reverse().slice(0,10)){
      // Skip expired alerts instead of sending old spawns after a long browser shutdown.
      if(Date.now()>event.createdAt+event.spawn.ttlSeconds*1000){await updateEvents([event.id],{discordStatus:'expired'});continue;}
      // Persist the in-flight marker. A restart will not blindly resend an ambiguously delivered POST.
      await updateEvents([event.id],{discordStatus:'sending',attempts:event.attempts+1});
      try{
        const messages=event.discordInfoSent?[]:[{part:'info',payload:C.discordPayload(event)}];
        messages.push({part:'coords',payload:C.discordCoordinatePayload(event)});
        let retry=false;
        for(const message of messages){
          await updateEvents([event.id],{discordPart:message.part});
          const result=await postWebhook(settings.webhook,message.payload);
          if(result.retryAfter){
            await updateEvents([event.id],{discordStatus:'pending',nextRetryAt:Date.now()+result.retryAfter});
            await chrome.alarms.create('pogo-discord-retry',{when:Date.now()+result.retryAfter});retry=true;break;
          }
          if(message.part==='info')await updateEvents([event.id],{discordInfoSent:true});
        }
        if(retry)break;
        await updateEvents([event.id],{discordStatus:'sent',discordError:null});
      }catch(e){await updateEvents([event.id],{discordStatus:/^Discord HTTP \d+$/.test(e.message)?'failed':'uncertain',discordError:e.message});}
    }
    const pending=(await get('history')).history?.filter(e=>e.discordStatus==='pending');
    if(pending?.length)await chrome.alarms.create('pogo-discord-retry',{when:Math.max(Date.now()+2000,Math.min(...pending.map(e=>e.nextRetryAt)))});
  }finally{deliveryBusy=false;}
}
async function refreshData() {
  const base='https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/';
  const json=async p=>{const r=await fetch(base+p,{signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error(`PvPoke HTTP ${r.status}`);return r.json();};
  const [gm,great,ultra,bundled]=await Promise.all([json('gamemaster.json'),json('rankings/all/overall/rankings-1500.json'),
    json('rankings/all/overall/rankings-2500.json'),fetch(chrome.runtime.getURL('data/pvpoke.json')).then(r=>r.json())]);
  if(!Array.isArray(gm.pokemon)||!Array.isArray(great)||!Array.isArray(ultra)||great.length<100||ultra.length<100)throw Error('Dữ liệu PvPoke không hợp lệ.');
  if(gm.pokemon.some(p=>!p.speciesId||!p.baseStats||!Number.isFinite(p.baseStats.atk)))throw Error('Game master thiếu chỉ số.');
  const compact=d=>d.map((p,i)=>({speciesId:p.speciesId,speciesName:p.speciesName,rank:i+1,score:p.score}));
  const data={...bundled,pokemon:gm.pokemon,timestamp:gm.timestamp,fetchedAt:new Date().toISOString(),rankings:{great:compact(great),ultra:compact(ultra)}};
  await set({pvpData:data,dataUpdatedAt:data.fetchedAt});enginePromise=Promise.resolve(new PvpEngine(data));
  const tabs=await chrome.tabs.query({url:'https://pogocoordinates.com/search*'});
  await Promise.allSettled(tabs.map(t=>chrome.tabs.sendMessage(t.id,{type:'PAGE_RANKS_INVALIDATE'})));
  return data.fetchedAt;
}
async function handle(m) {
  await init();
  switch(m.type){
    case 'STATE': {
      const stored=await get(['settings','run','history','status','lastSearchAt','nextSearchAt','dataUpdatedAt']);
      const t=await findTab(false);let site=null;
      if(t)site=await page(t.id,'PAGE_STATE').catch(e=>({message:e.message,ready:false,loggedIn:false}));
      // Popup follows the web's filters; no form clone needs to cross this bridge.
      if(site)delete site.schema;
      return {...stored,site,tabId:t?.id,cycleBusy};
    }
    case 'OPEN_SITE': return focusSite();
    case 'SAVE': {
      if(cycleBusy)throw Error('Chờ lượt Search hoàn tất rồi lưu cấu hình.');
      const settings=C.validateSettings(m.settings);await pause('Đã lưu cấu hình.');await set({settings});
      await chrome.storage.session.set({trainerCode:settings.trainerCode});return settings;
    }
    case 'EDIT': {
      if(cycleBusy)throw Error('Chờ lượt Search hoàn tất rồi sửa trường.');
      await pause('Đã đổi bộ lọc. Bấm Bắt đầu để chạy lại.');const t=await findTab(false);if(!t)throw Error('Mở tab Search trước.');
      return page(t.id,'PAGE_EDIT',m.edit);
    }
    case 'START': return start();
    case 'STOP': await pause();return true;
    case 'CLEAR_HISTORY': {
      if(cycleBusy||deliveryBusy)throw Error('Chờ lượt tìm hoặc gửi Discord hoàn tất rồi xóa lịch sử.');
      await pause('Đã xóa lịch sử. Bấm Tìm ngay hoặc Chạy tự động để thử lại.');
      await chrome.alarms.clear('pogo-discord-retry');
      await mutateHistory(()=>[]);
      await set({seen:{},lastSearchAt:null});
      return true;
    }
    case 'SEARCH_ONCE': return cycle(true);
    case 'REFRESH_DATA': return refreshData();
    case 'TEST_DISCORD': {
      const {settings}=await get('settings');C.validateWebhook(settings.webhook);
      const result=await postWebhook(settings.webhook,{content:'✅ PoGo Radar: kết nối Discord thành công.',allowed_mentions:{parse:[]}});
      if(!result.sent)throw Error('Discord đang giới hạn tốc độ. Thử lại sau.');return true;
    }
    case 'RETRY_DISCORD': await updateEvents([m.id],{discordStatus:'pending',nextRetryAt:0});await deliverDiscord();return true;
    default:throw Error('Yêu cầu không được hỗ trợ.');
  }
}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{
  if(m.type==='PAGE_PVPOKE_RANKS'&&sender.id===chrome.runtime.id&&sender.tab&&
    /^https:\/\/pogocoordinates\.com\/search(?:[?#]|$)/.test(sender.url||'')){
    if(!['great','ultra'].includes(m.league)||!Array.isArray(m.spawns)||m.spawns.length>100){
      reply({ok:false,error:'Yêu cầu hạng PvPoke không hợp lệ.'});return;
    }
    engine().then(pvp=>reply({ok:true,value:m.spawns.map(s=>pvp.speciesRanking(
      {dex:s?.dex,name:String(s?.name||'').slice(0,256),form:String(s?.form||'').slice(0,256)},
      m.league,m.includeEvolutions===true))}),()=>reply({ok:false,error:'Không đọc được hạng PvPoke.'}));return true;
  }
  if(m.type==='PAGE_MONITOR_STATUS'&&sender.id===chrome.runtime.id&&sender.tab&&
    /^https:\/\/pogocoordinates\.com\//.test(sender.url||'')){
    get(['run','status','lastSearchAt','nextSearchAt']).then(stored=>{
      const run=stored.run||{};
      reply({ok:true,value:{running:!!run.running&&(!run.endsAt||run.endsAt>Date.now()),
        onThisTab:run.tabId===sender.tab.id,endsAt:run.endsAt||null,
        status:stored.status||'Chưa chạy',lastSearchAt:stored.lastSearchAt||null,
        nextSearchAt:stored.nextSearchAt||null,cycleBusy}});
    },()=>reply({ok:false,error:'Không đọc được trạng thái.'}));return true;
  }
  // Web page/content scripts cannot configure secrets, start jobs, or send Discord messages.
  if(sender.id!==chrome.runtime.id||sender.url?.split('?')[0]!==chrome.runtime.getURL('panel.html'))return;
  handle(m).then(value=>reply({ok:true,value}),e=>reply({ok:false,error:e.message}));return true;
});
chrome.action.onClicked.addListener(async()=>{
  const url=chrome.runtime.getURL('panel.html'),tabs=await chrome.tabs.query({url});
  if(tabs.length){await chrome.tabs.update(tabs[0].id,{active:true});await chrome.windows.update(tabs[0].windowId,{focused:true});}
  else await chrome.tabs.create({url});
});
chrome.alarms.onAlarm.addListener(a=>{
  if(a.name===ALARM)void cycle(false);
  if(a.name===STOP_ALARM)void pause('Đã hết thời gian chạy.');
  if(a.name==='pogo-discord-retry')void deliverDiscord();
});
async function restore() {
  await init();const {run,pvpData,settings,history=[]}=await get(['run','pvpData','settings','history']);
  if(pvpData)enginePromise=Promise.resolve(new PvpEngine(pvpData));
  await mutateHistory(history=>history.map(e=>e.discordStatus==='sending'?{...e,discordStatus:'uncertain',discordError:'Browser dừng lúc gửi; kiểm tra Discord trước khi gửi lại.'}:e));
  if(run?.running){
    if(run.endsAt&&run.endsAt<=Date.now())await pause('Đã hết thời gian chạy.');
    else{
      await keepAwake(run).catch(()=>{});
      await chrome.alarms.create(ALARM,{periodInMinutes:settings.intervalSeconds/60,delayInMinutes:settings.intervalSeconds/60});
      if(run.endsAt)await chrome.alarms.create(STOP_ALARM,{when:run.endsAt});
    }
  }else chrome.power.releaseKeepAwake();
}
chrome.runtime.onInstalled.addListener(()=>void restore());
chrome.runtime.onStartup.addListener(()=>void restore());
// This runs on worker wake too, so cached rankings survive normal MV3 suspension.
void get('pvpData').then(({pvpData})=>{if(pvpData&&!enginePromise)enginePromise=Promise.resolve(new PvpEngine(pvpData));});
