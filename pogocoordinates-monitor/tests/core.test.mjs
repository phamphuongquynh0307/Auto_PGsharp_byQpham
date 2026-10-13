import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import '../core.js';
import {PvpEngine} from '../pvp.js';
const C=globalThis.PogoCore;
const data=JSON.parse(await readFile(new URL('../data/pvpoke.json',import.meta.url),'utf8'));
const engine=new PvpEngine(data),settings={...C.defaults,trainerCode:'123456789012'};
const card=`Pikachu\n#025 · Male · M\nThunder Shock / Discharge\nCP\n474\nLVL\n18\nIV\n93% (14/14/14)\nLocation\nPasay, Philippines\nDespawn\n52:04\nOpen in Maps\n14.538988,121.004883`;
test('Web species rank follows league and includes evolutions only when requested',()=>{
 const spawn={dex:821,name:'Rookidee',form:''};
 assert.equal(engine.speciesRanking(spawn,'great',false),null);
 const own=engine.speciesRanking({dex:184,name:'Azumarill',form:''},'great',false);
 assert.equal(own.speciesName,'Azumarill');
 assert.equal(own.speciesRank,engine.ranks.great.get('azumarill').rank);
 const evolved=engine.speciesRanking(spawn,'great',true);
 assert.equal(evolved.speciesRank,Math.min(...engine.evolutions(engine.resolve(spawn),true).map(p=>engine.ranks.great.get(p.speciesId)?.rank||Infinity)));
 assert.equal(engine.speciesRanking({dex:25,name:'Pikachu',form:'Unknown Costume'},'great',true),null);
 assert.equal(engine.speciesRanking(spawn,'master',true),null);
 assert.equal(engine.speciesRanking(spawn,'ultra',false)?.speciesRank,engine.ranks.ultra.get('rookidee')?.rank);
});
test('Parse full real card data, including coordinates and exact IVs',()=>{
  const p=C.parseCard(card);assert.deepEqual(p.iv,[14,14,14]);assert.equal(p.dex,25);assert.equal(p.cp,474);
  assert.equal(p.coords,'14.538988,121.004883');assert.equal(p.ttlSeconds,3124);assert.equal(p.gender,'Male');
});
test('Friend code required, interval cannot be below MV3 alarm minimum, webhook host restricted',()=>{
  assert.throws(()=>C.validateSettings({...settings,trainerCode:'123'}));
  assert.throws(()=>C.validateSettings({...settings,intervalSeconds:5}));
  assert.throws(()=>C.validateSettings({...settings,discordEnabled:true,webhook:'https://example.com/api/webhooks/1/abc'}));
  assert.throws(()=>C.validateWebhook('https://discord.com/api/webhooks/1/abc?redirect=https://evil.test'));
  assert.equal(C.validateSettings({...settings,trainerCode:'1234 5678 9012'}).trainerCode,'123456789012');
});
test('Top N is inclusive, rank 1 best, and both criteria must match the same candidate',()=>{
  assert.equal(C.matchThreshold({ivRank:100,speciesRank:100},settings),true);
  assert.equal(C.matchThreshold({ivRank:101,speciesRank:1},settings),false);
  assert.equal(C.matchThreshold({ivRank:1,speciesRank:null},settings),false);
  assert.equal(C.matchThreshold({ivRank:0,speciesRank:1},settings),false);
});
test('Normal and regional forms resolve separately; unknown costume never maps to normal',()=>{
  assert.equal(engine.resolve({dex:26,name:'Raichu',form:'Alola'}).speciesId,'raichu_alolan');
  assert.equal(engine.resolve({dex:26,name:'Raichu',form:''}).speciesId,'raichu');
  assert.equal(engine.resolve({dex:25,name:'Pikachu',form:'Unknown Costume'}),null);
});
test('4096 combinations are ranked at level 50, rank 1 follows maximum stat product',()=>{
  const p=engine.byId.get('azumarill'),table=engine.ivTable(p,1500,50,0);
  assert.equal(table.size,4096);const values=[...table.values()],best=values.find(v=>v.rank===1);
  assert.equal(best.key,'0/15/15');assert.equal(best.cp,1499);assert.equal(best.level,45.5);
  assert.equal(best.productPercent,100);assert.ok(values.every(v=>v.cp<=1500&&v.level<=50));
});
test('Level cap and IV floor are part of the ranking basis',()=>{
  const p=engine.byId.get('azumarill');assert.equal(engine.ivTable(p,1500,40,10).size,216);
  assert.equal(engine.ivTable(p,1500,40,10).has('0/15/15'),false);
  assert.notEqual(engine.ivTable(p,1500,40,0).get('0/15/15').rank,engine.ivTable(p,1500,50,0).get('0/15/15').rank);
});
test('Previous evolution enabled evaluates future forms and rejects a Pokémon above legal level',()=>{
  const spawn={dex:183,name:'Marill',fullName:'Marill',form:'',iv:[0,15,15],level:5};
  const s={...settings,ivTop:1,speciesTop:10000};
  assert.ok(engine.evaluate(spawn,s,'great',true).matches.some(m=>m.speciesId==='azumarill'));
  assert.ok(!engine.evaluate(spawn,s,'great',false).matches.some(m=>m.speciesId==='azumarill'));
  assert.equal(engine.evaluate({...spawn,level:50},s,'great',true).matches.length,0);
});
test('Missing IVs and unsupported forms fail closed',()=>{
  assert.equal(engine.evaluate({...C.parseCard(card),iv:null},settings).matches.length,0);
  assert.ok(engine.evaluate({...C.parseCard(card),form:'Unknown Costume'},settings).error);
});
test('No cross-evolution mixing of IV rank and PvPoke species rank',()=>{
  const fake={...data,pokemon:[{dex:1,speciesId:'a',speciesName:'A',baseStats:{atk:100,def:100,hp:100},family:{evolutions:['b']}},
    {dex:2,speciesId:'b',speciesName:'B',baseStats:{atk:200,def:100,hp:100}}],rankings:{great:[{speciesId:'a',rank:200},{speciesId:'b',rank:1}],ultra:[]}};
  const e=new PvpEngine(fake);e.ivTable=p=>new Map([['0/15/15',{rank:p.speciesId==='a'?1:200,level:30,cp:1499,productPercent:100}]]);
  assert.equal(e.evaluate({dex:1,name:'A',form:'',iv:[0,15,15],level:1},settings,'great',true).matches.length,0);
});
test('Discord summary contains coordinates and ranks without filters, attachments or secrets',()=>{
  const event={spawn:C.parseCard(card),mode:'pvp',filters:{Pokemon:'Pikachu',League:'Great League'},createdAt:Date.now(),
    pvp:{league:'Great League',speciesName:'Raichu',ivRank:20,speciesRank:90,cp:1499,level:28,productPercent:99.5,maxLevel:50,minIv:0,dataDate:'2026-10-12'}};
  const payload=C.discordPayload(event);assert.deepEqual(payload.allowed_mentions,{parse:[]});assert.equal(payload.content,event.spawn.coords);
  assert.match(payload.embeds[0].description,/\*\*Great League \(1500\) · Raichu: IV #20 · PvPoke #90\*\*/);
  assert.match(payload.embeds[0].description,/```\n14\.538988,121\.004883\n```/);
  assert.match(payload.embeds[0].description,/```\nPikachu\n```/);
  const despawnAt=Math.floor((event.createdAt+3124*1000)/1000);
  assert.ok(payload.embeds[0].description.includes(`Despawn: <t:${despawnAt}:T> · <t:${despawnAt}:R>`));
  assert.match(payload.embeds[0].thumbnail.url,/\/25\.png$/);
  const body=JSON.stringify(payload);for(const value of ['14.538988','14/14/14','Pikachu','Raichu','IV #20']){
    assert.ok(body.includes(value),value);
  }
  assert.ok(!body.includes('Pokemon: Pikachu'));assert.ok(!body.includes('Stat product'));assert.ok(body.length<700);
  assert.ok(!body.includes(settings.trainerCode));assert.throws(()=>C.eventKey({...event.spawn,coords:''}));
});
test('Discord Ultra shows 2500; Stats omits all ranks, league and long context',()=>{
  const spawn=C.parseCard(card),pvp={league:'Ultra League',speciesName:'Raichu',ivRank:2,speciesRank:30};
  const ultra=C.discordPayload({spawn,pvp,mode:'pvp'}).embeds[0];assert.match(ultra.description,/\*\*Ultra League \(2500\)/);
  const stats=C.discordPayload({spawn,pvp,mode:'stats'}).embeds[0];
  assert.match(stats.description,/CP 474 · LV 18/);assert.match(stats.description,/```\n/);
  assert.ok(!/hạng|PvP|League|Pasay/i.test(stats.description));
  assert.match(stats.description,/Despawn: 52:04 lúc phát hiện/);
  assert.ok(stats.thumbnail);assert.ok(stats.description.length<200);
});

test('Queued Discord alerts keep their original despawn deadline after retries',()=>{
  const event={spawn:C.parseCard(card),mode:'stats',createdAt:1700000000000};
  const original=C.discordPayload(event).embeds[0].description;
  const retried=C.discordPayload({...event,attempts:3,nextRetryAt:event.createdAt+120000}).embeds[0].description;
  assert.equal(original,retried);
  assert.match(original,/Despawn: <t:1700003124:T> · <t:1700003124:R>/);
  const unknown=C.discordPayload({spawn:{...event.spawn,ttlSeconds:null,despawn:''},mode:'stats',createdAt:event.createdAt});
  assert.match(unknown.embeds[0].description,/Despawn: chưa có thông tin/);
  assert.ok(!unknown.embeds[0].description.includes('<t:'));
});

test('Mobile Copy Text uses raw coordinates while rich information stays in the embed',()=>{
 const spawn={...C.parseCard(card),coords:'-33.865143,151.209900'};
 for(const mode of ['stats','pvp']){
  const payload=C.discordPayload({spawn,mode,pvp:{league:'Great League',speciesName:'Raichu',ivRank:20,speciesRank:90},createdAt:1700000000000});
  assert.equal(payload.content,'-33.865143,151.209900');
  assert.ok(!payload.content.includes(String(spawn.cp)));
  assert.equal(payload.embeds.length,1);
  assert.match(payload.embeds[0].title,/Pikachu/);
  assert.ok(payload.embeds[0].description.includes('IV 93% (14/14/14)'));
  assert.deepEqual(payload.allowed_mentions,{parse:[]});
 }
});
