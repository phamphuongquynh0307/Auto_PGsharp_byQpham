import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
const html=await readFile(new URL('./fixtures/search.html',import.meta.url),'utf8');
const source=await readFile(new URL('../content.js',import.meta.url),'utf8');
const core=await readFile(new URL('../core.js',import.meta.url),'utf8');
function harness(loggedIn=true,code='123456789012',fixture=html){
  const dom=new JSDOM(fixture,{url:'https://pogocoordinates.com/search',runScripts:'outside-only'}),w=dom.window;
  // jsdom does not implement layout-derived innerText. Preserve block line breaks as the browser does.
  Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){
    function walk(n){if(n.nodeType===3)return n.textContent;
      if(['SVG','SCRIPT','STYLE'].includes(n.tagName))return '';
      const out=[...n.childNodes].map(walk).join('');return /^(P|DIV|FORM|MAIN|NAV|SECTION|BUTTON)$/.test(n.tagName)?`\n${out}\n`:out;}
    return walk(this).replace(/\n\s*\n/g,'\n').trim();
  }});
  if(loggedIn)for(const a of w.document.querySelectorAll('nav a'))if(/Login/.test(a.textContent))a.remove();
  let listener;
  w.chrome={runtime:{id:'test',onMessage:{addListener:fn=>listener=fn},sendMessage:async()=>({ok:true,value:{running:false,status:'Đã dừng'}})},storage:{session:{get:async()=>({trainerCode:code})}}};
  w.eval(core);w.eval(source);
  const call=m=>new Promise(resolve=>listener(m,{id:'test'},resolve));
  return {w,dom,call};
}
test('Web PvPoke column annotates every result without changing parsed spawn data',async t=>{
 const h=harness();t.after(()=>h.dom.window.close());
 const cards=[...h.w.document.querySelectorAll('main .card')].filter(c=>!c.matches('form')&&/\bCP\b/.test(c.innerText)&&/\bIV\b/.test(c.innerText));
 const before=cards.map(c=>JSON.stringify(h.w.PogoCore.parseCard(c.innerText)));
 const requests=[];
 h.w.chrome.runtime.sendMessage=async m=>{
  if(m.type==='PAGE_PVPOKE_RANKS'){
   requests.push(m);return {ok:true,value:m.spawns.map((s,i)=>i?null:{speciesName:'Corviknight',speciesRank:9})};
  }
  return {ok:true,value:{running:false,status:'Đã dừng'}};
 };
 await new Promise(resolve=>h.w.setTimeout(resolve,400));
 assert.equal(requests.length,1);assert.equal(requests[0].league,'great');
 assert.equal(cards.length,5);
 const column=cards[0].querySelector('[data-pogo-pvpoke]');
 assert.equal(column.shadowRoot.querySelector('.rank').textContent,'#9');
 assert.equal(column.shadowRoot.querySelector('.species').textContent,'Corviknight');
 assert.match(column.title,/Great League 1500/);
 assert.ok(column.parentElement.classList.contains('grid-cols-4'));
 assert.equal(cards[1].querySelector('[data-pogo-pvpoke]').shadowRoot.querySelector('.rank').textContent,'—');
 assert.deepEqual(cards.map(c=>JSON.stringify(h.w.PogoCore.parseCard(c.innerText))),before);
 h.w.__pogoMonitorStatusCleanup();
 assert.equal(h.w.document.querySelectorAll('[data-pogo-pvpoke]').length,0);
 assert.ok(column.parentElement===null);
});

