import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
const html=await readFile(new URL('../panel.html',import.meta.url),'utf8');
const source=await readFile(new URL('../panel.js',import.meta.url),'utf8');
const core=await readFile(new URL('../core.js',import.meta.url),'utf8');
const tick=()=>new Promise(resolve=>setTimeout(resolve,20));
async function harness(unlocked=false){
  const dom=new JSDOM(html,{runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,calls=[];
  const schema={kind:'group',children:[{kind:'input',id:'1',label:'CP',value:'10'},
    {kind:'button',id:'2',text:'Search',command:'search',disabled:false}]};
  const state={settings:{trainerCode:'123456789012'},site:{loggedIn:unlocked,unlocked,schema:unlocked?schema:null},history:[]};
  let poll;w.setInterval=fn=>{poll=fn;};
  w.chrome={runtime:{sendMessage:async m=>{calls.push(m);return {ok:true,value:m.type==='STATE'?structuredClone(state):true};}}};
  w.eval(core);w.eval(source);await tick();
  return {dom,w,state,calls,schema,poll};
}
test('Popup reconnects after login and reads the web mode without cloned filters',async()=>{
  const h=await harness();Object.assign(h.state.site,{loggedIn:true,unlocked:true,mode:'pvp',league:'great'});h.poll();await tick();
  assert.match(h.w.document.getElementById('siteMode').textContent,/PvP/);
  assert.equal(h.w.document.querySelector('#filters'),null);
  assert.equal(h.w.document.getElementById('loginGate').hidden,true);h.dom.window.close();
});
test('Returning from login refreshes immediately and missing trainer code requests code instead of another login',async()=>{
  const h=await harness();Object.assign(h.state.site,{loggedIn:true,unlocked:false});
  h.w.dispatchEvent(new h.w.Event('focus'));await tick();
  assert.equal(h.w.document.getElementById('loginGate').hidden,true);
  assert.match(h.w.document.getElementById('nextStep').textContent,/mã bạn bè/);
  assert.equal(h.w.document.getElementById('start').textContent,'Lưu mã & tiếp tục');
  assert.equal(h.w.document.getElementById('start').disabled,false);h.dom.window.close();
});
test('Search once auto-saves settings and never edits web filters',async()=>{
  const h=await harness(true),interval=h.w.document.getElementById('intervalSeconds');interval.value='90';
  interval.dispatchEvent(new h.w.Event('input',{bubbles:true}));h.w.document.getElementById('searchOnce').click();await tick();
  const save=h.calls.findIndex(m=>m.type==='SAVE'),search=h.calls.findIndex(m=>m.type==='SEARCH_ONCE');
  assert.ok(save>=0&&search>save);assert.equal(h.calls[save].settings.intervalSeconds,90);
  assert.ok(!h.calls.some(m=>m.type==='EDIT'));h.dom.window.close();
});
test('Popup waits for explicit login action and opens website for filter changes',async()=>{
  const h=await harness();assert.ok(!h.calls.some(m=>m.type==='OPEN_SITE'));
  h.w.document.getElementById('configureSite').click();await tick();assert.ok(h.calls.some(m=>m.type==='OPEN_SITE'));h.dom.window.close();
});
test('Separate settings and history views preserve unsaved settings when switching tabs',async()=>{
  const h=await harness(true),d=h.w.document;
  assert.equal(d.getElementById('view-monitor').hidden,false);assert.equal(d.getElementById('view-settings').hidden,true);
  d.querySelector('[data-view="settings"]').click();d.getElementById('intervalSeconds').value='120';
  d.querySelector('[data-view="history"]').click();assert.equal(d.getElementById('view-monitor').hidden,true);
  assert.equal(d.getElementById('view-history').hidden,false);
  d.querySelector('[data-view="settings"]').click();assert.equal(d.getElementById('intervalSeconds').value,'120');h.dom.window.close();
});
