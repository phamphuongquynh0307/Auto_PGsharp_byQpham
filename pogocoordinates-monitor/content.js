(() => {
  'use strict';
  if (globalThis.__pogoMonitorInstalled) return;
  globalThis.__pogoMonitorInstalled = true;
  globalThis.__pogoMonitorStatusCleanup?.();
  const C=globalThis.PogoCore, nodes=new Map(), nodeIds=new WeakMap();
  let nextId=1,busy=false,alertsRoot=null;
  const text=e=>(e?.innerText||e?.textContent||'').trim();
  const buttons=(root=document)=>[...root.querySelectorAll('button')];
  const exact=(name,root=document)=>buttons(root).find(e=>text(e)===name);
  const form=()=>[...document.querySelectorAll('main form')].find(f=>exact('Search',f));
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const visible=e=>!!e&&e.getClientRects().length>0;
  function auth() {
    const nav=document.querySelector('nav'), f=form();
    if(!nav||!f)return {loggedIn:false,ready:false,message:'Đang chờ form Search. Mở /search.'};
    const login=[...nav.querySelectorAll('a')].some(a=>/login|sign in/i.test(text(a))||/oauth2\/authorize|\/o\/oauth2/.test(a.href));
    return {loggedIn:!login,ready:true,message:login?'Bạn cần đăng nhập PoGo Coordinates.':'Đã đăng nhập trên web.'};
  }
  async function guard() {
    const a=auth();if(!a.loggedIn)throw Error(a.message);
    if(!exact('Stats',form())||!exact('PvP',form()))throw Error('Chọn tab Pokémon trên web; extension theo dõi Stats/PvP của Pokémon.');
    const {trainerCode}=await chrome.storage.session.get('trainerCode');
    if(!/^\d{12}$/.test(trainerCode||''))throw Error('Nhập mã bạn bè 12 số trong extension trước.');
    return {trainerCode};
  }
  function labelFor(e) {
    if(e.getAttribute('aria-label'))return e.getAttribute('aria-label');
    for(let p=e.parentElement;p&&p!==form();p=p.parentElement){
      const label=[...p.children].find(x=>x.tagName==='LABEL')||p.querySelector(':scope > div > label');
      if(label)return text(label);
    }
    return e.getAttribute('placeholder')||text(e)||e.tagName;
  }
  function locked(e) {
    return e.disabled||!!e.closest('[aria-hidden="true"]')||e.getAttribute('aria-disabled')==='true';
  }
  function idFor(e) {
    let id=nodeIds.get(e);if(!id){id=String(nextId++);nodeIds.set(e,id);}nodes.set(id,e);return id;
  }
  function snapshotNode(e) {
    if(e.nodeType===Node.TEXT_NODE)return e.textContent.trim()?{kind:'text',text:e.textContent}:null;
    if(e.nodeType!==Node.ELEMENT_NODE||['SCRIPT','STYLE','SVG','IMG','PATH'].includes(e.tagName))return null;
    if(e.tagName==='INPUT'&&e.type==='hidden')return null;
    const common={label:labelFor(e),disabled:locked(e)};
    if(e.matches('input,select,textarea'))return {kind:e.tagName.toLowerCase(),id:idFor(e),...common,
      type:e.type,value:e.value,checked:e.checked,placeholder:e.getAttribute('placeholder')||'',
      min:e.getAttribute('min'),max:e.getAttribute('max'),step:e.getAttribute('step'),
      options:e.tagName==='SELECT'?[...e.options].map(o=>({value:o.value,text:o.text,disabled:o.disabled})):undefined};
    if(e.matches('button,[role="button"],[role="switch"]')){
      const name=text(e)||e.getAttribute('aria-label')||'Xóa lựa chọn';
      const selected=e.getAttribute('aria-checked')==='true'||e.className.includes('bg-[var(--accent)]');
      return {kind:'button',id:idFor(e),...common,text:name,selected,role:e.getAttribute('role'),
        command:e.type==='submit'&&name==='Search'?'search':undefined,
        disabled:common.disabled||(e.type==='submit'&&name!=='Search')||/Use my location|Notify Me|Unlock .*VIP/.test(name),
        children:[...e.querySelectorAll('[role="button"]')].map(snapshotNode).filter(Boolean)};
    }
    if(e.tagName==='A')return {kind:'text',text:text(e)};
    const children=[...e.childNodes].map(snapshotNode).filter(Boolean);
    if(!children.length)return null;
    return {kind:e.tagName==='LABEL'?'label':e.tagName==='P'?'note':'group',
      layout:e.classList.contains('grid')?'grid':e.classList.contains('inline-flex')?'row':'',children};
  }
  function filters() {
    const f=form(),values={};if(!f)return values;
    for(const e of f.querySelectorAll('input,select,button.input-field,[role="switch"]')){
      if(e.type==='hidden'||e.closest('[aria-hidden="true"]'))continue;
      if(/^Search by name|^Search forms/i.test(e.placeholder||''))continue;
      let label=labelFor(e);if(e.placeholder)label+=` · ${e.placeholder}`;
      const value=e.tagName==='SELECT'?e.selectedOptions[0]?.text:e.matches('[role="switch"]')?e.getAttribute('aria-checked'):
        e.matches('button')?text(e):e.value;
      values[label]=String(value??'').trim()||'Any / không giới hạn';
    }
    values['Filter by']=mode();
    values['Location mode']=exact('Area',f)?.className.includes('bg-[var(--accent)]')?'Area':'Coords';
    if(mode()==='stats')values['IV mode']=exact('Raw IV',f)?.className.includes('bg-[var(--accent)]')?'Raw IV':'% IV';
    return values;
  }
  function mode() {
    const p=exact('PvP',form());return p?.className.includes('bg-[var(--accent)]')?'pvp':'stats';
  }
  function pvpOptions() {
    const f=form();const selects=[...f.querySelectorAll('select')];
    return {league:selects.find(s=>labelFor(s)==='League')?.value||'great',
      includeEvolutions:selects.find(s=>labelFor(s)==='Include previous evolutions')?.value!=='no'};
  }
  function cardElements() {
    return [...document.querySelectorAll('main .card')].filter(c=>!c.matches('form')&&!c.closest('form')&&
      [...c.querySelectorAll('p')].some(p=>text(p)==='CP')&&[...c.querySelectorAll('p')].some(p=>text(p)==='IV'));
  }
  let rankTimer=null,rankRequest=0,rankSignature='';
  function clearRankColumns(){
    for(const host of document.querySelectorAll('[data-pogo-pvpoke]')){
      const grid=host.parentElement;host.remove();
      if(grid?.dataset.pogoRankGrid==='true'){
        grid.classList.replace('grid-cols-4','grid-cols-3');delete grid.dataset.pogoRankGrid;
      }
    }
  }
  async function refreshRankColumns(){
    const request=++rankRequest;
    if(!form()||mode()!=='pvp'){rankSignature='';clearRankColumns();return;}
    const cards=cardElements(),options=pvpOptions();
    const parsed=cards.map(c=>C.parseCard(text(c)));
    if(parsed.some(s=>!s)){rankSignature='';clearRankColumns();return;}
    const spawns=parsed.map(s=>({dex:s.dex,name:s.name,form:s.form}));
    const signature=JSON.stringify([options,spawns]);
    if(signature===rankSignature&&cards.every(c=>c.querySelector('[data-pogo-pvpoke]')))return;
    let response;
    try{response=await chrome.runtime.sendMessage({type:'PAGE_PVPOKE_RANKS',...options,spawns});}catch{return;}
    if(request!==rankRequest||!response?.ok||!Array.isArray(response.value))return;
    // A Search may replace all rows while the background is answering.
    if(cards.some(c=>!c.isConnected)||!form()||mode()!=='pvp'||JSON.stringify(pvpOptions())!==JSON.stringify(options))return;
    if(JSON.stringify(cards.map(c=>{const s=C.parseCard(text(c));return s?{dex:s.dex,name:s.name,form:s.form}:null;}))!==JSON.stringify(spawns))return;
    rankSignature=signature;
    cards.forEach((card,i)=>{
      const grid=[...card.querySelectorAll('.grid')].find(g=>['CP','LVL','IV'].every(label=>
        [...g.querySelectorAll('p')].some(p=>text(p)===label)));
      if(!grid)return;
      let host=card.querySelector('[data-pogo-pvpoke]');
      if(!host){
        host=document.createElement('div');host.dataset.pogoPvpoke='true';
        const shadow=host.attachShadow({mode:'open'}),style=document.createElement('style');
        style.textContent=':host{display:block;min-width:0}p{margin:0}.label{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--text-muted,#94a3b8)}.rank{font:600 12px ui-monospace,monospace;color:var(--accent,#a78bfa)}.species{font:10px system-ui;color:var(--text-muted,#94a3b8);overflow-wrap:anywhere}';
        const label=document.createElement('p'),value=document.createElement('p'),species=document.createElement('p');
        label.className='label';label.textContent='PvPoke';value.className='rank';species.className='species';
        shadow.append(style,label,value,species);grid.append(host);
        if(grid.classList.contains('grid-cols-3')){grid.classList.replace('grid-cols-3','grid-cols-4');grid.dataset.pogoRankGrid='true';}
      }
      const rank=response.value[i],league=options.league==='great'?'Great League 1500':'Ultra League 2500';
      host.shadowRoot.querySelector('.rank').textContent=rank?`#${rank.speciesRank}`:'—';
      host.shadowRoot.querySelector('.species').textContent=rank?.speciesName||'Chưa có hạng';
      host.title=`${league} · Hạng loài PvPoke, không phải hạng IV.${options.includeEvolutions?' Xét cả tiến hóa, hiển thị loài có hạng tốt nhất.':''}`;
    });
  }
  function scheduleRankColumns(){
    rankRequest++;clearTimeout(rankTimer);rankTimer=setTimeout(()=>void refreshRankColumns(),150);
  }
  const rankObserver=new MutationObserver(records=>{
    if(records.every(r=>r.target.closest?.('[data-pogo-pvpoke]')||
      (r.type==='childList'&&[...r.addedNodes,...r.removedNodes].every(n=>n.nodeType===1&&n.matches('[data-pogo-pvpoke]')))))return;
    scheduleRankColumns();
  });
  rankObserver.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['class','value'],characterData:true});
  document.addEventListener('change',scheduleRankColumns);
  scheduleRankColumns();
  async function state() {
    const a=auth();const {trainerCode}=await chrome.storage.session.get('trainerCode');
    const unlocked=a.loggedIn&&/^\d{12}$/.test(trainerCode||'');
    nodes.clear();
    return {...a,unlocked,mode:form()?mode():'stats',schema:unlocked?snapshotNode(form()):null,
      filters:unlocked?filters():{},url:location.href};
  }
  async function edit(message) {
    await guard();if(busy)throw Error('Đang Search, chờ hoàn tất rồi sửa bộ lọc.');
    const e=nodes.get(String(message.id));if(!e||!e.isConnected||!form()?.contains(e))throw Error('Trường đã đổi. Bấm Đồng bộ lại.');
    if(locked(e))throw Error('Trường bị khóa trên web (VIP hoặc không khả dụng).');
    if(message.action==='click'){
      if(e.type==='submit'||/Use my location|Notify Me|Unlock .*VIP/.test(text(e)))throw Error('Thao tác này cần thực hiện trực tiếp trên web.');
      e.click();
    } else if(e.matches('input,textarea,select')){
      const prototype=e.tagName==='SELECT'?HTMLSelectElement.prototype:e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
      const property=e.type==='checkbox'?'checked':'value';
      Object.getOwnPropertyDescriptor(prototype,property).set.call(e,property==='checked'?!!message.value:String(message.value));
      e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));
    }else throw Error('Không thể sửa trường này.');
    await sleep(120);return state();
  }
  async function search() {
    await guard();if(busy)throw Error('Một lượt tìm kiếm khác đang chạy.');
    const f=form(),submit=exact('Search',f);if(!submit||submit.disabled)throw Error('Nút Search đang bận.');
    if(!f.reportValidity())throw Error('Bộ lọc trên web chưa hợp lệ.');
    busy=true;
    try {
      const sentFilters=filters(),sentMode=mode(),options=pvpOptions();
      let started=false;
      const observer=new MutationObserver(()=>{if(submit.disabled||text(submit)!=='Search')started=true;});
      observer.observe(f,{subtree:true,attributes:true,childList:true,characterData:true});
      submit.click();
      try{
        const deadline=Date.now()+45000;
        while(Date.now()<deadline){
          await sleep(100);if(submit.disabled||text(submit)!=='Search')started=true;
          const current=exact('Search',form());
          if(started&&current&&!current.disabled){await sleep(150);break;}
        }
        if(!started)throw Error('Không xác minh được web bắt đầu lượt Search mới; bỏ qua kết quả cũ.');
        if(!exact('Search',form())||exact('Search',form()).disabled)throw Error('Search quá 45 giây.');
      }finally{observer.disconnect();}
      await guard();
      const error=[...document.querySelectorAll('main [role="alert"],main .text-red-500,main .text-red-400,main [class*="text-[var(--danger)]"]')]
        .map(text).filter(t=>/error|failed|limit|try again|login|log in|expired|unauthoriz|invalid|forbidden/i.test(t)).join('; ');
      if(error)throw Error(error);
      const cards=cardElements();
      const mainText=text(document.querySelector('main'));
      // A visible count (including zero) is required; otherwise a failed request could leave old cards.
      if(!/Showing\s+\d+\s+(spawns|results)|No (results|spawns|Pokemon|Pokémon)|Nothing found/i.test(mainText))
        throw Error('Web không trả về số kết quả; có thể phiên đã hết hạn hoặc bị giới hạn.');
      return {mode:sentMode,filters:sentFilters,...options,spawns:cards.map((c,i)=>({...C.parseCard(text(c)),index:i})).filter(s=>s.name)};
    }finally{busy=false;}
  }
  async function coords(message) {
    await guard();const cards=cardElements(),card=cards[message.index];
    const original=C.parseCard(text(card));
    if(!original||original.dex!==message.spawn.dex||original.cp!==message.spawn.cp||original.iv?.join('/')!==message.spawn.iv?.join('/')||original.location!==message.spawn.location)
      throw Error('Kết quả đã thay đổi trước khi lấy tọa độ.');
    if(!original.coords){
      const b=exact('Get coords',card);if(!b)throw Error('Không tìm thấy Get coords.');b.click();
      const deadline=Date.now()+15000;
      while(Date.now()<deadline){await sleep(150);if(C.parseCard(text(card))?.coords)break;if(/error|failed|expired|limit/i.test(text(card)))break;}
    }
    const result=C.parseCard(text(card));
    if(!result?.coords)throw Error('Web chưa cho lấy tọa độ (hết hạn, hạn mức hoặc lỗi mạng).');
    return result;
  }
  function showAlerts(events) {
    if(!events.length)return;
    if(!alertsRoot){
      const host=document.createElement('div');host.id='pogo-monitor-alerts';document.body.append(host);
      alertsRoot=host.attachShadow({mode:'open'});
      const style=document.createElement('style');style.textContent=`:host{position:fixed;right:16px;bottom:16px;z-index:2147483647;font:14px system-ui;color:#edf4ff;width:min(430px,calc(100vw - 32px))} .feed{max-height:65vh;overflow:auto} article{background:#182237;border:1px solid #62d7aa;border-radius:12px;padding:14px;margin-top:8px;box-shadow:0 8px 30px #0008} h3{margin:0 0 7px;font-size:15px} p{margin:4px 0;line-height:1.4} a{color:#7bdcbb} button{float:right;color:white;background:transparent;border:0;cursor:pointer;font-size:18px}`;
      alertsRoot.append(style,Object.assign(document.createElement('div'),{className:'feed'}));
    }
    const feed=alertsRoot.querySelector('.feed');
    for(const event of events){
      const article=document.createElement('article'),s=event.spawn,p=event.pvp;
      const close=document.createElement('button');close.textContent='×';close.setAttribute('aria-label','Đóng thông báo');close.onclick=()=>article.remove();article.append(close);
      const h=document.createElement('h3');h.textContent=`${event.mode.toUpperCase()} · ${s.fullName}`;article.append(h);
      for(const line of [`CP ${s.cp} · LV ${s.level} · IV ${s.ivPercent}% (${s.iv?.join('/')||'?'})`,s.location,
        ...(p?[`${p.speciesName}: IV #${p.ivRank} · PvPoke #${p.speciesRank??'?'} · ${p.league}`]:[]),`Còn ${s.despawn} lúc phát hiện`]){
        const row=document.createElement('p');row.textContent=line;article.append(row);
      }
      const link=document.createElement('a');link.textContent=s.coords;link.href=`https://www.google.com/maps?q=${encodeURIComponent(s.coords)}`;link.target='_blank';link.rel='noopener noreferrer';article.append(link);feed.prepend(article);
    }
    while(feed.children.length>30)feed.lastElementChild.remove();
  }
  globalThis.__pogoMonitorListener=(m,sender,respond)=>{
    if(sender.id!==chrome.runtime.id)return;
    const tasks={PAGE_STATE:state,PAGE_EDIT:()=>edit(m),PAGE_SEARCH:search,PAGE_COORDS:()=>coords(m),PAGE_ALERT:()=>{showAlerts(m.events||[]);return {ok:true};},PAGE_RANKS_INVALIDATE:()=>{rankSignature='';scheduleRankColumns();return true;}};
    if(!tasks[m.type])return;
    Promise.resolve().then(tasks[m.type]).then(value=>respond({ok:true,value}),e=>respond({ok:false,error:e.message}));return true;
  };
  chrome.runtime.onMessage.addListener(globalThis.__pogoMonitorListener);

  // Keep a small read-only indicator on the page even while the popup is closed.
  document.getElementById('pogo-monitor-status')?.remove();
  const statusHost=document.createElement('div');statusHost.id='pogo-monitor-status';
  document.body.append(statusHost);
  const statusRoot=statusHost.attachShadow({mode:'open'});
  const statusStyle=document.createElement('style');
  statusStyle.textContent=`:host{position:fixed;left:16px;bottom:16px;z-index:2147483646;font:13px system-ui;color:#edf4ff;width:min(310px,calc(100vw - 32px))}section{background:#182237;border:1px solid #64748b;border-radius:12px;box-shadow:0 6px 24px #0006;overflow:hidden}button{display:block;width:100%;background:transparent;color:inherit;border:0;text-align:left;padding:11px 13px;font:600 13px system-ui;cursor:pointer}button:focus-visible{outline:2px solid #7bdcbb;outline-offset:-3px}.details{padding:0 13px 11px}p{margin:5px 0;line-height:1.4;overflow-wrap:anywhere}.muted{color:#b6c4d8;font-size:12px}[hidden]{display:none}`;
  const box=document.createElement('section'),badge=document.createElement('button'),details=document.createElement('div');
  details.className='details';badge.type='button';badge.setAttribute('aria-expanded','true');
  badge.title='Bấm để thu gọn / mở trạng thái';
  const message=document.createElement('p'),timing=document.createElement('p'),hint=document.createElement('p');
  timing.className=hint.className='muted';hint.textContent='Đóng popup vẫn chạy · Mở extension để điều khiển';
  details.append(message,timing,hint);box.append(badge,details);statusRoot.append(statusStyle,box);
  badge.onclick=()=>{details.hidden=!details.hidden;badge.setAttribute('aria-expanded',String(!details.hidden));};
  let monitorState=null,lastStatusAt=0,statusPending=false,disposed=false;
  const clock=value=>value?new Date(value).toLocaleTimeString('vi-VN'):'—';
  function renderMonitorStatus(){
    if(!lastStatusAt||Date.now()-lastStatusAt>15000){
      badge.textContent='⚪ PoGo Monitor · Chưa kết nối';box.style.borderColor='#64748b';
      message.textContent='Không xác nhận được trạng thái. Mở extension hoặc tải lại trang.';timing.textContent='';return;
    }
    const s=monitorState,running=s.running&&(!s.endsAt||s.endsAt>Date.now());
    const searching=s.cycleBusy&&(!running||s.onThisTab);
    badge.textContent=`${searching?'🟡':running?'🟢':'⏸'} PoGo Monitor · ${searching?'Đang tìm':running?(s.onThisTab?'Đang chạy':'Chạy ở tab khác'):'Đã dừng'}`;
    box.style.borderColor=searching?'#fbbf24':running?'#62d7aa':'#64748b';message.textContent=s.status;
    let next='—';
    if(running&&s.nextSearchAt){const seconds=Math.ceil((s.nextSearchAt-Date.now())/1000);next=seconds>0?`còn ${seconds}s`:'đang chờ lượt tìm';}
    timing.textContent=`Tìm gần nhất: ${clock(s.lastSearchAt)} · Lần kế: ${next}${running&&s.endsAt?' · Dừng: '+clock(s.endsAt):''}`;
  }
  async function refreshMonitorStatus(){
    if(statusPending||disposed)return;statusPending=true;
    try{
      const response=await chrome.runtime.sendMessage({type:'PAGE_MONITOR_STATUS'});
      if(!disposed&&response?.ok){monitorState=response.value;lastStatusAt=Date.now();}
    }catch{lastStatusAt=0;}finally{statusPending=false;if(!disposed)renderMonitorStatus();}
  }
  renderMonitorStatus();void refreshMonitorStatus();
  const pollTimer=setInterval(()=>void refreshMonitorStatus(),5000),clockTimer=setInterval(renderMonitorStatus,1000);
  const onVisible=()=>{if(!document.hidden)void refreshMonitorStatus();};
  document.addEventListener('visibilitychange',onVisible);
  globalThis.__pogoMonitorStatusCleanup=()=>{disposed=true;clearInterval(pollTimer);clearInterval(clockTimer);document.removeEventListener('visibilitychange',onVisible);statusHost.remove();rankRequest++;clearTimeout(rankTimer);rankObserver.disconnect();document.removeEventListener('change',scheduleRankColumns);clearRankColumns();};
})();
