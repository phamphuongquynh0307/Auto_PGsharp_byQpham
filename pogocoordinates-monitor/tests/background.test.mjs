import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import '../core.js';
const C=globalThis.PogoCore;
const data=JSON.parse(await readFile(new URL('../data/pvpoke.json',import.meta.url),'utf8'));
let serial=0;
async function harness(options={}){
  const store={settings:{...C.defaults,trainerCode:'123456789012',discordEnabled:true,webhook:'https://discord.com/api/webhooks/12345/test_token',...options.settings},run:{running:false},history:[],seen:{}},session={},alarms=new Map();
  const listeners={},posts=[],web=[],power={level:null},tab={id:11,windowId:1,url:options.tabUrl||'https://pogocoordinates.com/search',active:true,status:options.tabStatus||'complete',autoDiscardable:options.autoDiscardable!==false};
  if(options.tabUrl)store.targetTabId=11;
  const spawn={dex:25,name:'Pikachu',fullName:'Pikachu',form:'',cp:474,level:18,iv:[14,14,14],ivPercent:93,gender:'Male',size:'M',moves:'Thunder Shock / Discharge',location:'Pasay, Philippines',despawn:'30:00',ttlSeconds:1800,coords:'14.538988,121.004883',index:0};
  let searches=0;
  const event=name=>({addListener:fn=>listeners[name]=fn});
  globalThis.chrome={runtime:{id:'test',getURL:p=>`chrome-extension://test/${p}`,onMessage:event('message'),onInstalled:event('install'),onStartup:event('startup')},
    storage:{local:{get:async keys=>{const names=typeof keys==='string'?[keys]:keys;return structuredClone(Object.fromEntries(names.filter(k=>k in store).map(k=>[k,store[k]])));},set:async obj=>Object.assign(store,structuredClone(obj)),setAccessLevel:async()=>{}},
      session:{set:async obj=>Object.assign(session,obj),setAccessLevel:async()=>{}}},
    action:{onClicked:event('action')},windows:{update:async()=>{}},scripting:{executeScript:async()=>{}},
    power:{requestKeepAwake:level=>power.level=level,releaseKeepAwake:()=>power.level=null},
    alarms:{onAlarm:event('alarm'),create:async(name,info)=>alarms.set(name,info),clear:async name=>alarms.delete(name)},
    tabs:{get:async()=>options.closed?null:tab,query:async()=>options.closed||!tab.url.includes('/search')?[]:[tab],create:async()=>tab,update:async(_,patch)=>Object.assign(tab,patch),
      sendMessage:async(_,m)=>{
        if(m.type==='PAGE_STATE')return {ok:true,value:{loggedIn:options.loggedIn!==false,unlocked:options.loggedIn!==false,ready:true,filters:options.filters||{Pokemon:'Pikachu'},schema:{kind:'group',children:[]}}};
        if(m.type==='PAGE_SEARCH'){
          searches++;if(options.searchDelay)await new Promise(r=>setTimeout(r,options.searchDelay));
          if(options.searchError)return {ok:false,error:options.searchError};
          return {ok:true,value:{mode:options.mode||'stats',filters:{Pokemon:'Pikachu'},league:'great',includeEvolutions:true,spawns:[spawn]}};
        }
        if(m.type==='PAGE_COORDS')return {ok:true,value:spawn};
        if(m.type==='PAGE_ALERT'){web.push(m.events);return {ok:true,value:{}};}
        return {ok:true,value:{}};
      }}
  };
  globalThis.fetch=async(url,init)=>{
    if(String(url).startsWith('chrome-extension:'))return new Response(JSON.stringify(data),{status:200});
    posts.push({url,body:JSON.parse(typeof init.body==='string'?init.body:init.body.get('payload_json')),
      attachment:typeof init.body==='string'?null:await init.body.get('files[0]').text()});
    if(options.networkFail||options.networkFailAt===posts.length)throw Error('fetch failed');
    if((options.discord429&&posts.length===1)||options.discord429At===posts.length)return new Response(JSON.stringify({retry_after:1}),{status:429});
    if(options.discordFail)return new Response('bad',{status:401});
    return new Response('{}',{status:200});
  };
  await import(`../background.js?test=${serial++}`);
  const rpc=m=>new Promise(resolve=>listeners.message(m,{id:'test',url:'chrome-extension://test/panel.html'},resolve));
  const until=async condition=>{const end=Date.now()+3000;while(!condition()&&Date.now()<end)await new Promise(r=>setTimeout(r,5));assert.ok(condition(),'operation timed out');};
  return {store,session,alarms,listeners,posts,web,rpc,spawn,until,power,tab,options,get searches(){return searches;}};
}

