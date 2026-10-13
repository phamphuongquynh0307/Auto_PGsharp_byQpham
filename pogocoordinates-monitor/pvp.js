import './core.js';
const {normalize,matchThreshold} = globalThis.PogoCore;
export class PvpEngine {
  constructor(data) {
    this.data=data; this.byId=new Map(data.pokemon.map(p=>[p.speciesId,p])); this.tables=new Map();
    this.ranks=Object.fromEntries(Object.entries(data.rankings).map(([k,v])=>[k,new Map(v.map(p=>[p.speciesId,p]))]));
  }
  resolve(spawn) {
    const candidates=this.data.pokemon.filter(p=>p.dex===spawn.dex&&!/_shadow|_mega|_primal/.test(p.speciesId));
    const normal=!spawn.form||/^(normal|unset)$/i.test(spawn.form);
    const target=normalize(normal?spawn.name:`${spawn.name} (${spawn.form})`);
    return candidates.find(p=>normalize(p.speciesName)===target) || null;
  }
  evolutions(p,include) {
    const result=[], seen=new Set();
    const walk=x=>{if(!x||seen.has(x.speciesId))return;seen.add(x.speciesId);result.push(x);
      if(include) for(const id of x.family?.evolutions||[]) walk(this.byId.get(id));};
    walk(p); return result.filter(x=>x.released!==false&&!/_shadow|_mega|_primal/.test(x.speciesId));
  }
  speciesRanking(spawn,league='great',includeEvolutions=false) {
    if(!['great','ultra'].includes(league))return null;
    const species=this.resolve(spawn);if(!species)return null;
    return this.evolutions(species,includeEvolutions).map(p=>{
      const rank=this.ranks[league]?.get(p.speciesId)?.rank;
      return Number.isInteger(rank)&&rank>0?{speciesName:p.speciesName,speciesRank:rank}:null;
    }).filter(Boolean).sort((a,b)=>a.speciesRank-b.speciesRank)[0]||null;
  }
  bestStats(p,ivs,cap,maxLevel) {
    const base=p.baseStats, maxIndex=Math.min(this.data.cpm.length-1,(maxLevel-1)*2);
    const cpAt=i=>Math.max(10,Math.floor((base.atk+ivs[0])*Math.sqrt(base.def+ivs[1])*Math.sqrt(base.hp+ivs[2])*this.data.cpm[i]**2/10));
    if(cpAt(0)>cap)return null;
    let low=0,high=maxIndex;
    while(low<high){const mid=Math.ceil((low+high)/2);if(cpAt(mid)<=cap)low=mid;else high=mid-1;}
    const cpm=this.data.cpm[low], attack=(base.atk+ivs[0])*cpm, defense=(base.def+ivs[1])*cpm,
      hp=Math.max(10,Math.floor((base.hp+ivs[2])*cpm));
    return {cp:cpAt(low),level:1+low/2,product:attack*defense*hp,attack,defense,hp};
  }
  ivTable(p,cap,maxLevel,minIv) {
    const key=[p.speciesId,cap,maxLevel,minIv].join('|');
    if(this.tables.has(key))return this.tables.get(key);
    const entries=[];
    for(let a=minIv;a<=15;a++)for(let d=minIv;d<=15;d++)for(let h=minIv;h<=15;h++){
      const stats=this.bestStats(p,[a,d,h],cap,maxLevel);if(stats)entries.push({key:`${a}/${d}/${h}`,...stats});
    }
    entries.sort((a,b)=>b.product-a.product);
    const table=new Map();let rank=0,previous=null;
    entries.forEach((e,i)=>{if(previous===null||Math.abs(e.product-previous)>1e-8)rank=i+1;
      table.set(e.key,{...e,rank,productPercent:e.product/entries[0].product*100});previous=e.product;});
    // Bound memory when following many species for days.
    if(this.tables.size>=250)this.tables.delete(this.tables.keys().next().value);
    this.tables.set(key,table);return table;
  }
  evaluate(spawn,settings,league='great',includeEvolutions=true) {
    if(!['great','ultra'].includes(league))return {matches:[],error:'League không được hỗ trợ.'};
    if(!spawn.iv||spawn.iv.length!==3||spawn.iv.some(n=>!Number.isInteger(n)||n<settings.minIv||n>15))
      return {matches:[],error:'Thiếu bộ ba IV chính xác hoặc IV dưới sàn đã chọn.'};
    const p=this.resolve(spawn);if(!p)return {matches:[],error:`PvPoke chưa ánh xạ được ${spawn.fullName}; không đoán form.`};
    const cap=league==='great'?1500:2500, matches=[];
    for(const species of this.evolutions(p,includeEvolutions)){
      const iv=this.ivTable(species,cap,settings.maxLevel,settings.minIv).get(spawn.iv.join('/'));
      // Pokémon cannot be powered down, including when evaluating a future evolution.
      if(!iv||iv.level<spawn.level)continue;
      const meta=this.ranks[league]?.get(species.speciesId);
      const candidate={speciesId:species.speciesId,speciesName:species.speciesName,league:league==='great'?'Great League':'Ultra League',
        ivRank:iv.rank,speciesRank:meta?.rank??null,score:meta?.score??null,cp:iv.cp,level:iv.level,
        productPercent:iv.productPercent,maxLevel:settings.maxLevel,minIv:settings.minIv,dataDate:this.data.fetchedAt.slice(0,10)};
      if(matchThreshold(candidate,settings))matches.push(candidate);
    }
    matches.sort((a,b)=>(a.speciesRank??Infinity)-(b.speciesRank??Infinity)||a.ivRank-b.ivRank);
    return {matches,error:null};
  }
}
