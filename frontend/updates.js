let updatePolling=false,updateActionBusy=false,updateNeedsPolling=false,updateLoadedCommit=null,updateObservedStart=null,rolloutObservedStart=null,agentPackageState={};
const updateLabels={idle:'Siap diperiksa',queued:'Dalam antrean',preparing:'Menyiapkan versi',stopping:'Menghentikan sementara',backup:'Membuat backup',installing:'Memasang pembaruan',verifying:'Memeriksa server',rolling_back:'Memulihkan versi lama',success:'Update berhasil',failed:'Update dibatalkan',rolled_back:'Versi lama dipulihkan',rollback_failed:'Pemulihan perlu diperiksa'};
const updateStages=[['queued','Antrean'],['preparing','Persiapan'],['stopping','Hentikan server'],['backup','Backup'],['installing','Pemasangan'],['verifying','Verifikasi']];
function updateElapsed(job){const start=Number(job.started_at||updateObservedStart||job.updated_at),end=['success','failed','rolled_back','rollback_failed'].includes(job.state)?Number(job.updated_at):Date.now()/1000;if(!Number.isFinite(start)||!Number.isFinite(end)||end<start)return '';const seconds=Math.floor(end-start),minutes=Math.floor(seconds/60);return `${String(minutes).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
function rolloutElapsed(rollout){if(!rollout)return '';const start=Number(rollout.started_at||rolloutObservedStart||rollout.updated_at),end=rollout.busy?Date.now()/1000:Number(rollout.updated_at||Date.now()/1000);if(!Number.isFinite(start)||!Number.isFinite(end)||end<start)return '00:00';const seconds=Math.floor(end-start),minutes=Math.floor(seconds/60);return `${String(minutes).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
function updateProgress(job,busy){if(!busy)return '';const current=updateStages.findIndex(([state])=>state===job.state),rollback=job.state==='rolling_back';return `<div class="update-progress" aria-label="Proses update sedang berjalan"><div class="update-progress-head"><span class="update-spinner" aria-hidden="true"></span><b>${rollback?'Pemulihan sedang berjalan':'Update sedang berjalan'}</b><span data-elapsed="app">Berjalan ${updateElapsed(job)||'00:00'}</span></div><ol>${updateStages.map(([state,label],index)=>`<li class="${rollback?'':index<current?'done':index===current?'active':''}"><i></i><span>${label}</span></li>`).join('')}</ol>${rollback?'<p>Versi baru gagal diperiksa. SIMON sedang mengembalikan versi dan database sebelumnya.</p>':''}</div>`;}
function agentRolloutBox(rollout){
 if(!rollout||(!rollout.busy&&!rollout.total))return '';
 if(rollout.busy){
  const total=Number(rollout.total||0),done=Number(rollout.done||0),inProg=Number(rollout.in_progress||0),queued=Number(rollout.queued||0),failed=Number(rollout.failed||0),pct=total>0?Math.round((done/total)*100):0;
  return `<div class="update-progress" id="agentRolloutProgress" aria-label="Proses update massal agent sedang berjalan"><div class="update-progress-head"><span class="update-spinner" aria-hidden="true"></span><b>Update massal agent sedang berjalan (maks. ${rollout.max_concurrent||3} PC paralel)</b><span id="agentRolloutTimer">Berjalan ${rolloutElapsed(rollout)||'00:00'}</span></div><div class="meter" style="margin:10px 0 8px"><i style="width:${pct}%"></i></div><p style="margin:0;color:var(--muted)"><b>${done} / ${total} PC selesai (${pct}%)</b> &middot; ${inProg} sedang diproses &middot; ${queued} antrean${failed?` &middot; ${failed} gagal`:''}</p></div>`;
 }
 return `<div class="update-result" role="status"><b>${rollout.state==='completed'?'Update massal agent selesai':'Status update massal agent'}</b><p>${esc(rollout.message||'')}</p></div>`;
}
function agentPackageCard(data){
 const ready=agentPackageState.ready,rollout=agentPackageState.rollout||{},rolloutBusy=Boolean(rollout.busy),outdated=Number(agentPackageState.online_outdated||0);
 const sha=(agentPackageState.source_sha||'').slice(0,12),size=agentPackageState.size?(agentPackageState.size/1048576).toLocaleString('id-ID',{maximumFractionDigits:1})+' MiB':'',created=agentPackageState.created_at?new Date(agentPackageState.created_at*1000).toLocaleString('id-ID'):'';
 return `<section class="agent-package-panel"><div class="card-heading"><div><h3>Paket agent store</h3><p>Build resmi yang cocok dengan versi server, dibungkus bersama CA publik kantor.</p></div><span class="subtle-badge">${rolloutBusy?'Sedang update massal':ready?'Siap dibagikan':'Belum disiapkan'}</span></div>${ready?`<div class="agent-package-ready"><div><b>SIMONAgent-store.zip</b><small>Agent v${esc(agentPackageState.agent_version||data.version)} · ${esc(created)}</small></div><span>${size} &middot; ${esc(sha)}</span></div>`:''}${agentRolloutBox(rollout)}${agentPackageState.error?`<p class="error">${esc(agentPackageState.error)}</p>`:''}<div class="toolbar"><button id="prepareAgentPackage" class="secondary" ${data.busy||data.maintenance||rolloutBusy?'disabled':''}>Ambil agent terbaru</button><button id="startAgentRollout" ${!ready||data.busy||data.maintenance||rolloutBusy?'disabled':''}>${rolloutBusy?'Sedang memperbarui agent...':'Update semua agent online'+(outdated>0?` (${outdated} PC)`:'')}</button>${ready?'<a class="download-button compact-download" href="/api/system/agent-package/download">Download paket agent</a>':''}</div><p class="device-note">Update massal hanya memperbarui PC yang sedang <b>Online</b> secara bergilir (maksimal 3 PC bersamaan) tanpa menghapus konfigurasi atau identitas PC. PC yang sedang offline dapat diperbarui manual dengan paket di atas.</p><p id="agentPackageError" class="error" role="alert"></p></section>`;
}
function updateCard(data){
 if(!updateLoadedCommit&&data.current)updateLoadedCommit=data.current;
 const checked=data.check||{},job=data.job||{},busy=data.busy,available=checked.available&&checked.latest!==data.current,rollout=agentPackageState.rollout||{};
 updateNeedsPolling=Boolean(data.busy||data.maintenance||rollout.busy);
 if((data.busy||data.maintenance)&&!updateObservedStart)updateObservedStart=Number(job.started_at)||Date.now()/1000;
 if(!data.busy&&!data.maintenance)updateObservedStart=null;
 if(rollout.busy&&!rolloutObservedStart)rolloutObservedStart=Number(rollout.started_at)||Date.now()/1000;
 if(!rollout.busy)rolloutObservedStart=null;
 const issues=job.error||job.rollback_error;
 return `<article class="card update-panel" id="updatePanel" data-update-mode="app"><div class="card-heading"><div><h3>Update aplikasi SIMON</h3><p>Web dan server diperbarui dari repo SIMON, branch main.</p></div><span class="subtle-badge">Khusus Super Admin</span></div><div class="update-versions"><div><small>Versi terpasang</small><strong>${esc(data.version)}</strong><code>${esc((data.current||'Belum tercatat').slice(0,12))}</code></div><div><small>Versi terbaru</small><strong>${checked.latest?esc(checked.latest_version||checked.latest.slice(0,8)):'Belum diperiksa'}</strong><code>${checked.latest?esc(checked.latest.slice(0,12)):'Klik Cek update'}</code></div></div>${!data.ready?`<div class="update-notice"><b>Pemasangan awal diperlukan satu kali</b><p>${esc(data.setup_message)}</p><code>deployment/server/setup-updater.bat</code></div>`:''}${updateProgress(job,busy||data.maintenance)}<div class="update-result" role="status"><b>${esc(updateLabels[job.state]||'Status update')}</b><p>${esc(job.message||'Klik Cek update untuk memeriksa versi terbaru.')}</p>${checked.latest&&!busy&&!available&&job.state==='idle'?'<p>SIMON sudah memakai versi terbaru.</p>':''}${issues?`<p class="error">${esc(job.error||'')} ${esc(job.rollback_error||'')}</p>`:''}</div>${checked.changes?.length?`<details class="update-changes"><summary>Perubahan yang tersedia</summary><ul>${checked.changes.map(line=>`<li>${esc(line)}</li>`).join('')}</ul></details>`:''}<div class="toolbar"><button id="checkUpdate" class="secondary" ${!data.ready||busy||data.maintenance?'disabled':''}>Cek update</button><button id="startUpdate" data-target="${esc(checked.latest||'')}" ${!data.ready||!available||busy||data.maintenance?'disabled':''}>Update sekarang</button><button id="showUpdateLog" class="link-button">Lihat log</button></div><p id="updateError" class="error" role="alert"></p><pre id="updateLog" class="update-log" hidden></pre><p class="device-note">Backup database dibuat sebelum pemasangan. Jika versi baru gagal, helper memulihkan aplikasi dan database sebelumnya. Halaman dapat terputus sementara saat restart.</p></article>`;
}
function agentUpdateCard(data){
 const rollout=agentPackageState.rollout||{};
 updateNeedsPolling=Boolean(data.busy||data.maintenance||rollout.busy);
 if(rollout.busy&&!rolloutObservedStart)rolloutObservedStart=Number(rollout.started_at)||Date.now()/1000;
 if(!rollout.busy)rolloutObservedStart=null;
 return `<article class="card update-panel" id="updatePanel" data-update-mode="agent"><div class="card-heading"><div><h3>Update Agent SIMON</h3><p>Kelola paket installer agent store dan pembaruan massal PC yang sedang online.</p></div><span class="subtle-badge">Versi Server ${esc(data.version)}</span></div>${agentPackageCard(data)}<p class="device-note" style="margin-top:14px;margin-bottom:0">Catatan: Update aplikasi Web &amp; Server (SIMON + ADO) kini dilakukan dari <b>halaman Login</b> melalui tombol <b>Update</b>.</p></article>`;
}
function reloadAfterUpdate(data){if(data.job?.state==='success'&&!data.busy&&!data.maintenance&&updateLoadedCommit&&data.current!==updateLoadedCommit){sessionStorage.setItem('simonUpdateView','1');window.location.reload();return true;}return false;}
async function updatesMarkup(){const [data,agent]=await Promise.all([api('system/update/status'),api('system/agent-package/status')]);agentPackageState=agent;if(typeof applyUpdateIndicator==='function')applyUpdateIndicator(data);if(reloadAfterUpdate(data))return '<p>Memuat versi terbaru...</p>';return agentUpdateCard(data);}
function replaceUpdatePanel(data){if(typeof applyUpdateIndicator==='function')applyUpdateIndicator(data);if(reloadAfterUpdate(data))return;const panel=document.querySelector('#updatePanel');if(!panel)return;const mode=panel.dataset.updateMode;if(mode==='agent'&&view!=='Updates')return;const log=panel.querySelector('#updateLog'),saved=log&&!log.hidden?log.textContent:null;panel.outerHTML=(mode==='agent'?agentUpdateCard(data):updateCard(data));bindUpdates();if(saved!==null){const output=document.querySelector('#updateLog');if(output){output.textContent=saved;output.hidden=false;}}}
function bindUpdates(){
 const check=document.querySelector('#checkUpdate'),start=document.querySelector('#startUpdate'),logs=document.querySelector('#showUpdateLog'),prepare=document.querySelector('#prepareAgentPackage'),rolloutBtn=document.querySelector('#startAgentRollout');
 if(check)check.onclick=async()=>{updateActionBusy=true;check.disabled=true;const original=check.textContent;check.textContent='Memeriksa...';const error=document.querySelector('#updateError');error.textContent='';try{await api('system/update/check',{});replaceUpdatePanel(await api('system/update/status'));}catch(e){if(error.isConnected)error.textContent=e.message;}finally{updateActionBusy=false;if(check.isConnected){check.disabled=false;check.textContent=original;}}};
 if(start)start.onclick=async()=>{updateActionBusy=true;updateNeedsPolling=true;start.disabled=true;start.textContent='Memulai...';document.querySelector('#checkUpdate').disabled=true;try{await api('system/update/start',{target:start.dataset.target});replaceUpdatePanel(await api('system/update/status'));}catch(e){const error=document.querySelector('#updateError');if(error)error.textContent=e.message;if(start.isConnected){start.disabled=false;start.textContent='Update sekarang';}}finally{updateActionBusy=false;}};
 if(logs)logs.onclick=async()=>{try{const result=await api('system/update/log');const output=document.querySelector('#updateLog');output.textContent=result.log;output.hidden=!output.hidden;}catch(e){document.querySelector('#updateError').textContent=e.message;}};
 if(prepare)prepare.onclick=async()=>{prepare.disabled=true;prepare.textContent='Mengambil agent...';const error=document.querySelector('#agentPackageError');error.textContent='';try{agentPackageState=await api('system/agent-package/prepare',{});toast('Paket agent terbaru siap diunduh.');replaceUpdatePanel(await api('system/update/status'));}catch(e){if(error.isConnected)error.textContent=e.message;toast(e.message,'error');prepare.disabled=false;prepare.textContent='Ambil agent terbaru';}};
 if(rolloutBtn)rolloutBtn.onclick=async()=>{updateActionBusy=true;updateNeedsPolling=true;rolloutBtn.disabled=true;rolloutBtn.textContent='Memulai update massal...';const error=document.querySelector('#agentPackageError');if(error)error.textContent='';try{agentPackageState=await api('system/agent-package/rollout',{});toast('Update massal agent online dimulai.');replaceUpdatePanel(await api('system/update/status'));}catch(e){if(error&&error.isConnected)error.textContent=e.message;toast(e.message,'error');if(rolloutBtn.isConnected){rolloutBtn.disabled=false;rolloutBtn.textContent='Update semua agent online';}}finally{updateActionBusy=false;}};
}
async function openLoginUpdateModal(){
 const d=document.querySelector('#dialog');
 if(!d)return;
 d.style.maxWidth='760px';
 d.innerHTML=`<div class="loading-state"><div></div><p>Memeriksa akses Super Admin...</p></div>`;
 if(!d.open)d.showModal();
 const renderAppUpdate=(data)=>{
  d.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px"><h2 style="margin:0">Update Aplikasi SIMONADO</h2><button type="button" id="closeLoginUpdateModal" class="secondary compact">Tutup</button></div>${updateCard(data)}`;
  document.querySelector('#closeLoginUpdateModal').onclick=()=>d.close();
  bindUpdates();
 };
 try{
  const r=await fetch('/api/system/update/status',{cache:'no-store'});
  if(r.ok){renderAppUpdate(await r.json());return;}
 }catch{}
 d.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:8px"><h2 style="margin:0">Update Aplikasi SIMONADO</h2><button type="button" id="closeLoginUpdateModal" class="secondary compact">Tutup</button></div>
  <p class="muted" style="margin-top:0">Masukkan akun <b>Super Admin</b> untuk memeriksa dan menjalankan pembaruan aplikasi SIMON &amp; ADO.</p>
  <form id="loginUpdateAuthForm">
   <label>Username Super Admin</label>
   <input name="username" autocomplete="username" required>
   <label>Password</label>
   <input name="password" type="password" autocomplete="current-password" required>
   <p class="error" id="loginUpdateAuthErr"></p>
   <p><button type="submit" id="loginUpdateAuthBtn">Verifikasi &amp; Buka Update</button></p>
  </form>`;
 document.querySelector('#closeLoginUpdateModal').onclick=()=>d.close();
 document.querySelector('#loginUpdateAuthForm').onsubmit=async e=>{
  e.preventDefault();
  const btn=document.querySelector('#loginUpdateAuthBtn');
  const errEl=document.querySelector('#loginUpdateAuthErr');
  errEl.textContent='';
  btn.disabled=true;
  try{
   const creds=Object.fromEntries(new FormData(e.target));
   const u=await api('login',creds);
   if(u.role!=='super_admin'){
    errEl.textContent='Hanya akun Super Admin yang dapat melakukan update aplikasi.';
    btn.disabled=false;
    return;
   }
   const st=await api('system/update/status');
   renderAppUpdate(st);
  }catch(err){
   errEl.textContent=err.message;
   btn.disabled=false;
  }
 };
}
setInterval(()=>{
 if(!updateNeedsPolling||view!=='Updates'||document.hidden)return;
 const timer=document.querySelector('#agentRolloutTimer');
 if(timer&&agentPackageState.rollout?.busy)timer.textContent='Berjalan '+rolloutElapsed(agentPackageState.rollout);
},1000);
setInterval(async()=>{
 const panel=document.querySelector('#updatePanel');
 if(!updateNeedsPolling||updatePolling||updateActionBusy||document.hidden||!panel)return;
 const mode=panel.dataset.updateMode;
 if(mode==='agent'&&(!me||view!=='Updates'))return;
 // Keep controls steady while someone is checking; fetch status only, never trigger a Git fetch here.
 updatePolling=true;
 try{
  const fetches=[fetch('/api/system/update/status',{cache:'no-store'})];
  if(mode==='agent')fetches.push(fetch('/api/system/agent-package/status',{cache:'no-store'}));
  const [response,agentRes]=await Promise.all(fetches);
  if(response.status===401||(agentRes&&agentRes.status===401)){login();return;}
  if(!response.ok)throw Error('Server sedang restart. Menunggu tersambung kembali...');
  const result=await response.json();
  if(agentRes&&agentRes.ok)agentPackageState=await agentRes.json();
  if(document.querySelector('#updatePanel'))replaceUpdatePanel(result);
 }catch(e){const state=document.querySelector('#updatePanel .update-result');if(state)state.textContent='Koneksi sementara terputus. Menunggu server dan hasil update...';}
 finally{updatePolling=false;}
},3000);