test('Unlimited run keeps system awake and tab protected until stopped',async()=>{
  const h=await harness();await h.rpc({type:'START'});
  await h.until(()=>h.store.history[0]?.discordStatus==='sent');
  assert.equal(h.store.run.endsAt,null);assert.equal(h.power.level,'system');
  assert.equal(h.tab.autoDiscardable,false);assert.equal(h.alarms.has('pogo-stop'),false);
  await h.rpc({type:'STOP'});
  assert.equal(h.power.level,null);assert.equal(h.tab.autoDiscardable,true);
});

test('Stopping preserves an existing tab discard exclusion',async()=>{
  const h=await harness({autoDiscardable:false});await h.rpc({type:'START'});
  await h.until(()=>h.store.history[0]?.discordStatus==='sent');await h.rpc({type:'STOP'});
  assert.equal(h.tab.autoDiscardable,false);
});

test('Transient Search failures retain schedule and recover on the following alarm',async()=>{
  for(const searchError of ['Search quá 45 giây.','Nút Search đang bận.','Một lượt tìm kiếm khác đang chạy.']){
    const h=await harness({searchError});await h.rpc({type:'START'});
    await h.until(()=>h.store.status.startsWith('Đang chờ thử lại:'));
    assert.equal(h.store.run.running,true);assert.ok(h.alarms.has('pogo-search'));
    assert.equal(h.posts.length,0);assert.ok(h.store.nextSearchAt>Date.now());
    h.options.searchError=null;h.listeners.alarm({name:'pogo-search'});
    await h.until(()=>h.store.history[0]?.discordStatus==='sent');assert.equal(h.searches,2);
    await h.rpc({type:'STOP'});
  }
});

test('Loading tab waits without clicking Search and recovers without changing filters',async()=>{
  const h=await harness();await h.rpc({type:'START'});
  await h.until(()=>h.store.history[0]?.discordStatus==='sent');
  h.tab.status='loading';h.listeners.alarm({name:'pogo-search'});
  await h.until(()=>h.store.status.startsWith('Đang chờ thử lại:'));
  assert.equal(h.store.run.running,true);assert.equal(h.searches,1);
  h.tab.status='complete';h.listeners.alarm({name:'pogo-search'});
  await h.until(()=>h.searches===2);await h.rpc({type:'STOP'});
});

test('Startup restores keep-awake protection and deadline releases it',async()=>{
  const h=await harness();h.store.run={running:true,id:'saved',tabId:11,autoDiscardable:true,endsAt:Date.now()+60000};
  h.listeners.startup();await h.until(()=>h.alarms.has('pogo-stop'));
  assert.equal(h.power.level,'system');assert.equal(h.tab.autoDiscardable,false);
  h.listeners.alarm({name:'pogo-stop'});await h.until(()=>h.power.level===null);
  assert.equal(h.store.run.running,false);assert.equal(h.tab.autoDiscardable,true);
});

