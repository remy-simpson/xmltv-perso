let state={sources:[],programs:[],errors:[]}, editing=null;
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'});
function dayKey(d){const parts=day.formatToParts(new Date(d));return ['year','month','day'].map(k=>parts.find(p=>p.type===k).value).join('-')}
$('#day').value=dayKey(new Date());
let favorites;try{favorites=JSON.parse(localStorage.getItem('onde-favorites')||'[]')}catch{favorites=[]}
function message(text){$('#notice').textContent=text}
async function api(path,data){const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const result=await response.json();if(!response.ok)throw Error(result.error||'Erreur du serveur');return result}
function view(name){document.querySelectorAll('.view').forEach(x=>x.hidden=x.id!==name);document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('active',x.dataset.view===name));$('#breadcrumb').textContent={guide:'GUIDE',channels:'SOURCES',exports:'EXPORT'}[name]}
document.querySelectorAll('nav button').forEach(x=>x.onclick=()=>view(x.dataset.view));
function render(){
 $('#count-channels').textContent=state.sources.length;$('#count-programs').textContent=state.programs.length;
 $('#source-label').textContent=state.last_grab?'Dernière collecte : '+new Date(state.last_grab).toLocaleString('fr-FR'):'Aucune collecte effectuée';
 $('#channel-list').innerHTML=state.sources.map((s,i)=>`<div class="channel-item"><span class="logo">${esc(s.name.slice(0,2).toUpperCase())}</span><b>${esc(s.name)}</b><small>${esc(s.id)} · ${esc(s.mode)}<br><span>${esc(s.url)}</span></small><button data-edit="${i}">Modifier</button><button data-delete="${i}">Supprimer</button></div>`).join('')||'<p class="empty">Ajoutez votre première source pour commencer.</p>';
 document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>{const s=state.sources[+b.dataset.edit];editing=s.id;for(const el of $('#add-channel').elements)if(el.name)el.value=s[el.name]||'';$('#cancel-edit').hidden=false;$('#add-channel').scrollIntoView({behavior:'smooth'})});
 document.querySelectorAll('[data-delete]').forEach(b=>b.onclick=async()=>{if(!confirm('Supprimer cette source et ses programmes ?'))return;try{state=await api('/api/sources',{sources:state.sources.filter((_,i)=>i!==+b.dataset.delete)});render()}catch(e){message(e.message)}});
 const query=$('#search').value.toLocaleLowerCase('fr');
 const rows=state.sources.filter(s=>!$('#favorites').checked||favorites.includes(s.id)).map(s=>{const programs=state.programs.filter(p=>p.channel===s.id&&dayKey(p.start)===$('#day').value&&(s.name+' '+p.title).toLocaleLowerCase('fr').includes(query)).sort((a,b)=>new Date(a.start)-new Date(b.start));if(query&&!programs.length&&!s.name.toLocaleLowerCase('fr').includes(query))return '';return `<div class="program-row"><div class="channel"><button class="star" data-star="${esc(s.id)}" aria-label="Favori ${esc(s.name)}">${favorites.includes(s.id)?'★':'☆'}</button><span class="logo">${esc(s.name.slice(0,2).toUpperCase())}</span><b>${esc(s.name)}</b></div><div class="cards">${programs.map(p=>`<article class="program"><time>${esc(new Date(p.start).toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Paris'}))} — ${esc(new Date(p.stop).toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Paris'}))}</time><h3>${esc(p.title)}</h3><p>${esc(p.description)}</p></article>`).join('')||'<p class="muted">Aucun programme pour cette date.</p>'}</div></div>`}).join('');
 $('#programs').innerHTML=rows||'<div class="empty">Votre guide commence ici. Ajoutez une source dans « Sources & chaînes », puis lancez une collecte.</div>';
 document.querySelectorAll('[data-star]').forEach(b=>b.onclick=()=>{favorites=favorites.includes(b.dataset.star)?favorites.filter(id=>id!==b.dataset.star):[...favorites,b.dataset.star];localStorage.setItem('onde-favorites',JSON.stringify(favorites));render()});
}
$('#search').oninput=render;$('#day').onchange=render;$('#favorites').onchange=render;
function cancel(){editing=null;$('#add-channel').reset();$('#cancel-edit').hidden=true}
$('#cancel-edit').onclick=cancel;
$('#add-channel').onsubmit=async e=>{e.preventDefault();const source=Object.fromEntries(new FormData(e.target));const sources=editing?state.sources.map(s=>s.id===editing?source:s):[...state.sources,source];try{state=await api('/api/sources',{sources});cancel();render();message('Source enregistrée. Lancez une collecte pour tester sa configuration.')}catch(e){message(e.message)}};
$('#import-top').onclick=async()=>{if(!state.sources.length){view('channels');message('Ajoutez une source avant de lancer la récupération.');return}const button=$('#import-top');button.disabled=true;button.textContent='Collecte en cours…';message('Récupération des programmes auprès des sources configurées…');try{state=await api('/api/grab',{});render();message(state.errors.length?state.errors.map(e=>e.source+' : '+e.error).join(' | '):'Collecte terminée. Le guide XMLTV est disponible.')}catch(e){message(e.message)}finally{button.disabled=false;button.textContent='↻ Récupérer les programmes'}};
$('#feed-url').textContent=location.origin+'/guide.xml';
api('/api/state').then(s=>{state=s;render()}).catch(e=>message('Chargement impossible : '+e.message));
