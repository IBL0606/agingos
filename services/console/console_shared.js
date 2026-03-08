const LS_BASE='agingos_api_base',LS_KEY='agingos_api_key';
const NAV=[['index.html','Oversikt'],['events.html','Hendelser'],['alarms.html','Varsler'],['anomalies.html','Mulige avvik'],['proposals.html','Anbefalinger'],['report.html','Ukessammendrag'],['rooms.html','Rom og sensorer']];
const CACHE_PREFIX='agingos_cache_';
function nbase(v){v=(v||localStorage.getItem(LS_BASE)||'/api').trim();if(!v.startsWith('/'))v='/'+v;return v.replace(/\/+$/,'')||'/api'}
function key(){return (localStorage.getItem(LS_KEY)||'').trim()}
function setCfg(base,k){localStorage.setItem(LS_BASE,nbase(base));localStorage.setItem(LS_KEY,(k||'').trim())}
function fmtNo(ts){if(!ts)return '—';const d=new Date(ts);if(Number.isNaN(d.getTime()))return String(ts);return new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(d).replace(',', ' kl.')}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function statusMsg(container,msg,type=''){container.innerHTML=`<div class="notice ${type}">${esc(msg)}</div>`}
async function api(path,opts={}){const headers={...(opts.headers||{})};if(key())headers['X-API-Key']=key();if(opts.body && !headers['Content-Type'])headers['Content-Type']='application/json';const res=await fetch(nbase()+path,{...opts,headers});const txt=await res.text();let json=null;try{json=JSON.parse(txt)}catch{};if(!res.ok){const e=new Error((json&&json.detail)||txt||`HTTP ${res.status}`);e.status=res.status;e.raw=txt;throw e}return json}
function saveCache(name,data){localStorage.setItem(CACHE_PREFIX+name,JSON.stringify({updated_at:new Date().toISOString(),data}))}
function loadCache(name){try{return JSON.parse(localStorage.getItem(CACHE_PREFIX+name)||'null')}catch{return null}}
function pageShell(active,title){const mount=document.getElementById('shell');const links=NAV.map(([h,t])=>`<a class="${h===active?'active':''}" href="./${h}">${t}</a>`).join('');mount.innerHTML=`<div class="card"><h1>${title}</h1><div class="muted">AgingOS Console</div><div class="topnav">${links}</div><div class="row small" style="margin-top:8px"><span class="chip">API: ${esc(nbase())}</span><span class="chip">Nøkkel: ${key()?'lagt inn':'mangler'}</span><button class="btn secondary" id="openCfg">Koble til</button></div><div id="cfg" style="display:none;margin-top:8px" class="row"><input id="cfgBase" placeholder="/api" value="${esc(nbase())}"><input id="cfgKey" placeholder="API-nøkkel" value="${esc(key())}"><button class="btn" id="saveCfg">Lagre</button></div></div>`;
 document.getElementById('openCfg').onclick=()=>{const c=document.getElementById('cfg');c.style.display=c.style.display==='none'?'flex':'none'};
 document.getElementById('saveCfg').onclick=()=>{setCfg(document.getElementById('cfgBase').value,document.getElementById('cfgKey').value);location.reload()};
}
function failSoftBlock(cache){if(key())return '';let t='<div class="notice">Konsollen er ikke koblet til ennå. Legg inn nøkkel for å hente nye data.</div>';if(cache?.updated_at)t+=`<div class="notice small">Viser sist kjente data. Sist oppdatert: ${fmtNo(cache.updated_at)}. Ikke oppdatert nå.</div>`;return t}
function devDetails(obj){return `<details><summary>Vis tekniske detaljer</summary><pre>${esc(JSON.stringify(obj,null,2))}</pre></details>`}
