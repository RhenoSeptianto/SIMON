function bindDeviceActions(id,d,assignments){document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>act(()=>api(`devices/${id}/${b.dataset.action}`,{})));const assignmentForm=document.querySelector('#deviceAssignments');if(assignmentForm){const select=assignmentForm.querySelector('#assignTS'),button=assignmentForm.querySelector('#assignTSButton'),error=assignmentForm.querySelector('#assignmentError'),success=assignmentForm.querySelector('#assignmentSuccess');let busy=false;const paint=()=>{select.innerHTML='<option value="">Pilih user TS</option>'+assignments.filter(x=>!x.assigned).map(x=>`<option value="${x.id}">${esc(x.name)} (${esc(x.username)})${x.active?'':' - Nonaktif'}</option>`).join('');assignmentForm.querySelector('#assignedTS').innerHTML=assignments.filter(x=>x.assigned).map(x=>`<span class="assigned-user">${esc(x.name)} <button type="button" data-remove-ts="${x.id}" aria-label="Lepas akses ${esc(x.name)}">&times;</button></span>`).join('')||'<p class="muted">Belum ada user TS yang diassign.</p>';button.disabled=busy||!select.value;select.disabled=busy;assignmentForm.querySelectorAll('[data-remove-ts]').forEach(b=>{b.disabled=busy;b.onclick=()=>save(Number(b.dataset.removeTs),false)})};const save=async(userId,assigned)=>{if(busy)return;busy=true;paint();error.textContent='';success.textContent='';const ids=assignments.filter(x=>x.id===userId?assigned:x.assigned).map(x=>x.id);try{await api(`devices/${id}/assignments`,{user_ids:ids},'PUT');assignments.find(x=>x.id===userId).assigned=assigned;success.textContent=assigned?'User berhasil diassign.':'Akses user dilepas.'}catch(e){if(me)error.textContent=e.message}finally{busy=false;paint()}};select.onchange=()=>button.disabled=busy||!select.value;assignmentForm.onsubmit=e=>{e.preventDefault();if(select.value)save(Number(select.value),true)};paint();}document.querySelector('#deleteDevice')?.addEventListener('click',()=>{if(confirm(`Hapus perangkat ${d.hostname} (${d.ip})?\n\nHistori telemetry, alert, dan akses user untuk PC ini akan dihapus permanen. Agent dengan identitas lama tidak dapat mendaftar ulang.`))act(()=>api(`devices/${id}`,undefined,'DELETE'))});}
const fmtNumber = value => Number(value).toLocaleString('id-ID', {maximumFractionDigits: 1});
const percent = value => value == null || !Number.isFinite(Number(value)) ? 'N/A' : fmtNumber(value) + '%';
const clampPercent = value => Math.max(0, Math.min(100, Number(value) || 0));
function ageLabel(timestamp) {
  if (!timestamp) return 'Belum tersedia';
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));
  return seconds < 60 ? 'Baru saja' : seconds < 3600 ? `${Math.floor(seconds / 60)} menit lalu` : seconds < 86400 ? `${Math.floor(seconds / 3600)} jam lalu` : `${Math.floor(seconds / 86400)} hari lalu`;
}
function infoRows(rows) {
  return `<dl class="device-info">${rows.map(([label,value]) => `<div><dt>${esc(label)}</dt><dd>${esc(value || 'Tidak tersedia')}</dd></div>`).join('')}</dl>`;
}
function metricCard(label,value,description,extra='') {
  return `<article class="metric-card"><span class="muted">${label}</span><strong>${percent(value)}</strong><div class="usage-track"><span style="width:${clampPercent(value)}%"></span></div><small>${description}</small>${extra ? `<p>${extra}</p>` : ''}</article>`;
}
function volumeCard(v) {
  const free = v.total_bytes > 0 && v.free_bytes != null ? clampPercent(v.free_bytes / v.total_bytes * 100) : null;
  const used = free == null ? null : 100 - free;
  const level = free == null ? 'unknown' : free < 10 ? 'critical' : free < 20 ? 'warning' : 'normal';
  const label = {normal:'Ruang cukup', warning:'Ruang mulai menipis', critical:'Hampir penuh',unknown:'Data belum tersedia'}[level];
  return `<article class="storage-card ${level}"><div class="section-heading"><h4>${esc(v.drive_letter)}</h4><span class="storage-status">${label}</span></div><div class="storage-free">${gib(v.free_bytes)} <small>tersisa / ${gib(v.total_bytes)}</small></div><div class="usage-track" role="meter" aria-label="Ruang terpakai ${esc(v.drive_letter)}" aria-valuemin="0" aria-valuemax="100" ${used == null ? '' : `aria-valuenow="${used.toFixed(1)}"`}><span style="width:${clampPercent(used)}%"></span></div><div class="volume-labels"><span>Terpakai ${percent(used)}</span><b>Tersisa ${percent(free)}</b></div><small>${esc(v.filesystem || 'File system tidak tersedia')}</small></article>`;
}
let deviceOpenRequest = 0;
async function details(id,initialTab='overview',period=24) {
  const requestNumber = ++deviceOpenRequest;
  try {
    const [d,assignments] = await Promise.all([api('devices/'+id),admin()?api(`devices/${id}/assignments`):Promise.resolve([])]);
    if (!me || requestNumber !== deviceOpenRequest) return;
    const m = d.metrics, inventory = d.inventory;
    const tabs = [['overview','Ringkasan'],['storage','Storage'],['history','Histori'],...(admin()?[['access','Akses User']]:[])];
    if (!tabs.some(([key])=>key===initialTab)) initialTab='overview';
    const volumes = (m.volumes || []).map(volumeCard).join('') || '<p>Data drive belum tersedia. Tunggu koleksi agent berikutnya.</p>';
    const disks=renderDiskCards(m);
    modal(`<div class="device-head"><div><span class="eyebrow">DETAIL PERANGKAT</span><h2>${esc(d.hostname)}</h2><p><b>Store ${esc(d.store_code||'Belum diisi')}</b> <span>&middot;</span> ${esc(d.ip)} <span>·</span> Serial ${esc(d.serial)}</p></div><div class="device-head-actions"><span class="badge ${d.online?'':'offline'}">${d.online?'Online':'Offline'}</span><button id="deviceClose" class="secondary" aria-label="Tutup detail perangkat">&times;</button></div></div><div class="device-freshness"><span title="${esc(stamp(d.last_seen))}">Terakhir terhubung: ${ageLabel(d.last_seen)}</span><button class="secondary" id="refreshDevice">Refresh data</button></div><div class="device-tabs" role="tablist" aria-label="Informasi perangkat">${tabs.map(([key,label])=>`<button role="tab" id="tab-${key}" data-device-tab="${key}" aria-selected="${initialTab===key}" aria-controls="panel-${key}" tabindex="${initialTab===key?0:-1}">${label}</button>`).join('')}</div><div class="device-body"><section role="tabpanel" id="panel-overview" aria-labelledby="tab-overview" ${initialTab!=='overview'?'hidden':''}><div class="metric-grid">${metricCard('CPU',m.cpu_usage,'Persentase penggunaan prosesor.')}${metricCard('RAM',m.ram_percent,'Persentase memori yang sedang digunakan.',`${gib(m.ram_used)} terpakai / ${gib(m.ram_total)}`)}</div><p class="device-note" title="${esc(stamp(m.metrics_at))}">Sampel CPU/RAM: ${ageLabel(m.metrics_at)}. Refresh mengambil data terakhir yang sudah dikirim agent.</p><h3>Informasi PC</h3>${infoRows([['Kode store',d.store_code||'Belum diisi'],['Perangkat',[inventory.manufacturer,inventory.model].filter(Boolean).join(' ')],['Prosesor',inventory.cpu],['Sistem operasi',inventory.os_name],['Total RAM',gib(m.ram_total)],['Waktu aktif',m.uptime_seconds==null?'Tidak tersedia':fmtNumber(m.uptime_seconds/3600)+' jam'],['Terakhir terhubung',stamp(d.last_seen)]])}<h3>Sisa storage</h3><div class="storage-grid">${volumes}</div></section><section role="tabpanel" id="panel-storage" aria-labelledby="tab-storage" ${initialTab!=='storage'?'hidden':''}><h3>Physical SSD / HDD</h3><div id="sentinelStatus">${sentinelStatus(m)}</div><div id="physicalDisks" class="storage-grid">${disks}</div><h3>Drive dan ruang tersisa</h3><div class="storage-grid">${volumes}</div><p class="device-note">Hijau: sisa ≥20% · Kuning: sisa 10–20% · Merah: sisa &lt;10%.</p></section><section role="tabpanel" id="panel-history" aria-labelledby="tab-history" ${initialTab!=='history'?'hidden':''}><div class="section-heading"><div><h3>Histori CPU & RAM</h3><p class="device-note">Perubahan penggunaan CPU dan RAM dari sampel yang dikirim agent.</p></div><select id="historyPeriod" aria-label="Periode histori"><option value="1" ${period===1?'selected':''}>1 jam</option><option value="24" ${period===24?'selected':''}>24 jam</option><option value="168" ${period===168?'selected':''}>7 hari</option></select></div><div id="deviceHistory" aria-live="polite"></div></section>${admin()?`<section role="tabpanel" id="panel-access" aria-labelledby="tab-access" ${initialTab!=='access'?'hidden':''}><form id="deviceAssignments"><h3>Assign user TS</h3><p class="device-note">User yang dipilih bisa melihat PC ini. Super Admin otomatis melihat semua PC.</p><div class="toolbar"><select id="assignTS" aria-label="Pilih user TS"></select><button id="assignTSButton">Assign</button></div><div id="assignedTS"></div><p id="assignmentError" class="error"></p><p id="assignmentSuccess" role="status"></p></form><div class="device-danger"><h3>Pengelolaan perangkat</h3><p class="device-note">Revoke mencabut izin agent. Hapus menghilangkan PC beserta histori dan assignment.</p><div class="toolbar">${d.status==='approved'?'<button class="secondary" data-action="revoke">Revoke credential</button>':''}<button id="deleteDevice" class="danger">Hapus perangkat</button></div></div></section>`:''}</div>`);
    const dialog = document.querySelector('#dialog');dialog.classList.add('device-dialog');
    dialog.querySelector('#close').parentElement.hidden=true;
    dialog.querySelector('#deviceClose').onclick=()=>dialog.close();
    let currentTab = initialTab, historyLoaded = false, historyVersion=0;
    async function loadHistory() {
      const target=dialog.querySelector('#deviceHistory'),version=++historyVersion;
      target.innerHTML='<p>Memuat histori…</p>';
      try {
        const samples=await api(`devices/${id}/history?hours=${period}`);
        if(version!==historyVersion || !target.isConnected)return;
        drawHistory(target,samples,period);historyLoaded=true;
      } catch(e) {if(me&&target.isConnected&&version===historyVersion){target.innerHTML=`<p class="error">${esc(e.message)}</p><button id="retryHistory">Coba lagi</button>`;target.querySelector('button').onclick=loadHistory;}}
    }
    function selectTab(key) {
      currentTab=key;
      dialog.querySelectorAll('[data-device-tab]').forEach(button=>{const selected=button.dataset.deviceTab===key;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;});
      tabs.forEach(([name])=>dialog.querySelector('#panel-'+name).hidden=name!==key);
      if(key==='history'&&!historyLoaded)loadHistory();
      dialog.querySelector('.device-body').scrollTop=0;
    }
    dialog.querySelectorAll('[data-device-tab]').forEach((button,index)=>{
      button.onclick=()=>selectTab(button.dataset.deviceTab);
      button.onkeydown=e=>{let next;if(e.key==='ArrowRight')next=(index+1)%tabs.length;else if(e.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=tabs.length-1;else return;e.preventDefault();selectTab(tabs[next][0]);dialog.querySelector('#tab-'+tabs[next][0]).focus();};
    });
    dialog.querySelector('#historyPeriod').onchange=e=>{period=Number(e.target.value);historyLoaded=false;loadHistory();};
    dialog.querySelector('#refreshDevice').onclick=async e=>{e.target.disabled=true;await details(id,currentTab,period);};
    bindDeviceActions(id,d,assignments);
    if(initialTab==='history')loadHistory();
    let diskRefreshBusy=false;
    const diskTimer=setInterval(async()=>{
      if(!me||!dialog.isConnected||!dialog.open||requestNumber!==deviceOpenRequest){clearInterval(diskTimer);return;}
      if(document.hidden||diskRefreshBusy)return;
      diskRefreshBusy=true;
      try{
        const latest=await api('devices/'+id);
        if(!dialog.open||requestNumber!==deviceOpenRequest)return;
        const host=dialog.querySelector('#physicalDisks');
        const expanded=new Set([...host.querySelectorAll('details[open]')].map(node=>node.dataset.disk));
        host.innerHTML=renderDiskCards(latest.metrics);
        host.querySelectorAll('details').forEach(node=>node.open=expanded.has(node.dataset.disk));
        dialog.querySelector('#sentinelStatus').innerHTML=sentinelStatus(latest.metrics);
      }catch{}finally{diskRefreshBusy=false;}
    },10000);
    dialog.addEventListener('close',()=>clearInterval(diskTimer),{once:true});
  } catch(e) {if(me)alert(e.message);const refresh=document.querySelector('#refreshDevice');if(refresh)refresh.disabled=false;}
}
function drawHistory(target,history,hours) {
  const points=history.filter(x=>Number.isFinite(x.collected_at)&&(Number.isFinite(x.cpu_usage)||Number.isFinite(x.ram_percent))).sort((a,b)=>a.collected_at-b.collected_at);
  if(!points.length){target.innerHTML='<div class="history-empty"><h4>Belum ada sampel pada periode ini</h4><p>Pilih periode lebih panjang atau tunggu agent mengirim data. Data lama tidak dibuat secara otomatis.</p></div>';return;}
  const end=Date.now()/1000,start=end-hours*3600;
  const x=t=>48+Math.max(0,Math.min(1,(t-start)/(end-start)))*704,y=v=>212-clampPercent(v)*1.8;
  const series=[['cpu_usage','#1aa383','CPU'],['ram_percent','#5799cd','RAM']];
  target.innerHTML=`<div class="history-legend"><span class="cpu-key">● CPU</span><span class="ram-key">● RAM</span><small>${points.length} sampel tersedia</small></div><div class="history-chart"><svg id="historySVG" viewBox="0 0 780 255" role="img" aria-label="Grafik penggunaan CPU dan RAM 0 hingga 100 persen">${[0,25,50,75,100].map(n=>`<line x1="48" x2="752" y1="${y(n)}" y2="${y(n)}" class="chart-grid"/><text x="6" y="${y(n)+4}">${n}%</text>`).join('')}${[start,(start+end)/2,end].map(t=>`<text x="${x(t)}" y="242" text-anchor="${t===start?'start':t===end?'end':'middle'}">${esc(new Date(t*1000).toLocaleString('id-ID',{day:hours>24?'2-digit':undefined,month:hours>24?'short':undefined,hour:'2-digit',minute:'2-digit'}))}</text>`).join('')}${series.map(([key,color])=>{let segments=[],segment=[];for(const p of points){if(Number.isFinite(p[key]))segment.push(`${x(p.collected_at)},${y(p[key])}`);else{if(segment.length)segments.push(segment);segment=[];}}if(segment.length)segments.push(segment);return segments.map(s=>`<polyline fill="none" stroke="${color}" stroke-width="2.5" points="${s.join(' ')}"/>`).join('')+points.filter(p=>Number.isFinite(p[key])).map(p=>`<circle cx="${x(p.collected_at)}" cy="${y(p[key])}" r="2.5" fill="${color}"/>`).join('');}).join('')}<line id="historyCursor" x1="48" x2="48" y1="25" y2="216" stroke="currentColor" stroke-dasharray="4 4" opacity=".5"/></svg></div><div id="historyTooltip" class="history-tooltip" role="status"></div><input id="historySlider" type="range" min="0" max="${points.length-1}" value="${points.length-1}" aria-label="Pilih waktu sampel histori"><p class="device-note">Arahkan kursor atau sentuh grafik untuk melihat waktu dan persentase. Gunakan slider atau tombol panah untuk memilih sampel.</p><p class="device-note">Data tersedia: ${stamp(points[0].collected_at)} – ${stamp(points.at(-1).collected_at)}. Garis menghubungkan sampel, bukan pengukuran terus-menerus.</p>`;
  const svg=target.querySelector('svg'),slider=target.querySelector('#historySlider'),tip=target.querySelector('#historyTooltip'),cursor=target.querySelector('#historyCursor');
  function show(index){const p=points[index];tip.innerHTML=`<span>${stamp(p.collected_at)}</span><strong class="cpu-key">CPU ${percent(p.cpu_usage)}</strong><strong class="ram-key">RAM ${percent(p.ram_percent)}</strong>`;cursor.setAttribute('x1',x(p.collected_at));cursor.setAttribute('x2',x(p.collected_at));slider.value=index;slider.setAttribute('aria-valuetext',`${stamp(p.collected_at)}, CPU ${percent(p.cpu_usage)}, RAM ${percent(p.ram_percent)}`);}
  function locate(e){const matrix=svg.getScreenCTM();if(!matrix)return;const point=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());const time=start+(point.x-48)/704*(end-start);let nearest=0;for(let i=1;i<points.length;i++)if(Math.abs(points[i].collected_at-time)<Math.abs(points[nearest].collected_at-time))nearest=i;show(nearest);}
  svg.onpointermove=locate;svg.onpointerdown=locate;slider.oninput=()=>show(Number(slider.value));show(points.length-1);
}