test('Authentication and unknown website failures stop and release keep-awake',async()=>{
  for(const searchError of ['Bạn cần đăng nhập PoGo Coordinates.','forbidden','Web không trả về số kết quả; có thể phiên đã hết hạn hoặc bị giới hạn.']){
    const h=await harness({searchError});await h.rpc({type:'START'});
    await h.until(()=>h.store.status.startsWith('Đã dừng:')&&h.power.level===null);
    assert.equal(h.store.run.running,false);assert.equal(h.tab.autoDiscardable,true);
    assert.equal(h.alarms.has('pogo-search'),false);assert.equal(h.posts.length,0);
  }
});
test('Stats sends information then standalone coordinates and deduplicates the pair',async()=>{
  const h=await harness();assert.equal((await h.rpc({type:'SEARCH_ONCE'})).ok,true);
  assert.equal(h.store.history.length,1);assert.equal(h.posts.length,2);assert.equal(h.web.length,1);
  assert.equal(h.store.history[0].discordStatus,'sent');assert.equal(h.store.history[0].webStatus,'shown');
  assert.equal(h.posts[0].attachment,null);assert.equal(h.posts[0].body.content,undefined);
  assert.deepEqual(h.posts[1].body,{content:h.spawn.coords,allowed_mentions:{parse:[]}});
  assert.ok(!JSON.stringify(h.posts[0].body).includes(h.store.settings.trainerCode));
  await h.rpc({type:'SEARCH_ONCE'});assert.equal(h.searches,2);assert.equal(h.posts.length,2);assert.equal(h.store.history.length,1);
});
test('Page rank bridge returns only public species ranks and rejects oversized requests',async()=>{
 const h=await harness();
 const sender={id:'test',tab:{id:11},url:'https://pogocoordinates.com/search'};
 const request=m=>new Promise(resolve=>h.listeners.message(m,sender,resolve));
 const result=await request({type:'PAGE_PVPOKE_RANKS',league:'great',includeEvolutions:true,spawns:[{dex:821,name:'Rookidee',form:''}]});
 assert.equal(result.ok,true);assert.equal(result.value.length,1);assert.ok(result.value[0].speciesRank>0);
 assert.deepEqual(Object.keys(result.value[0]).sort(),['speciesName','speciesRank']);
 const body=JSON.stringify(result);assert.ok(!body.includes(h.store.settings.trainerCode));assert.ok(!body.includes(h.store.settings.webhook));
 assert.equal(h.posts.length,0);assert.equal(h.searches,0);
 const invalid=await request({type:'PAGE_PVPOKE_RANKS',league:'great',spawns:Array(101).fill({})});assert.equal(invalid.ok,false);
});

