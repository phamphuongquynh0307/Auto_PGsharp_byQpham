// Local visual QA only. No real account, searches, or Discord requests are made.
import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
const root=new URL('../',import.meta.url);
const html=await readFile(new URL('./fixtures/stats.html',import.meta.url),'utf8');
const dom=new JSDOM(html,{url:'https://pogocoordinates.com/search',runScripts:'outside-only'}),w=dom.window;
for(const a of w.document.querySelectorAll('nav a'))if(/Login/.test(a.textContent))a.remove();
Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent.trim();}});
let listener;
w.chrome={runtime:{id:'preview',onMessage:{addListener:fn=>listener=fn}},storage:{session:{get:async()=>({trainerCode:'123456789012'})}}};
w.eval(await readFile(new URL('core.js',root),'utf8'));w.eval(await readFile(new URL('content.js',root),'utf8'));
const site=(await new Promise(r=>listener({type:'PAGE_STATE'},{id:'preview'},r))).value;
const settings={...w.PogoCore.defaults,trainerCode:'123456789012'};
const mock=`window.chrome={runtime:{sendMessage:async m=>{
  let s=window.previewState;
  if(m.type==='STATE')return {ok:true,value:s};
  if(m.type==='SAVE'){s.settings=m.settings;return {ok:true,value:m.settings};}
  if(m.type==='START'){s.run={running:true};s.status='PREVIEW: lịch Search đã bật (không gửi yêu cầu thật)';return {ok:true,value:s.run};}
  if(m.type==='STOP'){s.run={running:false};s.status='PREVIEW: đã dừng';return {ok:true,value:true};}
  if(m.type==='OPEN_SITE')return {ok:true,value:1};
  if(m.type==='EDIT')return {ok:true,value:s.site};
  return {ok:true,value:true};
}}};window.previewState=${JSON.stringify({site,settings,run:{running:false},history:[],status:'Bản xem thử giao diện · dữ liệu mẫu · chưa bật lịch',tabId:1})};`;
const files=new Set(['panel.html','panel.css','panel.js','core.js']);
const server=http.createServer(async(req,res)=>{
  const path=new URL(req.url,'http://localhost').pathname.slice(1)||'panel.html';
  if(path==='preview-mock.js'){res.setHeader('Content-Type','text/javascript');res.end(mock);return;}
  if(!files.has(path)){res.writeHead(404);res.end();return;}
  let content=await readFile(new URL(path,root));
  if(path==='panel.html')content=content.toString().replace('<script src="core.js">','<script src="preview-mock.js"></script><script src="core.js">');
  res.setHeader('Content-Type',path.endsWith('.css')?'text/css':path.endsWith('.js')?'text/javascript':'text/html');res.end(content);
});
server.listen(8769,'127.0.0.1',()=>console.log('QA preview: http://127.0.0.1:8769/panel.html'));