function sentinelStatus(m){
 if(m.storage_source!=='sentinel')return `<p class="device-note">Data disk lama dari Windows. Perbarui agent dan atur ekspor XML Sentinel untuk memakai sumber baru.</p>`;
 const labels={fresh:'XML terbaru',stale:'XML belum diperbarui',missing:'XML belum ditemukan',error:'XML belum bisa dibaca',waiting:'Menunggu penulisan XML'};
 return `<p class="device-note"><b>Hard Disk Sentinel</b> <span class="badge ${m.sentinel_status==='fresh'?'':'offline'}">${esc(labels[m.sentinel_status]||'Menunggu data')}</span><br>Waktu laporan: ${esc(m.sentinel_report_time||'Tidak tersedia')}<br>File diperbarui: ${ageLabel(m.sentinel_file_updated_at)}${m.sentinel_message?'<br>'+esc(m.sentinel_message):''}<br>Hanya kondisi terbaru disimpan; perubahan penting dicatat sebagai alert.</p>`;
}
function renderDiskCards(m){return (m.disks||[]).map((disk,index)=>`<article class="storage-card"><div class="section-heading"><span class="eyebrow">PHYSICAL DISK ${index+1} &middot; ${esc(disk.media_type||'N/A')}</span><span class="badge ${disk.health_percent!=null?(disk.health_percent<80?'offline':''):(disk.health_status==='Healthy'?'':'offline')}">${disk.source==='sentinel'?'Health '+percent(disk.health_percent):esc(disk.health_status||'Tidak tersedia')}</span></div><h4>${esc(disk.model||'Model tidak tersedia')}</h4><div class="disk-numbers"><div><small>Kapasitas</small><strong>${gib(disk.capacity_bytes)}</strong></div><div><small>Suhu</small><strong>${disk.temperature_c==null?'N/A':fmtNumber(disk.temperature_c)+' ?C'}</strong></div>${disk.source==='sentinel'?`<div><small>Performance</small><strong>${percent(disk.performance_percent)}</strong></div>`:''}</div><details data-disk="${esc(disk.disk_identity||index)}"><summary>Serial dan informasi lainnya</summary>${infoRows([['Serial',disk.serial_number],['Interface',disk.bus_type],['Jam pemakaian',disk.power_on_hours==null?'Tidak tersedia':fmtNumber(disk.power_on_hours)+' jam'],...(disk.source==='sentinel'?[['Perkiraan sisa umur',disk.estimated_remaining_lifetime],['Status pemantauan',disk.power_state],['Keterangan Sentinel',disk.sentinel_description],['Saran Sentinel',disk.sentinel_tip]]:[['Wear (sensor)',disk.wear_percent==null?'Tidak tersedia':percent(disk.wear_percent)]])])}<small>${disk.source==='sentinel'?'Health dan performance berasal dari laporan Sentinel, bukan hasil konversi wear.':'Wear 0 bukan berarti sisa umur SSD 100%.'}</small></details></article>`).join('')||'<p>Data physical disk belum tersedia. Pastikan Sentinel mengekspor HDSentinel.xml otomatis.</p>';}