test('Page status exposes only progress and times, never settings, codes or webhook',async()=>{
  const h=await harness();
  h.store.run={running:true,tabId:11,endsAt:Date.now()+60000};
  h.store.status='Đang tìm';h.store.lastSearchAt=Date.now();h.store.nextSearchAt=Date.now()+30000;
  const reply=await new Promise(resolve=>h.listeners.message({type:'PAGE_MONITOR_STATUS'},
    {id:'test',tab:{id:11},url:'https://pogocoordinates.com/search'},resolve));
  assert.equal(reply.ok,true);assert.equal(reply.value.running,true);assert.equal(reply.value.onThisTab,true);
  assert.equal(reply.value.lastSearchAt,h.store.lastSearchAt);
  const body=JSON.stringify(reply);assert.ok(!body.includes(h.store.settings.webhook));
  assert.ok(!body.includes(h.store.settings.trainerCode));assert.ok(!body.includes('settings'));
  assert.equal(h.listeners.message({type:'PAGE_MONITOR_STATUS'},
    {id:'test',tab:{id:11},url:'https://example.com/'},()=>assert.fail('untrusted origin')),undefined);
  h.store.run.endsAt=Date.now()-1000;
  const expired=await new Promise(resolve=>h.listeners.message({type:'PAGE_MONITOR_STATUS'},
    {id:'test',tab:{id:11},url:'https://pogocoordinates.com/'},resolve));
  assert.equal(expired.value.running,false);
});
test('MV3 alarm interval and configured stop deadline are saved; stopping cancels search alarm',async()=>{
  const h=await harness({settings:{durationMinutes:5,intervalSeconds:30}});await h.rpc({type:'START'});
  assert.equal(h.alarms.get('pogo-search').periodInMinutes,.5);assert.ok(h.alarms.has('pogo-stop'));
  await h.until(()=>h.store.history[0]?.discordStatus==='sent');await h.rpc({type:'STOP'});
  assert.equal(h.store.run.running,false);assert.equal(h.alarms.has('pogo-search'),false);
});
test('Expired runtime never performs another search',async()=>{
  const h=await harness();h.store.run={running:true,id:'a',tabId:11,endsAt:Date.now()-1};
  h.listeners.alarm({name:'pogo-search'});await h.until(()=>!h.store.run.running);assert.equal(h.searches,0);
});
test('Stop during pending search suppresses notifications from that cycle',async()=>{
  const h=await harness({searchDelay:100});const pending=h.rpc({type:'SEARCH_ONCE'});
  await h.until(()=>h.searches===1);await h.rpc({type:'STOP'});await pending;
  assert.equal(h.posts.length,0);assert.equal(h.store.history.length,0);
});
test('Missing login blocks start and session expiration pauses an active monitor',async()=>{
  const h=await harness({loggedIn:false});const result=await h.rpc({type:'START'});assert.equal(result.ok,false);assert.match(result.error,/đăng nhập/);
  const h2=await harness({searchError:'Bạn cần đăng nhập PoGo Coordinates.'});h2.store.run={running:true,id:'a',tabId:11};
  h2.listeners.alarm({name:'pogo-search'});await h2.until(()=>!h2.store.run.running);assert.equal(h2.posts.length,0);
});
test('PvP results failing configured ranks are not notified',async()=>{
  const h=await harness({mode:'pvp',settings:{ivTop:1,speciesTop:1}});await h.rpc({type:'SEARCH_ONCE'});
  assert.equal(h.posts.length,0);assert.equal(h.web.length,0);assert.match(h.store.status,/không đạt ngưỡng PvP/);
});
test('Discord 429 is retained for retry and never marked sent prematurely',async()=>{
  const h=await harness({discord429:true});await h.rpc({type:'SEARCH_ONCE'});
  assert.equal(h.store.history[0].discordStatus,'pending');assert.ok(h.alarms.has('pogo-discord-retry'));
  h.store.history[0].nextRetryAt=0;h.listeners.alarm({name:'pogo-discord-retry'});
  await h.until(()=>h.store.history[0].discordStatus==='sent');assert.equal(h.posts.length,3);
});
test('Webhook failure is visible and does not cause an endless automatic retry',async()=>{
  const h=await harness({discordFail:true});await h.rpc({type:'SEARCH_ONCE'});
  assert.equal(h.store.history[0].discordStatus,'failed');assert.match(h.store.history[0].discordError,/401/);
  await h.rpc({type:'SEARCH_ONCE'});assert.equal(h.posts.length,1);
});
test('Expired queued messages are dropped on Discord retry',async()=>{
  const h=await harness();h.store.history=[{id:'old',createdAt:Date.now()-3600000,spawn:{...h.spawn,ttlSeconds:5},discordStatus:'pending',nextRetryAt:0}];
  h.listeners.alarm({name:'pogo-discord-retry'});await h.until(()=>h.store.history[0].discordStatus==='expired');assert.equal(h.posts.length,0);
});
test('Uncertain in-flight Discord POST is never blindly repeated on startup',async()=>{
  const h=await harness();h.store.history=[{id:'x',discordStatus:'sending',spawn:h.spawn}];
  h.listeners.startup();await h.until(()=>h.store.history[0].discordStatus==='uncertain');assert.equal(h.posts.length,0);
});
test('Messages from content scripts cannot trigger Discord or read settings',async()=>{
  const h=await harness();let replied=false;
  assert.equal(h.listeners.message({type:'TEST_DISCORD'},{id:'test',tab:{id:11},url:'https://pogocoordinates.com/search'},()=>replied=true),undefined);
  assert.equal(replied,false);assert.equal(h.posts.length,0);
});
test('Page reload or external filter change pauses scheduled search before reading another result',async()=>{
  const h=await harness();h.store.run={running:true,id:'a',tabId:11,filterSignature:JSON.stringify([['Pokemon','Bulbasaur']])};
  h.listeners.alarm({name:'pogo-search'});await h.until(()=>!h.store.run.running);
  assert.equal(h.searches,0);assert.match(h.store.status,/Bộ lọc/);
});
test('Network failure after POST is marked uncertain, never automatically resent',async()=>{
  const h=await harness({networkFail:true});await h.rpc({type:'SEARCH_ONCE'});
  assert.equal(h.store.history[0].discordStatus,'uncertain');await h.rpc({type:'SEARCH_ONCE'});assert.equal(h.posts.length,1);
});
test('Panel opened in a browser tab remains an authorized message sender',async()=>{
  const h=await harness();
  const result=await new Promise(resolve=>h.listeners.message({type:'STATE'},{id:'test',tab:{id:50},url:'chrome-extension://test/panel.html'},resolve));
  assert.equal(result.ok,true);assert.equal(result.value.settings.trainerCode,'123456789012');
});

