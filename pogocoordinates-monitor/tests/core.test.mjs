import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import '../core.js';
import {PvpEngine} from '../pvp.js';
const C=globalThis.PogoCore;
const data=JSON.parse(await readFile(new URL('../data/pvpoke.json',import.meta.url),'utf8'));
const engine=new PvpEngine(data),settings={...C.defaults,trainerCode:'123456789012'};
const card=`Pikachu\n#025 · Male · M\nThunder Shock / Discharge\nCP\n474\nLVL\n18\nIV\n93% (14/14/14)\nLocation\nPasay, Philippines\nDespawn\n52:04\nOpen in Maps\n14.538988,121.004883`;
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
test('Discord mobile Copy Text contains only coordinates for Stats and PvP',()=>{
  const spawn=C.parseCard(card),pvp={league:'Ultra League',speciesName:'Raichu',ivRank:2,speciesRank:30};
  for(const mode of ['stats','pvp']){
    const payload=C.discordPayload({spawn,pvp,mode,createdAt:1700000000000,filters:{Pokemon:'Pikachu'}});
    assert.deepEqual(payload,{content:'14.538988,121.004883',allowed_mentions:{parse:[]}});
  }
  assert.throws(()=>C.eventKey({...spawn,coords:''}));
});

test('Discord retries preserve the coordinate-only message',()=>{
  const event={spawn:{...C.parseCard(card),coords:'-33.865143,151.209900'},mode:'stats',createdAt:1700000000000};
  const original=C.discordPayload(event);
  const retried=C.discordPayload({...event,attempts:3,nextRetryAt:event.createdAt+120000});
  assert.deepEqual(original,retried);
  assert.equal(original.content,'-33.865143,151.209900');
});
