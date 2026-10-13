(function (root) {
  "use strict";
  const defaults = {intervalSeconds: 60, durationMinutes: 0, trainerCode: "", webAlerts: true,
    discordEnabled: false, webhook: "", ivTop: 100, speciesTop: 100, rankRule: "both", maxLevel: 50, minIv: 0};
  const normalize = s => String(s || "").replace(/♀|[_ -]female/gi,"f").replace(/♂|[_ -]male/gi,"m").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/alola\b/g, "alolan").replace(/galar\b/g, "galarian")
    .replace(/hisui\b/g, "hisuian").replace(/paldea\b/g, "paldean").replace(/[^a-z0-9]/g, "");
  function validateSettings(raw) {
    const s = {...defaults, ...raw};
    s.trainerCode = String(s.trainerCode).replace(/[\s-]/g, "");
    if (!/^\d{12}$/.test(s.trainerCode)) throw Error("Nhập mã bạn bè gồm đúng 12 số.");
    for (const [key, min, max] of [["intervalSeconds",30,86400],["durationMinutes",0,10080],
      ["ivTop",1,4096],["speciesTop",1,10000]]) {
      s[key] = Number(s[key]);
      if (!Number.isFinite(s[key]) || !Number.isInteger(s[key]) || s[key] < min || s[key] > max)
        throw Error(`${key}: nhập số nguyên từ ${min} đến ${max}.`);
    }
    if (![40,50,51].includes(Number(s.maxLevel))) throw Error("Giới hạn level không hợp lệ.");
    if (![0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15].includes(Number(s.minIv))) throw Error("IV tối thiểu không hợp lệ.");
    if (!["both","iv","species"].includes(s.rankRule)) throw Error("Quy tắc PvP không hợp lệ.");
    s.maxLevel = Number(s.maxLevel); s.minIv = Number(s.minIv);
    s.webhook = String(s.webhook || "").trim();
    if (s.discordEnabled) validateWebhook(s.webhook);
    return s;
  }
  function validateWebhook(url) {
    if (!/^https:\/\/discord\.com\/api\/webhooks\/\d+\/[A-Za-z0-9_-]+$/.test(url))
      throw Error("Webhook phải là https://discord.com/api/webhooks/ID/TOKEN (không có query).");
    return url;
  }
  function parseCard(text) {
    const lines = String(text).split(/\n/).map(s=>s.trim()).filter(Boolean);
    const dexLine = lines.findIndex(s=>/^#\s*\d+/.test(s));
    if (dexLine < 1) return null;
    const parts = lines[dexLine].split(/\s*·\s*/);
    const at = label => {const i=lines.findIndex(s=>s.toLowerCase()===label.toLowerCase()); return i<0?"":lines[i+1]||"";};
    const ivText = at("IV"), iv = ivText.match(/\((\d+)\s*\/\s*(\d+)\s*\/\s*(\d+)\)/);
    const fullName = lines[dexLine-1], form = fullName.match(/\(([^)]+)\)/)?.[1] || "";
    const coord = lines.find(s=>/^-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+$/.test(s));
    const ttl = at("Despawn").split(":").map(Number);
    return {name: fullName.replace(/\s*\([^)]+\)/g, "").trim(), fullName, form,
      dex:Number(parts[0].replace(/\D/g,"")), gender:parts[1]||"", size:parts[2]||"",
      moves: lines[dexLine+1] || "", cp:Number(at("CP")), level:Number(at("LVL")), ivPercent:Number(ivText.match(/(\d+)%/)?.[1]),
      iv:iv?iv.slice(1).map(Number):null, location:at("Location"), despawn:at("Despawn"),
      ttlSeconds:ttl.length===2&&ttl.every(Number.isFinite)?ttl[0]*60+ttl[1]:null,
      coords:coord?.replace(/\s/g,"")||"", raw:lines.join("\n")};
  }
  function matchThreshold(candidate, settings) {
    const iv = Number.isInteger(candidate.ivRank) && candidate.ivRank >= 1 && candidate.ivRank <= settings.ivTop;
    const species = Number.isInteger(candidate.speciesRank) && candidate.speciesRank >= 1 && candidate.speciesRank <= settings.speciesTop;
    return settings.rankRule === "iv" ? iv : settings.rankRule === "species" ? species : iv && species;
  }
  function eventKey(spawn) {
    if (!spawn.coords) throw Error("Thiếu tọa độ để nhận diện spawn.");
    return [spawn.dex,spawn.form,spawn.coords,spawn.cp,spawn.iv?.join("/")].join("|");
  }
  function discordPayload(event) {
    const s=event.spawn, p=event.mode==='pvp'?event.pvp:null;
    const copyName=String(s.fullName||s.name||'').replace(/`/g,'').replace(/[\r\n]+/g,' ').slice(0,256);
    const lines=['```\n'+copyName+'\n```',`IV ${s.ivPercent}% (${s.iv?.join('/')||'?'})`];
    if(p){
      const cap=/ultra|2500/i.test(p.league)?2500:1500;
      lines.push(`**${p.league} (${cap}) · ${p.speciesName}: IV #${p.ivRank??'?'} · PvPoke #${p.speciesRank??'?'}**`);
    }else lines.push(`CP ${s.cp} · LV ${s.level}`);
    if(Number.isFinite(event.createdAt)&&Number.isFinite(s.ttlSeconds)&&s.ttlSeconds>0){
      const despawnAt=Math.floor((event.createdAt+s.ttlSeconds*1000)/1000);
      lines.push(`⏳ Despawn: <t:${despawnAt}:T> · <t:${despawnAt}:R>`);
    }else if(s.despawn){
      lines.push(`⏳ Despawn: ${s.despawn} lúc phát hiện`);
    }else lines.push('⏳ Despawn: chưa có thông tin');
    const thumbnail=Number.isInteger(s.dex)&&s.dex>0
      ?{url:`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${s.dex}.png`}:undefined;
    return {allowed_mentions:{parse:[]},embeds:[{title:`${s.fullName} #${s.dex}`.slice(0,256),
      url:`https://www.google.com/maps?q=${encodeURIComponent(s.coords)}`,color:p?0x8b5cf6:0x22c55e,
      thumbnail,description:lines.join('\n').slice(0,4096)}]};
  }
  function discordCoordinatePayload(event) {
    return {content:event.spawn.coords,allowed_mentions:{parse:[]}};
  }
  root.PogoCore = {defaults,normalize,validateSettings,validateWebhook,parseCard,matchThreshold,eventKey,discordPayload,discordCoordinatePayload};
})(globalThis);