test('Post-login homepage recovers Search while OAuth callback and loading page are untouched',async()=>{
  const home=await harness({tabUrl:'https://pogocoordinates.com/'});
  assert.equal((await home.rpc({type:'STATE'})).value.site.loggedIn,true);
  for(const tabUrl of ['https://pogocoordinates.com/callback','https://accounts.google.com/o/oauth2/auth']){
    const pending=await harness({tabUrl});assert.equal((await pending.rpc({type:'STATE'})).value.site,null);
  }
  const loading=await harness({tabUrl:'https://pogocoordinates.com/',tabStatus:'loading'});
  assert.equal((await loading.rpc({type:'STATE'})).value.site,null);
});

test('Clear history stops the run and resets deduplication without losing settings',async()=>{
  const h=await harness();await h.rpc({type:'SEARCH_ONCE'});assert.equal(h.posts.length,2);
  const settings=structuredClone(h.store.settings);h.store.run={running:true,id:'test'};
  assert.equal((await h.rpc({type:'CLEAR_HISTORY'})).ok,true);
  assert.deepEqual(h.store.history,[]);assert.deepEqual(h.store.seen,{});assert.deepEqual(h.store.settings,settings);
  assert.equal(h.store.run.running,false);assert.equal(h.store.lastSearchAt,null);
  await h.rpc({type:'SEARCH_ONCE'});assert.equal(h.posts.length,4);
});
test('Clear history rejects while a search is in flight',async()=>{
  const h=await harness({searchDelay:100});const pending=h.rpc({type:'SEARCH_ONCE'});await h.until(()=>h.searches===1);
  assert.equal((await h.rpc({type:'CLEAR_HISTORY'})).ok,false);await pending;assert.equal(h.store.history.length,1);
});

test('Coordinate rate limit retries only the second message without repeating the information',async()=>{
 const h=await harness({discord429At:2});await h.rpc({type:'SEARCH_ONCE'});
 assert.equal(h.posts.length,2);assert.equal(h.store.history[0].discordInfoSent,true);
 assert.equal(h.store.history[0].discordStatus,'pending');assert.equal(h.store.history[0].discordPart,'coords');
 h.store.history[0].nextRetryAt=0;h.listeners.alarm({name:'pogo-discord-retry'});
 await h.until(()=>h.store.history[0].discordStatus==='sent');
 assert.equal(h.posts.length,3);assert.deepEqual(h.posts[2].body,{content:h.spawn.coords,allowed_mentions:{parse:[]}});
 assert.equal(h.posts.filter(p=>p.body.embeds).length,1);
});

test('Uncertain coordinate delivery is not repeated automatically and manual retry skips information',async()=>{
 const h=await harness({networkFailAt:2});await h.rpc({type:'SEARCH_ONCE'});
 const event=h.store.history[0];assert.equal(event.discordStatus,'uncertain');assert.equal(event.discordInfoSent,true);
 await h.rpc({type:'SEARCH_ONCE'});assert.equal(h.posts.length,2);
 await h.rpc({type:'RETRY_DISCORD',id:event.id});assert.equal(h.posts.length,3);
 assert.deepEqual(h.posts[2].body,{content:h.spawn.coords,allowed_mentions:{parse:[]}});
 assert.equal(h.store.history[0].discordStatus,'sent');
});