test('Web rank changes with league and removes columns after switching to Stats',async t=>{
 const h=harness();t.after(()=>h.dom.window.close());
 h.w.chrome.runtime.sendMessage=async m=>m.type==='PAGE_PVPOKE_RANKS'
  ?{ok:true,value:m.spawns.map(()=>({speciesName:'Pikachu',speciesRank:m.league==='great'?10:20}))}
  :{ok:true,value:{running:false,status:'Đã dừng'}};
 await new Promise(resolve=>h.w.setTimeout(resolve,300));
 const select=[...h.w.document.querySelectorAll('select')].find(s=>[...s.options].some(o=>o.value==='ultra'));
 select.value='ultra';select.dispatchEvent(new h.w.Event('change',{bubbles:true}));
 await new Promise(resolve=>h.w.setTimeout(resolve,300));
 const column=h.w.document.querySelector('[data-pogo-pvpoke]');
 assert.equal(column.shadowRoot.querySelector('.rank').textContent,'#20');assert.match(column.title,/Ultra League 2500/);
 const pvp=[...h.w.document.querySelectorAll('button')].find(b=>b.textContent.trim()==='PvP');
 pvp.className='';
 await new Promise(resolve=>h.w.setTimeout(resolve,300));
 assert.equal(h.w.document.querySelectorAll('[data-pogo-pvpoke]').length,0);
});
test('Unauthenticated page cannot search or expose editable cloned fields even with trainer code',async()=>{
  const h=harness(false);const s=await h.call({type:'PAGE_STATE'});assert.equal(s.value.loggedIn,false);assert.equal(s.value.schema,null);
  const search=await h.call({type:'PAGE_SEARCH'});assert.equal(search.ok,false);assert.match(search.error,/đăng nhập/);h.dom.window.close();
});

