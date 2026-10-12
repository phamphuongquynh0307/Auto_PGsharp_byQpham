// Only public JSON and a numerical CPM table are bundled. No remote JS is executed.
import {mkdir, writeFile} from 'node:fs/promises';
const base='https://raw.githubusercontent.com/pvpoke/pvpoke/master/';
async function get(path,json=true) {
  const r=await fetch(base+path); if(!r.ok) throw Error(`${path}: HTTP ${r.status}`);
  return json?r.json():r.text();
}
const [gm, great, ultra, pokemonSource, license] = await Promise.all([
  get('src/data/gamemaster.json'), get('src/data/rankings/all/overall/rankings-1500.json'),
  get('src/data/rankings/all/overall/rankings-2500.json'), get('src/js/pokemon/Pokemon.js',false),get('LICENSE',false)
]);
const cpmText=pokemonSource.match(/var cpms = (\[[\d\s.,]+\])/);
if(!cpmText) throw Error('CPM table missing');
const cpm=JSON.parse(cpmText[1]); if(cpm.length<101) throw Error('CPM table incomplete');
const compact=d=>d.map((p,i)=>({speciesId:p.speciesId,speciesName:p.speciesName,rank:i+1,score:p.score,moveset:p.moveset}));
const data={fetchedAt:new Date().toISOString(),timestamp:gm.timestamp,source:base,
  cpm,pokemon:gm.pokemon.map(p=>({dex:p.dex,speciesId:p.speciesId,speciesName:p.speciesName,baseStats:p.baseStats,
    family:p.family,released:p.released,types:p.types})), rankings:{great:compact(great),ultra:compact(ultra)}};
await mkdir(new URL('./data/',import.meta.url),{recursive:true});
await writeFile(new URL('./data/pvpoke.json',import.meta.url),JSON.stringify(data));
await writeFile(new URL('./data/PVPOKE-LICENSE.txt',import.meta.url),license);
console.log(`Bundled ${data.pokemon.length} species; GL ${great.length}, UL ${ultra.length}; ${data.fetchedAt}`);
