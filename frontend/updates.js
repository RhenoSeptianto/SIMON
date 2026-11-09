let updatePolling=false,updateActionBusy=false,updateNeedsPolling=false,updateLoadedCommit=null;
const updateLabels={idle:'Siap diperiksa',queued:'Dalam antrean',preparing:'Menyiapkan versi',stopping:'Menghentikan sementara',backup:'Membuat backup',installing:'Memasang pembaruan',verifying:'Memeriksa server',rolling_back:'Memulihkan versi lama',success:'Update berhasil',failed:'Update dibatalkan',rolled_back:'Versi lama dipulihkan',rollback_failed:'Pemulihan perlu diperiksa'};
function updateCard(data){
 if(!updateLoadedCommit&&data.current)updateLoadedCommit=data.current;
 updateNeedsPolling=Boolean(data.busy||data.maintenance);
 const checked=data.check||{},job=data.job||{},busy=data.busy,available=checked.available&&checked.latest!==data.current;
 const issues=job.error||job.rollback_error;
 return `<article class="card update-panel" id="updatePanel"><div class="card-heading"><div><h3>Update aplikasi SIMON</h3><p>Web dan server diperbarui dari repo SIMON, branch main.</p></div><span class="subtle-badge">Khusus Super Admin</span></div><div class="update-versions"><div><small>Versi terpasang</small><strong>${esc(data.version)}</strong><code>${esc((data.current||'Belum tercatat').slice(0,12))}</code></div><div><small>Versi terbaru</small><strong>${checked.latest?esc(checked.latest_version||checked.latest.slice(0,8)):'Belum diperiksa'}</strong><code>${checked.latest?esc(checked.latest.slice(0,12)):'Klik Cek update'}</code></div></div>${!data.ready?`<div class="update-notice"><b>Pemasangan awal diperlukan satu kali</b><p>${esc(data.setup_message)}</p><code>deployment/server/setup-updater.bat</code></div>`:''}<div class="update-result" role="status"><b>${esc(updateLabels[job.state]||'Status update')}</b><p>${esc(job.message||'Klik Cek update untuk memeriksa versi terbaru.')}</p>${checked.latest&&!busy&&!available&&job.state==='idle'?'<p>SIMON sudah memakai versi terbaru.</p>':''}${issues?`<p class="error">${esc(job.error||'')} ${esc(job.rollback_error||'')}</p>`:''}</div>${checked.changes?.length?`<details class="update-changes"><summary>Perubahan yang tersedia</summary><ul>${checked.changes.map(line=>`<li>${esc(line)}</li>`).join('')}</ul></details>`:''}<div class="toolbar"><button id="checkUpdate" class="secondary" ${!data.ready||busy||data.maintenance?'disabled':''}>Cek update</button><button id="startUpdate" data-target="${esc(checked.latest||'')}" ${!data.ready||!available||busy||data.maintenance?'disabled':''}>Update sekarang</button><button id="showUpdateLog" class="link-button">Lihat log</button></div><p id="updateError" class="error" role="alert"></p><pre id="updateLog" class="update-log" hidden></pre><p class="device-note">Backup database dibuat sebelum pemasangan. Jika versi baru gagal, helper memulihkan aplikasi dan database sebelumnya. Halaman dapat terputus sementara saat restart. Update ini tidak mengganti agent di PC store.</p></article>`;
}
function reloadAfterUpdate(data){if(data.job?.state==='success'&&!data.busy&&!data.maintenance&&updateLoadedCommit&&data.current!==updateLoadedCommit){sessionStorage.setItem('simonUpdateView','1');window.location.reload();return true;}return false;}
async function updatesMarkup(){const data=await api('system/update/status');if(reloadAfterUpdate(data))return '<p>Memuat versi terbaru...</p>';return updateCard(data);}
function replaceUpdatePanel(data){if(reloadAfterUpdate(data))return;const panel=document.querySelector('#updatePanel');if(!panel||view!=='Updates')return;const log=panel.querySelector('#updateLog'),saved=log&&!log.hidden?log.textContent:null;panel.outerHTML=updateCard(data);bindUpdates();if(saved!==null){const output=document.querySelector('#updateLog');output.textContent=saved;output.hidden=false;}}
function bindUpdates(){
 const check=document.querySelector('#checkUpdate'),start=document.querySelector('#startUpdate'),logs=document.querySelector('#showUpdateLog');
 if(check)check.onclick=async()=>{updateActionBusy=true;check.disabled=true;const error=document.querySelector('#updateError');error.textContent='';try{await api('system/update/check',{});replaceUpdatePanel(await api('system/update/status'));}catch(e){if(error.isConnected)error.textContent=e.message;}finally{updateActionBusy=false;if(check.isConnected)check.disabled=false;}};
 if(start)start.onclick=async()=>{updateActionBusy=true;updateNeedsPolling=true;start.disabled=true;document.querySelector('#checkUpdate').disabled=true;try{await api('system/update/start',{target:start.dataset.target});replaceUpdatePanel(await api('system/update/status'));}catch(e){const error=document.querySelector('#updateError');if(error)error.textContent=e.message;if(start.isConnected)start.disabled=false;}finally{updateActionBusy=false;}};
 if(logs)logs.onclick=async()=>{try{const result=await api('system/update/log');const output=document.querySelector('#updateLog');output.textContent=result.log;output.hidden=!output.hidden;}catch(e){document.querySelector('#updateError').textContent=e.message;}};
}
setInterval(async()=>{
 if(!updateNeedsPolling||updatePolling||updateActionBusy||!me||view!=='Updates'||document.hidden||!document.querySelector('#updatePanel'))return;
 // Keep controls steady while someone is checking; fetch status only, never trigger a Git fetch here.
 updatePolling=true;
 try{
  const response=await fetch('/api/system/update/status',{cache:'no-store'});
  if(response.status===401){login();return;}
  if(!response.ok)throw Error('Server sedang restart. Menunggu tersambung kembali...');
  const result=await response.json();
  if(view==='Updates'&&me)replaceUpdatePanel(result);
 }catch(e){const state=document.querySelector('#updatePanel .update-result');if(state)state.textContent='Koneksi sementara terputus. Menunggu server dan hasil update...';}
 finally{updatePolling=false;}
},3000);