test('Page indicator follows background state with popup closed, collapses and shows disconnected state',async t=>{
  const h=harness();
  t.after(()=>h.dom.window.close());
  Object.defineProperty(h.w.document,'hidden',{value:false,configurable:true});
  await new Promise(resolve=>h.w.setTimeout(resolve,0));
  const shadow=h.w.document.querySelector('#pogo-monitor-status').shadowRoot;
  assert.match(shadow.querySelector('button').textContent,/Đã dừng/);
  h.w.chrome.runtime.sendMessage=async m=>{
    assert.equal(m.type,'PAGE_MONITOR_STATUS');
    return {ok:true,value:{running:true,onThisTab:true,status:'Stats: 5 kết quả',lastSearchAt:Date.now(),nextSearchAt:Date.now()+60000}};
  };
  h.w.document.dispatchEvent(new h.w.Event('visibilitychange'));
  await new Promise(resolve=>h.w.setTimeout(resolve,0));
  assert.match(shadow.querySelector('button').textContent,/Đang chạy/);
  assert.match(shadow.textContent,/Stats: 5 kết quả/);
  assert.match(shadow.querySelector('.muted').textContent,/còn 60s/);
  shadow.querySelector('button').click();assert.equal(shadow.querySelector('.details').hidden,true);
  h.w.chrome.runtime.sendMessage=async()=>{throw Error('Extension context invalidated');};
  h.w.document.dispatchEvent(new h.w.Event('visibilitychange'));
  await new Promise(resolve=>h.w.setTimeout(resolve,0));
  assert.match(shadow.querySelector('button').textContent,/Chưa kết nối/);
  h.w.__pogoMonitorStatusCleanup();assert.equal(h.w.document.querySelector('#pogo-monitor-status'),null);
  h.dom.window.close();
});
test('Authenticated page still requires trainer code',async()=>{
  const h=harness(true,'');const s=await h.call({type:'PAGE_STATE'});assert.equal(s.value.unlocked,false);
  const search=await h.call({type:'PAGE_SEARCH'});assert.match(search.error,/mã bạn bè/);h.dom.window.close();
});
function flatten(n){return n?[n,...(n.children||[]).flatMap(flatten)]:[];}
test('Clone real site fields including league/rank/evolutions and respect VIP locks',async()=>{
  const h=harness();const s=await h.call({type:'PAGE_STATE'}),nodes=flatten(s.value.schema);
  assert.equal(s.value.mode,'pvp');assert.ok(nodes.some(n=>n.label==='League'&&n.kind==='select'));
  assert.ok(nodes.some(n=>n.label==='Top ranking'&&n.kind==='input'));
  assert.ok(nodes.some(n=>n.label==='Include previous evolutions'));
  const search=nodes.find(n=>n.command==='search');assert.ok(search);assert.equal(search.disabled,false);
  assert.equal((await h.call({type:'PAGE_EDIT',id:search.id,action:'click'})).ok,false);
  assert.equal(nodes.find(n=>n.label==='Min. TTL (minutes)'&&n.kind==='input').disabled,true);
  const rank=nodes.find(n=>n.label==='Top ranking'&&n.kind==='input');
  const changed=await h.call({type:'PAGE_EDIT',id:rank.id,action:'value',value:'20'});assert.equal(changed.ok,true);
  assert.equal(h.w.document.querySelector('input[placeholder="1-50"]').value,'20');
  const ttl=nodes.find(n=>n.label==='Min. TTL (minutes)'&&n.kind==='input');
  assert.equal((await h.call({type:'PAGE_EDIT',id:ttl.id,action:'value',value:'5'})).ok,false);h.dom.window.close();
});
test('Successful search waits for completion and emits complete current results',async()=>{
  const h=harness();const b=h.w.document.querySelector('button[type="submit"]');
  b.addEventListener('click',e=>{e.preventDefault();b.disabled=true;setTimeout(()=>{b.disabled=false;},20);});
  const result=await h.call({type:'PAGE_SEARCH'});assert.equal(result.ok,true,result.error);
  assert.equal(result.value.spawns.length,5);assert.deepEqual([...result.value.spawns[0].iv],[15,15,14]);
  assert.equal(result.value.mode,'pvp');assert.equal(result.value.filters['Top ranking · 1-50'],'10');h.dom.window.close();
});
test('Failed search does not send old result cards',async()=>{
  const h=harness();const b=h.w.document.querySelector('button[type="submit"]');
  b.addEventListener('click',e=>{e.preventDefault();b.disabled=true;setTimeout(()=>{b.disabled=false;
    const p=h.w.document.createElement('p');p.setAttribute('role','alert');p.textContent='Search failed, try again';h.w.document.querySelector('main').append(p);},20);});
  const result=await h.call({type:'PAGE_SEARCH'});assert.equal(result.ok,false);assert.match(result.error,/Search failed/);h.dom.window.close();
});
test('Coordinate request refuses changed result and obtains coordinates from the matching card',async()=>{
  const h=harness();const card=[...h.w.document.querySelectorAll('main .card')].find(c=>!c.matches('form'));
  const spawn=h.w.PogoCore.parseCard(card.innerText);
  const mismatch=await h.call({type:'PAGE_COORDS',index:0,spawn:{...spawn,cp:1}});assert.equal(mismatch.ok,false);
  const b=[...card.querySelectorAll('button')].find(b=>b.textContent.trim()==='Get coords');
  b.addEventListener('click',()=>{b.textContent='41.123456,-8.654321';});
  const result=await h.call({type:'PAGE_COORDS',index:0,spawn});assert.equal(result.ok,true,result.error);
  assert.equal(result.value.coords,'41.123456,-8.654321');h.dom.window.close();
});
test('Web notification shows result safely, with no HTML injection',async()=>{
  const h=harness();const result=await h.call({type:'PAGE_ALERT',events:[{mode:'stats',spawn:{fullName:'<img src=x onerror=alert(1)>',cp:5,level:1,ivPercent:100,iv:[15,15,15],location:'test',despawn:'05:00',coords:'10.123456,106.123456'}}]});
  assert.equal(result.ok,true);const shadow=h.w.document.querySelector('#pogo-monitor-alerts').shadowRoot;
  assert.equal(shadow.querySelectorAll('img').length,0);assert.ok(shadow.textContent.includes('<img'));h.dom.window.close();
});
test('Raw IV, CP ranges, weather and Area location are all cloned as separate editable fields',async()=>{
  const statsHtml=await readFile(new URL('./fixtures/stats.html',import.meta.url),'utf8');
  const h=harness(true,'123456789012',statsHtml);const result=await h.call({type:'PAGE_STATE'});
  const nodes=flatten(result.value.schema);assert.equal(result.value.mode,'stats');
  for(const placeholder of ['A','D','S','Location contains (e.g. Auckland)'])assert.ok(nodes.some(n=>n.placeholder===placeholder),placeholder);
  assert.ok(nodes.some(n=>n.label==='Weather'&&n.kind==='select'));
  assert.equal(nodes.filter(n=>n.label==='CP'&&n.kind==='input').length,2);
  assert.equal(result.value.filters['IV mode'],'Raw IV');assert.equal(result.value.filters['Location mode'],'Area');
  h.dom.window.close();
});
