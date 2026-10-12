(() => {
  'use strict';
  const $=id=>document.getElementById(id),C=globalThis.PogoCore;
  let state=null,loaded=false,dirty=false,working=false,toastTimer;
  async function rpc(type,extra={}) {
    const reply=await chrome.runtime.sendMessage({type,...extra});
    if(!reply?.ok)throw Error(reply?.error||'Extension không phản hồi.');return reply.value;
  }
  function toast(message,error=false){$('toast').textContent=message;$('toast').classList.toggle('error',error);$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,7000);}
  async function task(fn){if(working)return;working=true;try{await fn();}catch(e){toast(e.message,true);}finally{working=false;}}
  function readSettings(){
    const result={};for(const key of Object.keys(C.defaults)){const e=$(key);result[key]=e.type==='checkbox'?e.checked:e.value;}
    return C.validateSettings(result);
  }
  function fillSettings(s){for(const key of Object.keys(C.defaults)){const e=$(key);if(e.type==='checkbox')e.checked=s[key];else e.value=s[key];}}
  function el(tag,props={}){return Object.assign(document.createElement(tag),props);}
  function showView(view){
    for(const name of ['monitor','settings','history'])$('view-'+name).hidden=name!==view;
    for(const button of document.querySelectorAll('[data-view]'))button.setAttribute('aria-pressed',String(button.dataset.view===view));
  }
  for(const button of document.querySelectorAll('[data-view]'))button.onclick=()=>showView(button.dataset.view);
  async function search(type){
    if(!state?.site?.loggedIn){await rpc('OPEN_SITE');toast('Đăng nhập trên tab web vừa mở, rồi quay lại đây. Extension sẽ tự nhận.');return;}
    if(dirty){await rpc('SAVE',{settings:readSettings()});dirty=false;}
    await rpc(type);await refresh(false);
  }
  function time(t){return t?new Date(t).toLocaleString('vi-VN'):'—';}
  const delivery={sent:'đã gửi',pending:'đang chờ',sending:'đang gửi',failed:'lỗi',uncertain:'chưa xác định',expired:'spawn hết hạn',disabled:'tắt',shown:'đã hiện'};
  function renderHistory(history){
    $('historyCount').textContent=`(${history.length})`;$('history').replaceChildren();
    $('navCount').textContent=history.length;
    if(!history.length){$('history').append(el('p',{className:'hint',textContent:'Chưa có kết quả mới đạt điều kiện.'}));return;}
    for(const event of history.slice(0,100)){
      const s=event.spawn,p=event.pvp,row=el('article',{className:'result'}),left=el('div'),middle=el('div'),right=el('div');
      left.append(el('strong',{textContent:`${s.fullName} #${s.dex}`}),el('p',{textContent:`CP ${s.cp} · LV ${s.level} · IV ${s.ivPercent}% (${s.iv?.join('/')||'?'})`}),el('p',{className:'hint',textContent:`${event.mode.toUpperCase()} · ${time(event.createdAt)}`}));
      middle.append(el('p',{textContent:s.location}),el('a',{textContent:s.coords,href:`https://www.google.com/maps?q=${encodeURIComponent(s.coords)}`,target:'_blank',rel:'noopener noreferrer'}));
      if(p)middle.append(el('p',{textContent:`${p.speciesName} · ${p.league}: IV #${p.ivRank}, PvPoke #${p.speciesRank??'?'}`}));
      right.append(el('p',{className:'delivery',textContent:`Web: ${delivery[event.webStatus]||event.webStatus} · Discord: ${delivery[event.discordStatus]||event.discordStatus}`}));
      if(event.discordError)right.append(el('p',{className:'hint',textContent:event.discordError}));
      if(['failed','uncertain'].includes(event.discordStatus)){
        const retry=el('button',{textContent:'Gửi lại Discord'});retry.onclick=()=>void task(async()=>{await rpc('RETRY_DISCORD',{id:event.id});await refresh(false);});right.append(retry);
      }
      const details=el('details'),summary=el('summary',{textContent:'Bộ lọc và dữ liệu đầy đủ'}),pre=el('pre',{textContent:JSON.stringify({spawn:s,pvp:p,filters:event.filters},null,2)});pre.style.cssText='white-space:pre-wrap;font-size:11px;overflow-wrap:anywhere';details.append(summary,pre);right.append(details);
      row.append(left,middle,right);$('history').append(row);
    }
  }
  async function refresh(fields=true){
    state=await rpc('STATE');
    if(!loaded){fillSettings({...C.defaults,...state.settings});loaded=true;}
    const site=state.site;
    $('loginText').textContent=site?.message||'Chưa có tab PoGo Coordinates. Mở web và đăng nhập.';
    $('loginGate').hidden=!!site?.loggedIn;
    const codeReady=/^\d{12}$/.test(String($('trainerCode').value).replace(/[\s-]/g,''));
    $('nextStep').textContent=state.run?.running
      ?'Đang tìm tự động. Bạn có thể đóng popup.'
      :!site?.loggedIn?'Đăng nhập trên web để bắt đầu.'
      :!site?.unlocked?'Nhập mã bạn bè trong Cài đặt.'
      :'Sẵn sàng chạy theo bộ lọc trên web.';
    $('start').textContent=!site?.loggedIn?'Đăng nhập trên web':!site?.unlocked?(codeReady?'Lưu mã & tiếp tục':'Nhập mã bạn bè'):'Chạy tự động';
    $('badge').textContent=state.run?.running?'Đang chạy':site?.loggedIn?'Đã đăng nhập':'Cần đăng nhập';
    $('status').textContent=state.status||'Sẵn sàng';
    $('timing').textContent=`Lần Search gần nhất: ${time(state.lastSearchAt)} · Lần kế: ${time(state.nextSearchAt)}${state.run?.endsAt?' · Dừng lúc: '+time(state.run.endsAt):''}`;
    $('start').disabled=state.run?.running||state.cycleBusy;
    $('searchOnce').disabled=!site?.unlocked||state.cycleBusy;
    $('stop').disabled=!state.run?.running&&!state.cycleBusy;
    $('testDiscord').disabled=dirty||!state.settings?.webhook;
    $('dirty').hidden=!dirty;
    $('siteMode').textContent=site?.loggedIn?`Đã kết nối · ${site.mode==='pvp'?'PvP':'Stats'}${site.mode==='pvp'?' · '+(site.league==='ultra'?'Ultra League':'Great League'):''}`:'Chưa kết nối web';
    $('scheduleSummary').textContent=`Mỗi ${state.settings?.intervalSeconds||60} giây · ${state.settings?.durationMinutes?state.settings.durationMinutes+' phút':'Chạy đến khi dừng'}`;
    renderHistory(state.history||[]);
    $('dataDate').textContent=`PvPoke Overall Open Great / Ultra League. Cập nhật: ${state.dataUpdatedAt?time(state.dataUpdatedAt):'bản đóng gói 12/10/2026'}. Hạng IV được tính cục bộ từ base stats và CPM của PvPoke.`;
  }
  $('settingsForm').addEventListener('input',()=>{dirty=true;$('dirty').hidden=false;$('testDiscord').disabled=true;
    if(state?.site?.loggedIn&&!state.site.unlocked){$('start').disabled=false;$('start').textContent=/^\d{12}$/.test(String($('trainerCode').value).replace(/[\s-]/g,''))?'Lưu mã & tiếp tục':'Nhập mã bạn bè';}
  });
  $('settingsForm').addEventListener('submit',e=>{e.preventDefault();void task(async()=>{await rpc('SAVE',{settings:readSettings()});dirty=false;toast('Đã lưu. Bấm Chạy tự động để bắt đầu.');await refresh(true);showView('monitor');});});
  for(const id of ['openSite','login','configureSite'])$(id).onclick=()=>void task(async()=>{await rpc('OPEN_SITE');});
  for(const id of ['sync'])$(id).onclick=()=>void task(()=>refresh(true));
  $('refreshHistory').onclick=()=>void task(()=>refresh(false));
  $('clearHistory').onclick=()=>void task(async()=>{
    await rpc('CLEAR_HISTORY');await refresh(false);showView('monitor');
    toast('Đã xóa lịch sử. Bấm Tìm ngay để gửi lại kết quả hiện có.');
  });
  $('start').onclick=()=>void task(async()=>{
    if(state?.site?.loggedIn&&!state.site.unlocked){
      if(!/^\d{12}$/.test(String($('trainerCode').value).replace(/[\s-]/g,''))){showView('settings');$('trainerCode').focus();return;}
      await rpc('SAVE',{settings:readSettings()});dirty=false;await refresh(true);showView('monitor');return;
    }
    await search('START');
  });
  $('stop').onclick=()=>void task(async()=>{await rpc('STOP');await refresh(false);});
  $('searchOnce').onclick=()=>void task(()=>search('SEARCH_ONCE'));
  $('testDiscord').onclick=()=>void task(async()=>{await rpc('TEST_DISCORD');toast('Đã gửi tin thử tới Discord.');});
  $('refreshData').onclick=()=>void task(async()=>{await rpc('REFRESH_DATA');toast('Đã cập nhật dữ liệu PvPoke.');await refresh(false);});
  void task(async()=>{
    await refresh(true);

  });
  // Keep settings edits and dropdown focus intact; only refresh status/history in the background.
  setInterval(()=>{if(!working&&!document.hidden)void task(()=>refresh(false));},5000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!working)void task(()=>refresh(false));});
  window.addEventListener('focus',()=>{if(!working)void task(()=>refresh(false));});
})();
