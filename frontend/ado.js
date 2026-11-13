// === ADO (ASSET & DELIVERY ORDER) FRONTEND MODULE ===
let adoMe = null;
let adoView = 'Dashboard';
let adoStores = [];
let adoAssets = [];
let adoOrders = [];
let adoCatalog = { categories: [], devices: [] };
let adoUsers = [];
let adoMutations = [];

// Filter & draft states
let adoAssetSearch = '';
let adoAssetStoreFilter = '';
let adoAssetStatusFilter = '';
let adoDoTab = 'Existing Store';
let adoConfirmTab = 'Existing Store';
let adoDoSelectedStoreId = '';
let adoDoDraftItems = [];

const adoIsSuperAdmin = () => adoMe?.role === 'super_admin';
const adoIsAdminOrIt = () => ['super_admin', 'admin_it'].includes(adoMe?.role);
const adoRoleLabel = (role) => ({ super_admin: 'Super Admin', admin_it: 'Admin IT', ts: 'Technical Support' }[role] || role);

function adoDateId(ts) {
 if (!ts) return '-';
 return new Date(ts * 1000).toLocaleDateString('id-ID', { day: '2-digit', month: 'long', year: 'numeric' });
}

function adoIcon(name) {
 const extra = {
  Store: '<path d="M3 9l2-5h14l2 5M4 9v11h16V9M9 20v-6h6v6"/>',
  Confirm: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 5-5.5"/>',
  Mutation: '<path d="M16 3h5v5M4 20 21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/>',
  Network: '<rect x="2" y="3" width="6" height="6" rx="1"/><rect x="16" y="3" width="6" height="6" rx="1"/><rect x="9" y="15" width="6" height="6" rx="1"/><path d="M5 9v3h14V9M12 12v3"/>',
  DO: '<path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  Catalog: '<path d="M4 6h16M4 12h16M4 18h10"/>',
  Scan: '<path d="M3 5v14M7 5v14M11 5v14M15 5v14M19 5v14"/>',
 };
 if (extra[name]) {
  return `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${extra[name]}</svg>`;
 }
 return uiIcon(name);
}

async function adoApi(path, body, method) {
 const r = await fetch('/api/ado/' + path, {
  method: method || (body ? 'POST' : 'GET'),
  headers: { 'Content-Type': 'application/json', 'X-SIAMS-Request': '1' },
  body: body ? JSON.stringify(body) : undefined,
 });
 if (!r.ok) {
  if (r.status === 401 && path !== 'login') {
   adoMe = null;
   sessionStorage.removeItem('activePortal');
   login('ado');
   throw Error('Sesi ADO berakhir. Silakan login kembali.');
  }
  let x = await r.json().catch(() => ({ detail: 'Permintaan gagal' }));
  throw Error(typeof x.detail === 'string' ? x.detail : JSON.stringify(x.detail));
 }
 return r.json();
}

function startAdoSession(user) {
 adoMe = user;
 adoView = user?.role === 'admin_it' ? 'Confirm' : 'Dashboard';
 sessionStorage.setItem('activePortal', 'ado');
 renderAdo();
}

function adoStatusIcon(status) {
 if (status === 'rusak') return '<span class="ado-status-dot ado-status-bad" title="Rusak">&#10006;</span>';
 if (status === 'perbaikan') return '<span class="ado-status-dot ado-status-warn" title="Perbaikan">&#9888;</span>';
 return '<span class="ado-status-dot ado-status-ok" title="Normal / Aktif">&#10004;</span>';
}

function adoShell() {
 const pendingCount = Number(adoMe?.pending_do_count) || 0;
 const navItems = adoMe?.role === 'admin_it'
  ? [
   ['Confirm', 'Confirm', 'Konfirmasi'],
   ['Reports', 'Reports', 'Report'],
  ]
  : [
   ['Dashboard', 'Overview', 'Dashboard'],
   ['Stores', 'Store', adoIsAdminOrIt() ? 'Data Store' : 'Store Saya'],
   ['Confirm', 'Confirm', 'Konfirmasi'],
   ['Assets', 'Devices', 'Data Perangkat'],
   ['Network', 'Network', 'Data CCTV & Network'],
   ['Mutation', 'Mutation', 'Mutasi Perangkat'],
   ['DO', 'DO', 'Permintaan Perangkat'],
   ['Reports', 'Reports', 'Report'],
   ...(adoIsSuperAdmin() ? [['Catalog', 'Catalog', 'Master Perangkat'], ['Users', 'Users', 'Data User']] : []),
  ];

 root.innerHTML = `<aside class="sidebar ado-sidebar"><div class="brand"><div class="brand-mark">${adoIcon('Store')}</div><div class="brand-text"><h1>ADO<span>.</span></h1><small>ASSET &amp; DELIVERY ORDER</small></div><button id="toggleSidebar" class="sidebar-toggle" type="button" aria-label="Minimize menu" title="Minimize / Perlebar menu">${uiIcon('collapse')}</button></div><div class="nav-caption">MODUL ASSET &amp; DO</div><nav aria-label="Navigasi ADO">${navItems.map(([key, ic, label]) => `<button data-ado-view="${key}" title="${label}" class="${adoView === key ? 'active' : ''}" ${adoView === key ? 'aria-current="page"' : ''}>${adoIcon(ic)}<span>${label}</span><span class="nav-indicator-group" aria-hidden="true">${key === 'Confirm' && pendingCount > 0 ? `<b class="ado-new-badge">New${pendingCount > 1 ? ' ' + pendingCount : ''}</b>` : ''}${adoView === key ? '<i class="nav-dot"></i>' : ''}</span></button>`).join('')}</nav><div class="sidebar-bottom"><span class="server-dot server-dot-ok"></span><div class="sidebar-bottom-text"><b>ADO Workspace</b><small>SIMONDO v${esc(adoMe.version || '1.2.0')}</small></div></div></aside><main><header class="topbar"><div class="breadcrumb">ADO <span>/</span> <b>${esc(adoRoleLabel(adoMe.role))}</b></div><div class="topbar-actions"><div class="account"><span class="avatar">${esc((adoMe.name || 'U').slice(0, 1).toUpperCase())}</span><div><b>${esc(adoMe.name)}</b><small>${esc(adoRoleLabel(adoMe.role))}</small></div></div>${adoIsAdminOrIt() ? `<button id="adoMySigBtn" class="secondary compact" title="Atur Tanda Tangan (TTD) Saya">&#9998; TTD Saya</button>` : ''}<button id="adoTheme" class="icon-button" aria-label="Ganti tema" title="Ganti tema">${uiIcon('theme')}</button><button id="adoLogout" class="secondary compact">${uiIcon('logout')}<span>Keluar</span></button></div></header><div id="content" aria-live="polite"><div class="loading-state"><div></div><p>Memuat data ADO...</p></div></div><footer class="main-footer"><span>ADO <span>&middot;</span> ICT - Technical Support Store</span><span>1 Database Terpadu (Tabel ado_*)</span></footer></main><dialog id="dialog"></dialog>`;

 document.querySelector('#toggleSidebar').onclick = () => {
  const collapsed = document.documentElement.classList.toggle('sidebar-collapsed');
  localStorage.setItem('simonSidebarCollapsed', collapsed ? '1' : '0');
 };
 document.querySelectorAll('[data-ado-view]').forEach(b => b.onclick = () => {
  adoView = b.dataset.adoView;
  renderAdo();
 });
 document.querySelector('#adoTheme').onclick = () => {
  document.body.classList.toggle('dark');
  localStorage.setItem('theme', document.body.className);
 };
 document.querySelector('#adoMySigBtn')?.addEventListener('click', showAdoMySignatureModal);
 document.querySelector('#adoLogout').onclick = async () => {
  try { await adoApi('logout', {}); } catch {}
  adoMe = null;
  sessionStorage.removeItem('activePortal');
  login('ado');
 };
}

async function renderAdo(quiet = false) {
 if (!adoMe) return;
 if (adoMe.role === 'admin_it' && adoView !== 'Confirm' && adoView !== 'Reports') {
  adoView = 'Confirm';
 }
 if (!quiet) adoShell();
 const c = document.querySelector('#content');
 const currentView = adoView;
 try {
  const [meInfo, stores, catalog] = await Promise.all([
   adoApi('me'),
   adoApi('stores'),
   adoApi('catalog'),
  ]);
  adoMe = meInfo;
  adoStores = stores;
  adoCatalog = catalog;
  const badge = document.querySelector('[data-ado-view="Confirm"] .nav-indicator-group');
  if (badge) {
   const pCount = Number(adoMe.pending_do_count) || 0;
   badge.innerHTML = `${pCount > 0 ? `<b class="ado-new-badge">New${pCount > 1 ? ' ' + pCount : ''}</b>` : ''}${adoView === 'Confirm' ? '<i class="nav-dot"></i>' : ''}`;
  }

  let html = '';
  if (currentView === 'Dashboard') {
   const [summary, assets] = await Promise.all([adoApi('summary'), adoApi('assets')]);
   adoAssets = assets;
   html = renderAdoDashboard(summary, assets);
  } else if (currentView === 'Stores') {
   if (adoIsAdminOrIt()) adoUsers = await adoApi('users');
   html = renderAdoStores();
  } else if (currentView === 'Confirm') {
   adoOrders = await adoApi('do');
   html = renderAdoConfirm();
  } else if (currentView === 'Assets') {
   adoAssets = await adoApi('assets?group_type=PERANGKAT');
   html = renderAdoAssets('PERANGKAT', 'Data Perangkat', 'Inventaris perangkat IT Back Office, POS, dan Kitchen di store.');
  } else if (currentView === 'Network') {
   adoAssets = await adoApi('assets?group_type=CCTV_NETWORK');
   html = renderAdoAssets('CCTV_NETWORK', 'Data CCTV & Network', 'Inventaris Switch, Router, Modem, Access Point, DVR/NVR, dan Kamera CCTV.');
  } else if (currentView === 'Mutation') {
   const [allAssets, mutations] = await Promise.all([adoApi('assets'), adoApi('mutations')]);
   adoAssets = allAssets;
   adoMutations = mutations;
   html = renderAdoMutations();
  } else if (currentView === 'DO') {
   adoOrders = await adoApi('do');
   html = renderAdoDoForm();
  } else if (currentView === 'Reports') {
   const summary = await adoApi('summary');
   html = renderAdoReports(summary);
  } else if (currentView === 'Catalog') {
   html = renderAdoCatalog();
  } else if (currentView === 'Users') {
   adoUsers = await adoApi('users');
   html = renderAdoUsers();
  }

  if (!adoMe || adoView !== currentView || !c?.isConnected) return;
  c.innerHTML = html;
  bindAdoEvents();
 } catch (e) {
  if (!adoMe) return;
  c.innerHTML = `<p class="error">${esc(e.message)}</p><button id="adoRetry">Coba lagi</button>`;
  document.querySelector('#adoRetry').onclick = () => renderAdo();
 }
}

function adoYearTipCell(a) {
 const tip = a.purchase_date_label || String(a.purchase_year);
 return `<span class="ado-year-tip" tabindex="0" title="Tanggal &amp; Bulan: ${esc(tip)}" data-year-tip="${esc(tip)}">${esc(a.purchase_year)}</span>`;
}

function renderAdoDashboard(s, assets) {
 const kpis = [
  ['Jumlah Store Jabodetabek', s.stores_jabodetabek, 'ado-kpi-teal', 'Store wilayah Jabodetabek', 'Stores'],
  ['Jumlah Store Luar Jabodetabek', s.stores_luar, 'ado-kpi-cyan', 'Store luar Jabodetabek', 'Stores'],
  ['Total Perangkat Store', s.total_assets, 'ado-kpi-green', 'Perangkat & CCTV terdaftar', 'Assets'],
  ['DO Menunggu Konfirmasi', s.pending_do, 'ado-kpi-amber', 'Permintaan perangkat baru', 'Confirm'],
  ['DO Terkonfirmasi', s.confirmed_do, 'ado-kpi-red', 'Sudah masuk ke aset store', 'Confirm'],
 ];
 const rows = assets.map(a => `<tr><td><b>${esc(a.store_code ? a.store_code + ' · ' : '')}${esc(a.store_name)}</b></td><td>${esc(a.category)}</td><td><b>${esc(a.device_name)}</b></td><td>${esc(a.brand || '-')}</td><td><code>${esc(a.serial_number || '-')}</code></td><td>${adoYearTipCell(a)}</td><td>${esc(a.age_label)}</td><td style="text-align:center">${adoStatusIcon(a.status)}</td></tr>`);

 return `<div class="page-heading"><div><span class="eyebrow">ASSET &amp; DELIVERY ORDER</span><h2>Dashboard</h2></div><span class="workspace-badge"><span class="server-dot"></span> Store Board ${esc(adoMe.name)}</span></div>
 <div class="kpis ado-kpis">${kpis.map(([title, num, cls, note, targetView]) => `<div class="card kpi-card ${cls}" data-ado-jump="${targetView}" role="button" tabindex="0"><div class="kpi-label"><span>${esc(title)}</span></div><strong>${num}</strong><small>${esc(note)}</small></div>`).join('')}</div>
 <div class="card"><div class="card-heading"><div><h3>Store Board ${esc(adoMe.name)}</h3><p>${adoIsAdminOrIt() ? 'Menampilkan seluruh perangkat dari semua store.' : 'Menampilkan perangkat dari store yang menjadi tanggung jawab kamu.'}</p></div><span class="subtle-badge">${assets.length} perangkat</span></div>
 <div class="toolbar device-search"><input id="adoDashSearch" placeholder="Cari nama store, kode store, kategori, perangkat, merk, atau SN..." aria-label="Cari di Store Board"></div>
 <div id="adoDashTable">${table(['Nama Store', 'Kategori', 'Nama Perangkat', 'Merk', 'Serial Number', 'Tahun Perangkat', 'Usia Perangkat', 'Status'], rows, 'Belum ada data perangkat di Store Board', 'Tambahkan store lalu input perangkat atau konfirmasi Permintaan Perangkat (DO).', 'Devices')}</div></div>`;
}

function renderAdoStores() {
 const rows = adoStores.map(st => `<tr><td><span class="store-code">${esc(st.store_code)}</span></td><td><b>${esc(st.name)}</b></td><td><span class="pc-chip">${esc(st.region)}</span></td><td><span class="role-badge">${esc(st.store_type)}</span></td><td>${esc(st.ts_name)}</td><td><b>${st.asset_count}</b> unit</td><td style="text-align:right">${adoIsAdminOrIt() ? `<button class="link-button" data-edit-store="${st.id}">Edit</button>` : '<span class="muted">&mdash;</span>'}</td></tr>`);
 return `<div class="page-heading"><div><span class="eyebrow">MASTER STORE</span><h2>${adoIsAdminOrIt() ? 'Data Store' : 'Store Saya'}</h2></div>${adoIsAdminOrIt() ? `<button id="addAdoStore">+ Add Store</button>` : ''}</div>
 <div class="toolbar device-search"><input id="adoStoreSearch" placeholder="Cari kode store, nama store, wilayah, atau TS..." aria-label="Cari store"></div>
 <div class="card table-card" id="adoStoreTableWrap">${table(['Kode Store', 'Nama Store', 'Wilayah', 'Kategori Store', 'Technical Support', 'Total Perangkat', ''], rows, 'Belum ada store terdaftar', adoIsAdminOrIt() ? 'Klik tombol + Add Store untuk menambahkan kode store dan nama store.' : 'Belum ada store yang diassign ke akun TS kamu.')}</div>`;
}

function renderAdoConfirm() {
 const filtered = adoOrders.filter(o => o.store_type === adoConfirmTab);
 const pendingExisting = adoOrders.filter(o => o.store_type === 'Existing Store' && o.status === 'pending').length;
 const pendingNew = adoOrders.filter(o => o.store_type === 'New Store' && o.status === 'pending').length;

 const rows = filtered.map((o, idx) => {
  const itemSummary = o.items.map(i => `${i.category}: ${i.device_name} (${i.brand || '-'} / SN: ${i.serial_number || '-'})`).join(', ');
  let actionHtml = '';
  if (o.status === 'confirmed') {
   actionHtml = `<div style="display:flex;gap:6px;justify-content:center;align-items:center;flex-wrap:wrap"><span class="ado-confirmed-pill" title="Dikonfirmasi oleh ${esc(o.confirmed_by || 'Admin IT')}">&#10004; ACC: ${esc(o.confirmed_by || 'Admin IT')}</span><a class="secondary compact" style="text-decoration:none;padding:5px 10px;border-radius:8px;font-size:12px" href="/api/ado/do/${o.id}/print" target="_blank" rel="noopener">&#128424; Form DO</a></div>`;
  } else if (adoIsAdminOrIt()) {
   actionHtml = `<div style="display:flex;gap:6px;justify-content:center;align-items:center;flex-wrap:wrap"><button class="ado-confirm-btn" data-confirm-do="${o.id}" title="Edit Nomor DO, Attach TTD &amp; Konfirmasi">&#10004; Review &amp; Konfirmasi</button><a class="secondary compact" style="text-decoration:none;padding:5px 10px;border-radius:8px;font-size:12px" href="/api/ado/do/${o.id}/print" target="_blank" rel="noopener">&#128424; Form DO</a></div>`;
  } else {
   actionHtml = `<div style="display:flex;gap:6px;justify-content:center;align-items:center;flex-wrap:wrap"><span class="badge offline">Menunggu Admin IT</span><a class="secondary compact" style="text-decoration:none;padding:5px 10px;border-radius:8px;font-size:12px" href="/api/ado/do/${o.id}/print" target="_blank" rel="noopener">&#128424; Form DO</a></div>`;
  }
  return `<tr><td>${idx + 1}</td><td><button class="link-button" data-view-do="${o.id}">${esc(o.do_number)}</button></td><td><b>${esc(o.store_code ? '[' + o.store_code + '] ' : '')}${esc(o.store_name)}</b><small style="display:block;color:var(--muted);margin-top:3px">${esc(o.items.length)} perangkat &middot; ${esc(itemSummary.slice(0, 65))}${itemSummary.length > 65 ? '...' : ''}</small></td><td>${esc(o.ts_name)}</td><td>${esc(adoDateId(o.request_date))}</td><td style="text-align:center">${actionHtml}</td></tr>`;
 });

 return `<div class="page-heading"><div><span class="eyebrow">DELIVERY ORDER</span><h2>Konfirmasi Perangkat</h2></div></div>
 <div class="ado-tab-bar">
  <button type="button" class="ado-tab-btn ${adoConfirmTab === 'Existing Store' ? 'active' : ''}" data-confirm-tab="Existing Store">Existing Store ${pendingExisting ? `<b class="ado-new-badge">New ${pendingExisting}</b>` : ''}</button>
  <button type="button" class="ado-tab-btn ${adoConfirmTab === 'New Store' ? 'active' : ''}" data-confirm-tab="New Store">New Store ${pendingNew ? `<b class="ado-new-badge">New ${pendingNew}</b>` : ''}</button>
 </div>
 <div class="card table-card">${table(['No', 'Kode Permintaan', 'Nama Store', 'Technical Support', 'Tanggal Permintaan', 'Konfirmasi'], rows, 'Belum ada permintaan perangkat pada kategori ini', 'Permintaan perangkat (DO) yang dibuat oleh TS akan muncul di sini untuk dikonfirmasi Admin IT.')}</div>`;
}

function renderAdoAssets(groupType, title, subtitle) {
 const filtered = adoAssets.filter(a => {
  if (adoAssetStoreFilter && String(a.store_id) !== String(adoAssetStoreFilter)) return false;
  if (adoAssetStatusFilter && a.status !== adoAssetStatusFilter) return false;
  if (adoAssetSearch) {
   const hay = `${a.store_code} ${a.store_name} ${a.category} ${a.device_name} ${a.brand} ${a.serial_number} ${a.notes}`.toLowerCase();
   if (!hay.includes(adoAssetSearch.toLowerCase())) return false;
  }
  return true;
 });

 const rows = filtered.map(a => `<tr><td><span class="store-code">${esc(a.store_code)}</span></td><td><b>${esc(a.store_name)}</b></td><td>${esc(a.category)}</td><td><b>${esc(a.device_name)}</b></td><td>${esc(a.brand || '-')}</td><td><code>${esc(a.serial_number || '-')}</code></td><td>${adoYearTipCell(a)}</td><td>${esc(a.age_label)}</td><td style="text-align:center">${adoStatusIcon(a.status)}</td><td style="text-align:right"><button class="link-button" data-edit-asset="${a.id}">Edit</button>${adoIsAdminOrIt() ? ` &middot; <button class="link-button" style="color:#cf535a" data-del-asset="${a.id}">Hapus</button>` : ''}</td></tr>`);

 return `<div class="page-heading"><div><span class="eyebrow">INVENTARIS STORE</span><h2>${esc(title)}</h2></div><button id="addAdoAsset" data-group="${groupType}">+ Tambah ${groupType === 'CCTV_NETWORK' ? 'CCTV / Network' : 'Perangkat'}</button></div>
 <p class="page-description">${esc(subtitle)}</p>
 <div class="toolbar device-search">
  <input id="adoAssetSearchInput" value="${esc(adoAssetSearch)}" placeholder="Cari store, kategori, perangkat, merk, atau serial number..." aria-label="Cari perangkat">
  <select id="adoAssetStoreSelect" aria-label="Filter Store"><option value="">Semua Store (${adoStores.length})</option>${adoStores.map(st => `<option value="${st.id}" ${String(adoAssetStoreFilter) === String(st.id) ? 'selected' : ''}>[${esc(st.store_code)}] ${esc(st.name)}</option>`).join('')}</select>
  <select id="adoAssetStatusSelect" aria-label="Filter Kondisi"><option value="">Semua Kondisi</option><option value="normal" ${adoAssetStatusFilter === 'normal' ? 'selected' : ''}>Kondisi: Normal</option><option value="perbaikan" ${adoAssetStatusFilter === 'perbaikan' ? 'selected' : ''}>Kondisi: Perbaikan</option><option value="rusak" ${adoAssetStatusFilter === 'rusak' ? 'selected' : ''}>Kondisi: Rusak</option></select>
 </div>
 <div class="card table-card">${table(['Kode Store', 'Nama Store', 'Kategori', 'Nama Perangkat', 'Merk', 'Serial Number', 'Tahun', 'Usia', 'Status', ''], rows, 'Belum ada data perangkat', 'Klik tombol + Tambah di kanan atas atau lakukan Konfirmasi DO untuk menambahkan perangkat.')}</div>`;
}

function adoDevicesForCategory(catName) {
 const allDevs = adoCatalog.devices || [];
 const matched = allDevs.filter(d => d.parent_category === catName);
 return matched.length ? matched : (allDevs.length ? allDevs : [{ name: 'UPS' }, { name: 'BARCODE SCANNER' }]);
}

function renderAdoDoForm() {
 if (!adoDoSelectedStoreId && adoStores.length) {
  adoDoSelectedStoreId = String(adoStores[0].id);
 }
 const selectedStore = adoStores.find(st => String(st.id) === String(adoDoSelectedStoreId)) || adoStores[0];
 const selectedStoreName = selectedStore ? `${selectedStore.store_code} - ${selectedStore.name}` : 'Pilih Store terlebih dahulu';
 const cats = adoCatalog.categories.length ? adoCatalog.categories : [{ name: 'Back Office' }, { name: 'Pos 1' }];
 const initialCat = cats[0].name;
 const devs = adoDevicesForCategory(initialCat);
 const curYear = new Date().getFullYear();

 const draftRows = adoDoDraftItems.map((it, idx) => `<tr><td>${esc(it.category)}</td><td><b>${esc(it.device_name)}</b></td><td>${esc(it.brand || '-')}</td><td><code>${esc(it.serial_number || '-')}</code></td><td>${esc(it.purchase_year)}</td><td>${esc(it.notes || '-')}</td><td style="text-align:right"><button type="button" class="secondary compact" style="color:#cf535a" data-remove-draft="${idx}">Hapus</button></td></tr>`);

 const historyRows = adoOrders.map((o, idx) => `<tr><td>${idx + 1}</td><td><button class="link-button" data-view-do="${o.id}">${esc(o.do_number)}</button></td><td><span class="role-badge">${esc(o.store_type)}</span></td><td><b>[${esc(o.store_code)}] ${esc(o.store_name)}</b></td><td>${esc(o.ts_name)}</td><td>${esc(adoDateId(o.request_date))}</td><td>${o.status === 'confirmed' ? '<span class="badge"><i></i>Terkonfirmasi</span>' : '<span class="badge offline"><i></i>Menunggu Admin IT</span>'}</td><td style="text-align:right"><a class="link-button" href="/api/ado/do/${o.id}/print" target="_blank" rel="noopener">&#128424; Print DO</a></td></tr>`);

 return `<div class="page-heading"><div><span class="eyebrow">DELIVERY ORDER (DO)</span><h2>Permintaan Perangkat</h2></div></div>
 <div class="ado-tab-bar">
  <button type="button" class="ado-tab-btn ${adoDoTab === 'Existing Store' ? 'active' : ''}" data-do-tab="Existing Store">Existing Store</button>
  <button type="button" class="ado-tab-btn ${adoDoTab === 'New Store' ? 'active' : ''}" data-do-tab="New Store">New Store</button>
 </div>

 <div class="card ado-do-panel">
  <label for="doStoreSelect" style="margin-top:0;font-weight:600">Pilih Store (${esc(adoDoTab)})</label>
  <select id="doStoreSelect" aria-label="Pilih Store">${adoStores.map(st => `<option value="${st.id}" ${String(st.id) === String(adoDoSelectedStoreId) ? 'selected' : ''}>${esc(st.store_code)} - ${esc(st.name)}</option>`).join('') || '<option value="">Belum ada store terdaftar (tambahkan di menu Data Store)</option>'}</select>
 </div>

 <div class="card ado-do-panel">
  <div class="card-heading">
   <div><h3 id="doPanelStoreHeading">Input Data Perangkat Store ${esc(selectedStoreName)}</h3><p>Tambahkan satu atau beberapa perangkat ke daftar DO sebelum menekan tombol Simpan.</p></div>
   <button type="button" id="doScanBtn" class="ado-scan-btn" title="Fokus ke input Serial Number untuk scan barcode">${adoIcon('Scan')} <span>Scan</span></button>
  </div>
  <div class="ado-do-grid">
   <div><label for="doItemCategory">Kategori</label><select id="doItemCategory">${cats.map(c => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('')}</select></div>
   <div><label for="doItemDevice">Perangkat</label><select id="doItemDevice">${devs.map(d => `<option value="${esc(d.name)}">${esc(d.name)}</option>`).join('')}</select></div>
   <div><label for="doItemBrand">Merk</label><input id="doItemBrand" placeholder="Merk perangkat"></div>
   <div><label for="doItemSerial">Serial Number</label><input id="doItemSerial" placeholder="Scan / isi SN"></div>
   <div><label for="doItemYear">Tahun</label><input id="doItemYear" type="number" min="2000" max="2100" value="${curYear}"></div>
   <div><label for="doItemNotes">Keterangan</label><input id="doItemNotes" placeholder="Replace / New"></div>
   <div class="ado-do-add-col"><label>&nbsp;</label><button type="button" id="doAddItemBtn" class="ado-add-btn">+ Tambah</button></div>
  </div>
 </div>

 <div class="card ado-do-panel">
  <div class="card-heading"><h3>List Perangkat (${adoDoDraftItems.length} item)</h3></div>
  ${table(['Kategori', 'Perangkat', 'Merk', 'Serial Number', 'Tahun', 'Keterangan', 'Hapus'], draftRows, 'Belum ada perangkat di daftar sementara', 'Isi form di atas lalu klik tombol + Tambah.')}
  <div style="margin-top:16px;display:flex;justify-content:space-between;align-items:center;gap:12px">
   <button type="button" id="doSaveOrderBtn" class="ado-save-btn" ${!adoDoDraftItems.length || !adoStores.length ? 'disabled' : ''}>Simpan Permintaan (DO)</button>
   <small class="muted">Setelah disimpan, DO akan masuk ke menu <b>Konfirmasi Perangkat</b> untuk dikonfirmasi oleh Admin IT.</small>
  </div>
 </div>

 <div class="card table-card">
  <div style="padding:18px 20px 6px"><h3 style="margin:0">Riwayat Permintaan Perangkat (DO)</h3></div>
  ${table(['No', 'Kode Permintaan', 'Tipe Store', 'Nama Store', 'Technical Support', 'Tanggal', 'Status', 'Form DO'], historyRows, 'Belum ada riwayat DO', 'Permintaan perangkat yang telah disimpan akan tercatat di sini.')}
 </div>`;
}

function renderAdoMutations() {
 const rows = adoMutations.map(m => `<tr><td>${esc(adoDateId(m.moved_at))}</td><td><b>${esc(m.device_name)}</b></td><td><code>${esc(m.serial_number || '-')}</code></td><td>${esc(m.from_store_name)}</td><td><b>${esc(m.to_store_name)}</b></td><td>${esc(m.moved_by)}</td><td>${esc(m.notes || '-')}</td></tr>`);
 return `<div class="page-heading"><div><span class="eyebrow">PERGERAKAN ASET</span><h2>Mutasi Perangkat</h2></div><button id="addAdoMutation">+ Buat Mutasi Perangkat</button></div>
 <p class="page-description">Pindahkan kepemilikan perangkat dari satu Store ke Store lain beserta pencatatan historinya.</p>
 <div class="card table-card">${table(['Tanggal', 'Perangkat', 'Serial Number', 'Dari Store', 'Ke Store Tujuan', 'Dipindahkan Oleh', 'Keterangan'], rows, 'Belum ada riwayat mutasi perangkat', 'Klik tombol + Buat Mutasi Perangkat untuk memindahkan aset antar store.')}</div>`;
}

function renderAdoCatalog() {
 const cats = adoCatalog.categories || [];
 const devs = adoCatalog.devices || [];
 const areaCards = cats.map(c => {
  const items = devs.filter(d => d.parent_category === c.name);
  const grpBadge = c.group_type === 'CCTV_NETWORK' ? '<span class="role-badge">CCTV &amp; Network</span>' : '<span class="role-badge">Data Perangkat</span>';
  return `<div class="card ado-area-card">
   <div class="ado-area-head">
    <div>
     <h4>${esc(c.name)}</h4>
     <div style="display:flex;align-items:center;gap:8px;margin-top:4px">${grpBadge}<small class="muted">${items.length} jenis perangkat</small></div>
    </div>
    <button type="button" class="link-button" style="color:#cf535a;font-size:11.5px" data-del-catalog="${c.id}" title="Hapus area beserta daftar perangkatnya">Hapus Area</button>
   </div>
   <div class="ado-area-devices">
    ${items.length ? items.map(d => `<span class="ado-device-pill"><b>${esc(d.name)}</b><button type="button" data-del-catalog="${d.id}" title="Hapus ${esc(d.name)}">&times;</button></span>`).join('') : '<span class="muted" style="font-size:12px">Belum ada perangkat di area ini. Tambahkan di bawah.</span>'}
   </div>
   <form class="ado-area-add-form" data-add-area-device="${esc(c.name)}" data-area-group="${esc(c.group_type)}">
    <input name="name" placeholder="Tambah perangkat di ${esc(c.name)} (misal: PC Office, POS, UPS)..." required>
    <button type="submit">+ Tambah</button>
   </form>
  </div>`;
 }).join('');

 return `<div class="page-heading"><div><span class="eyebrow">KONFIGURASI SUPER ADMIN</span><h2>Master Perangkat per Area</h2></div><span class="subtle-badge">${cats.length} Area &middot; ${devs.length} Perangkat</span></div>
 <p class="page-description">Atur daftar <b>Area / Kategori</b> (seperti <i>Back Office, Pos 1, Kitchen, CCTV &amp; Network</i>) beserta <b>pilihan perangkat di dalam masing-masing area</b>. Saat memilih area di form DO atau Aset, pilihan perangkat otomatis menyesuaikan isinya.</p>

 <div class="card ado-area-create-bar">
  <form id="addCatalogCategoryForm" class="ado-area-create-form">
   <div>
    <label>Nama Area / Kategori Baru</label>
    <input name="name" placeholder="Contoh: Area Office, Area Counter, Pos 4, Gudang IT..." required>
   </div>
   <div>
    <label>Kelompok Menu</label>
    <select name="group_type">
     <option value="PERANGKAT">Menu Data Perangkat (Office / POS / Kitchen)</option>
     <option value="CCTV_NETWORK">Menu Data CCTV &amp; Network</option>
    </select>
   </div>
   <div>
    <label>&nbsp;</label>
    <button type="submit">+ Buat Area / Kategori Baru</button>
   </div>
  </form>
 </div>

 <div class="ado-area-grid">${areaCards || '<div class="card"><p class="muted">Belum ada area terdaftar.</p></div>'}</div>`;
}

function renderAdoReports(s) {
 return `<div class="page-heading"><div><span class="eyebrow">LAPORAN INVENTARIS &amp; DO</span><h2>Report ADO</h2></div></div>
 <p class="page-description">Unduh rekapitulasi lengkap Data Perangkat Store serta History Permintaan Perangkat (DO) dalam format Excel (.xlsx).</p>
 <article class="card report-card report-single">
  <div class="card-heading"><div><span class="report-icon">${adoIcon('Reports')}</span><h3>Laporan Asset &amp; Delivery Order (ADO)</h3><p>Satu file Excel berisi sheet <b>Data Perangkat Store</b> dan <b>History DO</b>.</p></div><span class="subtle-badge">${s.stores_total} Store &middot; ${s.total_assets} Perangkat</span></div>
  <ul class="report-sheets">
   <li><b>Sheet 1: Data Perangkat Store</b><span>Kode Store, Nama Store, Wilayah, TS, Kategori, Nama Perangkat, Merk, Serial Number, Tahun, Usia Perangkat, dan Status.</span></li>
   <li><b>Sheet 2: History DO (Permintaan &amp; Konfirmasi)</b><span>Kode Permintaan (I/DO/IT/...), Tipe Store, Nama Store, TS Pemohon, Tanggal, Status Konfirmasi Admin IT, dan Rincian Barang.</span></li>
  </ul>
  <a class="download-button" href="/api/ado/reports/xlsx">Unduh Laporan ADO (.xlsx) <span>&darr;</span></a>
 </article>`;
}

function renderAdoUsers() {
 const rows = adoUsers.map(u => {
  const storeNames = (u.store_ids || []).map(id => {
   const st = adoStores.find(x => x.id === id);
   return st ? `${st.store_code} · ${st.name}` : String(id);
  });
  const accessCell = u.role !== 'ts'
   ? '<span class="pc-chip pc-chip-all">Semua Store (Otomatis)</span>'
   : storeNames.length
    ? `<div class="user-pc-summary"><span class="pc-count-badge">${storeNames.length} Store</span>${storeNames.slice(0, 3).map(n => `<span class="pc-chip">${esc(n)}</span>`).join('')}${storeNames.length > 3 ? `<span class="pc-chip pc-chip-more">+${storeNames.length - 3} lainnya</span>` : ''}</div>`
    : '<span class="muted">Belum ada store</span>';
  const editCell = adoIsSuperAdmin() ? `<button class="link-button" data-edit-ado-user="${u.id}">Edit user</button>` : '<span class="muted">&mdash;</span>';
  return `<tr><td><b>${esc(u.name)}</b></td><td>${esc(u.username)}</td><td><span class="role-badge">${esc(adoRoleLabel(u.role))}</span>${u.has_signature ? ' <span class="pc-chip" title="Sudah memiliki TTD digital">TTD &#10004;</span>' : ''}</td><td>${accessCell}</td><td style="text-align:right">${editCell}</td></tr>`;
 });
 return `<div class="page-heading"><div><span class="eyebrow">MANAJEMEN AKUN ADO</span><h2>Data User</h2></div>${adoIsSuperAdmin() ? `<button id="addAdoUserBtn">+ Tambah User ADO</button>` : `<button id="openMySigFromUsersBtn" class="secondary compact">&#9998; Atur TTD Saya</button>`}</div>
 <p class="page-description">Kelola hak akses <b>Super Admin</b>, <b>Admin IT</b> (konfirmasi DO &amp; kelola store), serta <b>TS</b> (buat DO &amp; kelola store pegangannya).</p>
 <div class="card table-card">${table(['Nama', 'Username', 'Role ADO', 'Store Pegangan', ''], rows, 'Belum ada user ADO', 'Tambahkan akun Super Admin, Admin IT, atau TS.')}</div>`;
}

function bindAdoEvents() {
 document.querySelectorAll('[data-ado-jump]').forEach(card => {
  card.onclick = () => { adoView = card.dataset.adoJump; renderAdo(); };
 });
 document.querySelectorAll('[data-year-tip]').forEach(el => {
  el.onclick = () => toast(`Tanggal perangkat: ${el.dataset.yearTip}`);
 });

 const dashSearch = document.querySelector('#adoDashSearch');
 if (dashSearch) {
  dashSearch.oninput = () => {
   const q = dashSearch.value.trim().toLowerCase();
   const filtered = adoAssets.filter(a => !q || `${a.store_code} ${a.store_name} ${a.category} ${a.device_name} ${a.brand} ${a.serial_number}`.toLowerCase().includes(q));
   const rows = filtered.map(a => `<tr><td><b>${esc(a.store_code ? a.store_code + ' · ' : '')}${esc(a.store_name)}</b></td><td>${esc(a.category)}</td><td><b>${esc(a.device_name)}</b></td><td>${esc(a.brand || '-')}</td><td><code>${esc(a.serial_number || '-')}</code></td><td>${adoYearTipCell(a)}</td><td>${esc(a.age_label)}</td><td style="text-align:center">${adoStatusIcon(a.status)}</td></tr>`);
   document.querySelector('#adoDashTable').innerHTML = table(['Nama Store', 'Kategori', 'Nama Perangkat', 'Merk', 'Serial Number', 'Tahun Perangkat', 'Usia Perangkat', 'Status'], rows, 'Tidak ada perangkat yang cocok', 'Coba kata kunci pencarian lain.');
  };
 }

 const storeSearch = document.querySelector('#adoStoreSearch');
 if (storeSearch) {
  storeSearch.oninput = () => {
   const q = storeSearch.value.trim().toLowerCase();
   const filtered = adoStores.filter(st => !q || `${st.store_code} ${st.name} ${st.region} ${st.ts_name}`.toLowerCase().includes(q));
   const rows = filtered.map(st => `<tr><td><span class="store-code">${esc(st.store_code)}</span></td><td><b>${esc(st.name)}</b></td><td><span class="pc-chip">${esc(st.region)}</span></td><td><span class="role-badge">${esc(st.store_type)}</span></td><td>${esc(st.ts_name)}</td><td><b>${st.asset_count}</b> unit</td><td style="text-align:right">${adoIsAdminOrIt() ? `<button class="link-button" data-edit-store="${st.id}">Edit</button>` : '<span class="muted">&mdash;</span>'}</td></tr>`);
   document.querySelector('#adoStoreTableWrap').innerHTML = table(['Kode Store', 'Nama Store', 'Wilayah', 'Kategori Store', 'Technical Support', 'Total Perangkat', ''], rows, 'Tidak ada store yang cocok', 'Sesuaikan kata kunci pencarian.');
   document.querySelectorAll('[data-edit-store]').forEach(b => b.onclick = () => showAdoStoreModal(adoStores.find(x => x.id == b.dataset.editStore)));
  };
 }

 document.querySelector('#addAdoStore')?.addEventListener('click', () => showAdoStoreModal());
 document.querySelectorAll('[data-edit-store]').forEach(b => b.onclick = () => showAdoStoreModal(adoStores.find(x => x.id == b.dataset.editStore)));

 document.querySelectorAll('[data-confirm-tab]').forEach(b => b.onclick = () => {
  adoConfirmTab = b.dataset.confirmTab;
  renderAdo();
 });

 document.querySelectorAll('[data-confirm-do]').forEach(b => b.onclick = () => {
  const order = adoOrders.find(x => x.id == b.dataset.confirmDo);
  if (order) showAdoConfirmModal(order);
 });

 document.querySelectorAll('[data-view-do]').forEach(b => b.onclick = () => {
  const order = adoOrders.find(x => x.id == b.dataset.viewDo);
  if (order) showAdoDoDetailModal(order);
 });

 // Assets page filters & actions
 const assetSearchEl = document.querySelector('#adoAssetSearchInput');
 if (assetSearchEl) {
  let timer;
  assetSearchEl.oninput = () => {
   adoAssetSearch = assetSearchEl.value;
   clearTimeout(timer);
   timer = setTimeout(() => renderAdo(), 200);
  };
 }
 document.querySelector('#adoAssetStoreSelect')?.addEventListener('change', e => {
  adoAssetStoreFilter = e.target.value;
  renderAdo();
 });
 document.querySelector('#adoAssetStatusSelect')?.addEventListener('change', e => {
  adoAssetStatusFilter = e.target.value;
  renderAdo();
 });
 document.querySelector('#addAdoAsset')?.addEventListener('click', e => {
  showAdoAssetModal({ group_type: e.currentTarget.dataset.group || 'PERANGKAT' });
 });
 document.querySelectorAll('[data-edit-asset]').forEach(b => b.onclick = () => {
  showAdoAssetModal(adoAssets.find(x => x.id == b.dataset.editAsset));
 });
 document.querySelectorAll('[data-del-asset]').forEach(b => b.onclick = async () => {
  if (!confirm('Hapus perangkat ini dari inventaris store?')) return;
  try {
   await adoApi(`assets/${b.dataset.delAsset}`, null, 'DELETE');
   toast('Perangkat berhasil dihapus.');
   await renderAdo();
  } catch (e) { toast(e.message, 'error'); }
 });

 // DO Form events
 document.querySelectorAll('[data-do-tab]').forEach(b => b.onclick = () => {
  adoDoTab = b.dataset.doTab;
  renderAdo();
 });
 document.querySelector('#doStoreSelect')?.addEventListener('change', e => {
  adoDoSelectedStoreId = e.target.value;
  const st = adoStores.find(x => String(x.id) === String(adoDoSelectedStoreId));
  const heading = document.querySelector('#doPanelStoreHeading');
  if (heading && st) heading.textContent = `Input Data Perangkat Store ${st.store_code} - ${st.name}`;
 });
 document.querySelector('#doItemCategory')?.addEventListener('change', e => {
  const devSelect = document.querySelector('#doItemDevice');
  if (devSelect) {
   const list = adoDevicesForCategory(e.target.value);
   devSelect.innerHTML = list.map(d => `<option value="${esc(d.name)}">${esc(d.name)}</option>`).join('');
  }
 });
 document.querySelector('#doScanBtn')?.addEventListener('click', () => {
  const sn = document.querySelector('#doItemSerial');
  if (sn) { sn.focus(); sn.select(); toast('Siap scan barcode ke kolom Serial Number'); }
 });
 document.querySelector('#doAddItemBtn')?.addEventListener('click', () => {
  const category = document.querySelector('#doItemCategory')?.value || 'Pos 1';
  const device_name = document.querySelector('#doItemDevice')?.value || 'PERANGKAT';
  const brand = document.querySelector('#doItemBrand')?.value.trim() || '';
  const serial_number = document.querySelector('#doItemSerial')?.value.trim() || '';
  const purchase_year = Number(document.querySelector('#doItemYear')?.value) || new Date().getFullYear();
  const notes = document.querySelector('#doItemNotes')?.value.trim() || '';
  if (!brand && !serial_number) {
   toast('Isi minimal Merk atau Serial Number perangkat.', 'error');
   return;
  }
  adoDoDraftItems.push({ category, device_name, brand, serial_number, purchase_year, notes });
  renderAdo();
 });
 document.querySelectorAll('[data-remove-draft]').forEach(b => b.onclick = () => {
  adoDoDraftItems.splice(Number(b.dataset.removeDraft), 1);
  renderAdo();
 });
 document.querySelector('#doSaveOrderBtn')?.addEventListener('click', async e => {
  const storeId = Number(document.querySelector('#doStoreSelect')?.value || adoDoSelectedStoreId);
  if (!storeId || !adoDoDraftItems.length) return;
  e.currentTarget.disabled = true;
  try {
   const res = await adoApi('do', {
    store_id: storeId,
    store_type: adoDoTab,
    items: adoDoDraftItems,
   });
   adoDoDraftItems = [];
   toast(`Permintaan Perangkat ${res.do_number} berhasil disimpan!`);
   await renderAdo();
  } catch (err) {
   toast(err.message, 'error');
   e.currentTarget.disabled = false;
  }
 });

 // Mutation
 document.querySelector('#addAdoMutation')?.addEventListener('click', showAdoMutationModal);

 // Catalog (Super Admin)
 document.querySelector('#addCatalogCategoryForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(e.target));
  try {
   await adoApi('catalog', { kind: 'category', name: fd.name, group_type: fd.group_type });
   toast(`Area / Kategori "${fd.name}" berhasil ditambahkan.`);
   await renderAdo();
  } catch (err) { toast(err.message, 'error'); }
 });
 document.querySelectorAll('[data-add-area-device]').forEach(form => {
  form.onsubmit = async e => {
   e.preventDefault();
   const fd = Object.fromEntries(new FormData(form));
   const parent = form.dataset.addAreaDevice;
   const grp = form.dataset.areaGroup || 'PERANGKAT';
   try {
    await adoApi('catalog', { kind: 'device', name: fd.name, parent_category: parent, group_type: grp });
    toast(`Perangkat "${fd.name}" ditambahkan ke ${parent}.`);
    await renderAdo();
   } catch (err) { toast(err.message, 'error'); }
  };
 });
 document.querySelectorAll('[data-del-catalog]').forEach(b => b.onclick = async () => {
  try {
   await adoApi(`catalog/${b.dataset.delCatalog}`, null, 'DELETE');
   toast('Item master dihapus.');
   await renderAdo();
  } catch (err) { toast(err.message, 'error'); }
 });

 // Users ADO
 document.querySelector('#addAdoUserBtn')?.addEventListener('click', () => showAdoUserModal());
 document.querySelector('#openMySigFromUsersBtn')?.addEventListener('click', showAdoMySignatureModal);
 document.querySelectorAll('[data-edit-ado-user]').forEach(b => b.onclick = () => {
  showAdoUserModal(adoUsers.find(x => x.id == b.dataset.editAdoUser));
 });
}

function showAdoStoreModal(st = {}) {
 const tsList = adoUsers.filter(u => u.role === 'ts' && u.active);
 modal(`<h2>${st.id ? 'Edit Store' : 'Add Store'}</h2>
  <form id="adoStoreForm">
   <label>Kode Store</label>
   <input name="store_code" value="${esc(st.store_code || '')}" placeholder="Contoh: 00115" required maxlength="40">
   <label>Nama Store</label>
   <input name="name" value="${esc(st.name || '')}" placeholder="Contoh: HokBen Mall Grand Indonesia" required maxlength="200">
   <label>Wilayah</label>
   <select name="region">
    <option value="Jabodetabek" ${st.region !== 'Luar Jabodetabek' ? 'selected' : ''}>Jabodetabek</option>
    <option value="Luar Jabodetabek" ${st.region === 'Luar Jabodetabek' ? 'selected' : ''}>Luar Jabodetabek</option>
   </select>
   <label>Kategori Store</label>
   <select name="store_type">
    <option value="Existing Store" ${st.store_type !== 'New Store' ? 'selected' : ''}>Existing Store</option>
    <option value="New Store" ${st.store_type === 'New Store' ? 'selected' : ''}>New Store</option>
   </select>
   <label>Technical Support (TS)</label>
   <select name="ts_user_id">
    <option value="">-- Belum diassign --</option>
    ${tsList.map(u => `<option value="${u.id}" ${st.ts_user_id === u.id ? 'selected' : ''}>${esc(u.name)} (${esc(u.username)})</option>`).join('')}
   </select>
   <p><button>Simpan Store</button></p>
  </form>`);
 document.querySelector('#adoStoreForm').onsubmit = async e => {
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(e.target));
  fd.ts_user_id = fd.ts_user_id ? Number(fd.ts_user_id) : null;
  try {
   await adoApi('stores' + (st.id ? '/' + st.id : ''), fd, st.id ? 'PUT' : 'POST');
   document.querySelector('dialog')?.close();
   toast('Data Store berhasil disimpan.');
   await renderAdo();
  } catch (err) { toast(err.message, 'error'); }
 };
}

function showAdoAssetModal(a = {}) {
 if (!adoStores.length) {
  toast('Tambahkan Store terlebih dahulu di menu Data Store.', 'error');
  return;
 }
 const cats = adoCatalog.categories.length ? adoCatalog.categories : [{ name: 'Back Office' }, { name: 'Pos 1' }];
 const activeCat = a.category || cats[0].name;
 const devs = adoDevicesForCategory(activeCat);
 const curYear = new Date().getFullYear();
 modal(`<h2>${a.id ? 'Edit Perangkat Store' : 'Tambah Perangkat Store'}</h2>
  <form id="adoAssetForm">
   <label>Store</label>
   <select name="store_id" required>${adoStores.map(st => `<option value="${st.id}" ${a.store_id === st.id ? 'selected' : ''}>[${esc(st.store_code)}] ${esc(st.name)}</option>`).join('')}</select>
   <label>Grup Inventaris</label>
   <select name="group_type">
    <option value="PERANGKAT" ${a.group_type !== 'CCTV_NETWORK' ? 'selected' : ''}>Data Perangkat (Back Office / POS / Kitchen)</option>
    <option value="CCTV_NETWORK" ${a.group_type === 'CCTV_NETWORK' ? 'selected' : ''}>Data CCTV &amp; Network</option>
   </select>
   <label>Area / Kategori</label>
   <select name="category" id="modalAssetCategory">${cats.map(c => `<option value="${esc(c.name)}" ${activeCat === c.name ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select>
   <label>Nama Perangkat</label>
   <select name="device_name" id="modalAssetDevice">${devs.map(d => `<option value="${esc(d.name)}" ${a.device_name === d.name ? 'selected' : ''}>${esc(d.name)}</option>`).join('')}</select>
   <label>Merk</label>
   <input name="brand" value="${esc(a.brand || '')}" placeholder="Contoh: WEARNES, TPLINK, EPSON" required>
   <label>Serial Number</label>
   <input name="serial_number" value="${esc(a.serial_number || '')}" placeholder="Contoh: W23G00725" required>
   <label>Tahun Perangkat</label>
   <input name="purchase_year" id="modalAssetYear" type="number" min="1995" max="2100" value="${a.purchase_year || curYear}" required>
   <label>Tanggal &amp; Bulan Perangkat (Opsional)</label>
   <input name="purchase_date" id="modalAssetDate" type="date" value="${esc(a.purchase_date || new Date().toISOString().slice(0, 10))}">
   <label>Status Kondisi</label>
   <select name="status">
    <option value="normal" ${a.status === 'normal' || !a.status ? 'selected' : ''}>Normal / Aktif (Hijau)</option>
    <option value="perbaikan" ${a.status === 'perbaikan' ? 'selected' : ''}>Perbaikan (Kuning)</option>
    <option value="rusak" ${a.status === 'rusak' ? 'selected' : ''}>Rusak (Merah)</option>
   </select>
   <label>Keterangan</label>
   <input name="notes" value="${esc(a.notes || '')}" placeholder="Opsional">
   <p><button>Simpan Perangkat</button></p>
  </form>`);
 document.querySelector('#modalAssetCategory')?.addEventListener('change', e => {
  const devSelect = document.querySelector('#modalAssetDevice');
  if (devSelect) {
   const list = adoDevicesForCategory(e.target.value);
   devSelect.innerHTML = list.map(d => `<option value="${esc(d.name)}">${esc(d.name)}</option>`).join('');
  }
 });
 document.querySelector('#modalAssetDate')?.addEventListener('change', e => {
  const y = Number(String(e.target.value || '').slice(0, 4));
  const yInput = document.querySelector('#modalAssetYear');
  if (y >= 1995 && y <= 2100 && yInput) yInput.value = y;
 });
 document.querySelector('#adoAssetForm').onsubmit = async e => {
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(e.target));
  fd.store_id = Number(fd.store_id);
  fd.purchase_year = Number(fd.purchase_year);
  try {
   await adoApi('assets' + (a.id ? '/' + a.id : ''), fd, a.id ? 'PUT' : 'POST');
   document.querySelector('dialog')?.close();
   toast('Data perangkat berhasil disimpan.');
   await renderAdo();
  } catch (err) { toast(err.message, 'error'); }
 };
}

function adoReadSignatureFile(file, cb) {
 if (!file) return;
 const reader = new FileReader();
 reader.onload = () => {
  const img = new Image();
  img.onload = () => {
   const tmp = document.createElement('canvas');
   tmp.width = img.width;
   tmp.height = img.height;
   const tctx = tmp.getContext('2d');
   tctx.drawImage(img, 0, 0);
   const px = tctx.getImageData(0, 0, tmp.width, tmp.height).data;
   let minX = tmp.width, minY = tmp.height, maxX = -1, maxY = -1;
   for (let y = 0; y < tmp.height; y++) {
    for (let x = 0; x < tmp.width; x++) {
     const i = (y * tmp.width + x) * 4;
     const a = px[i + 3];
     const isInk = a > 20 && (px[i] < 242 || px[i + 1] < 242 || px[i + 2] < 242);
     if (isInk) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
     }
    }
   }
   const sx = maxX >= minX ? Math.max(0, minX - 4) : 0;
   const sy = maxY >= minY ? Math.max(0, minY - 4) : 0;
   const sw = maxX >= minX ? Math.min(tmp.width - sx, maxX - minX + 9) : tmp.width;
   const sh = maxY >= minY ? Math.min(tmp.height - sy, maxY - minY + 9) : tmp.height;
   const maxW = 460, maxH = 190;
   const ratio = Math.min(maxW / sw, maxH / sh, 1);
   const w = Math.max(1, Math.round(sw * ratio));
   const h = Math.max(1, Math.round(sh * ratio));
   const c = document.createElement('canvas');
   c.width = w;
   c.height = h;
   c.getContext('2d').drawImage(tmp, sx, sy, sw, sh, 0, 0, w, h);
   cb(c.toDataURL('image/png'));
  };
  img.src = reader.result;
 };
 reader.readAsDataURL(file);
}

function showAdoConfirmModal(order) {
 const cats = adoCatalog.categories.length ? adoCatalog.categories : [{ name: 'Back Office' }, { name: 'Pos 1' }];
 const draftItems = (order.items || []).map(it => ({ ...it }));
 const todayIso = new Date().toISOString().slice(0, 10);
 let currentSig = adoMe?.signature_data || '';

 modal(`<h2>Review, Edit &amp; Konfirmasi DO</h2>
  <form id="adoConfirmDoForm">
   <div class="ado-confirm-grid">
    <div>
     <label>Nomor DO</label>
     <input name="do_number" value="${esc(order.do_number)}" required>
    </div>
    <div>
     <label>Delivery Date</label>
     <input name="delivery_date" type="date" value="${esc(order.delivery_date || todayIso)}">
    </div>
    <div>
     <label>Store Tujuan</label>
     <select name="store_id">${adoStores.map(st => `<option value="${st.id}" ${order.store_id === st.id ? 'selected' : ''}>[${esc(st.store_code)}] ${esc(st.name)}</option>`).join('')}</select>
    </div>
    <div>
     <label>Tipe Store</label>
     <select name="store_type">
      <option value="Existing Store" ${order.store_type !== 'New Store' ? 'selected' : ''}>Existing Store</option>
      <option value="New Store" ${order.store_type === 'New Store' ? 'selected' : ''}>New Store</option>
     </select>
    </div>
    <div>
     <label>Checked by (Team IT)</label>
     <input name="ts_name" value="${esc(order.ts_name || '')}" placeholder="Nama TS">
    </div>
    <div>
     <label>Approved by (Admin IT)</label>
     <input name="confirmed_by" value="${esc(adoMe?.name || '')}" placeholder="Nama Admin IT (misal: Vani / Laras)" required>
    </div>
   </div>

   <div style="display:flex;justify-content:space-between;align-items:center;margin:14px 0 6px">
    <b>Daftar Perangkat di DO</b>
    <button type="button" id="confirmAddRowBtn" class="secondary compact">+ Tambah Baris</button>
   </div>
   <div id="confirmItemsWrap" class="ado-confirm-items"></div>

   <div class="ado-sig-panel">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px">
     <b>Attachment Tanda Tangan (TTD) Admin IT</b>
     <div style="display:flex;gap:8px;align-items:center">
      <button type="button" id="doSigToggleDrawBtn" class="secondary compact">Atau Gambar Manual</button>
      <button type="button" id="doSigClearBtn" class="secondary compact">Hapus TTD</button>
     </div>
    </div>
    <div class="ado-sig-body">
     <label class="ado-sig-upload-box" for="doSigFileInput">
      <b>&#128206; Pilih / Attach File Gambar TTD</b>
      <small>Format PNG, JPG, atau WEBP (disarankan PNG transparan / latar putih)</small>
      <input type="file" id="doSigFileInput" accept="image/png,image/jpeg,image/webp" hidden>
     </label>
     <div>
      <small class="muted" style="display:block;margin-bottom:4px">Preview TTD pada Form DO:</small>
      <div id="doSigPreview" class="ado-sig-preview"></div>
     </div>
    </div>
    <div id="doSigCanvasWrap" hidden style="margin-top:10px">
     <small class="muted" style="display:block;margin-bottom:4px">Gambar TTD manual di kotak ini:</small>
     <canvas id="doSigCanvas" width="320" height="105" class="ado-sig-canvas"></canvas>
    </div>
    <label style="display:flex;align-items:center;gap:8px;margin-top:8px;font-weight:500">
     <input type="checkbox" id="saveUserSigCheck" style="width:auto;margin:0" checked>
     Simpan TTD ini sebagai TTD default akun saya (${esc(adoMe?.name || '')})
    </label>
   </div>

   <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:16px;flex-wrap:wrap">
    <button type="button" id="saveDoDraftBtn" class="secondary">Simpan Perubahan Saja</button>
    <button type="submit" id="submitConfirmDoBtn" class="ado-confirm-btn" style="padding:10px 18px;font-size:13.5px">&#10004; Konfirmasi &amp; ACC DO</button>
   </div>
  </form>`);

 const dlg = document.querySelector('dialog');
 if (dlg) dlg.style.maxWidth = '860px';

 const renderItems = () => {
  const wrap = document.querySelector('#confirmItemsWrap');
  wrap.innerHTML = draftItems.map((it, idx) => {
   const catOpts = cats.map(c => `<option value="${esc(c.name)}" ${it.category === c.name ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
   const devs = adoDevicesForCategory(it.category || cats[0].name);
   const devOpts = devs.map(d => `<option value="${esc(d.name)}" ${it.device_name === d.name ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
   return `<div class="ado-confirm-item-row" data-idx="${idx}">
    <select data-f="category">${catOpts}</select>
    <select data-f="device_name">${devOpts}</select>
    <input data-f="brand" value="${esc(it.brand || '')}" placeholder="Merk">
    <input data-f="serial_number" value="${esc(it.serial_number || '')}" placeholder="Serial Number">
    <input data-f="notes" value="${esc(it.notes || '')}" placeholder="Keterangan (Replace)">
    <button type="button" class="secondary compact" style="color:#cf535a" data-del-row="${idx}" ${draftItems.length <= 1 ? 'disabled' : ''}>&times;</button>
   </div>`;
  }).join('');
  wrap.querySelectorAll('.ado-confirm-item-row').forEach(row => {
   const idx = Number(row.dataset.idx);
   row.querySelector('[data-f="category"]').onchange = e => {
    draftItems[idx].category = e.target.value;
    const list = adoDevicesForCategory(e.target.value);
    draftItems[idx].device_name = list[0]?.name || draftItems[idx].device_name;
    renderItems();
   };
   row.querySelector('[data-f="device_name"]').onchange = e => { draftItems[idx].device_name = e.target.value; };
   row.querySelector('[data-f="brand"]').oninput = e => { draftItems[idx].brand = e.target.value; };
   row.querySelector('[data-f="serial_number"]').oninput = e => { draftItems[idx].serial_number = e.target.value; };
   row.querySelector('[data-f="notes"]').oninput = e => { draftItems[idx].notes = e.target.value; };
   row.querySelector('[data-del-row]').onclick = () => {
    if (draftItems.length > 1) { draftItems.splice(idx, 1); renderItems(); }
   };
  });
 };
 renderItems();

 document.querySelector('#confirmAddRowBtn').onclick = () => {
  const cat = cats[0].name;
  const dev = adoDevicesForCategory(cat)[0]?.name || 'PC OFFICE';
  draftItems.push({ category: cat, device_name: dev, brand: '', serial_number: '', purchase_year: new Date().getFullYear(), notes: 'Replace' });
  renderItems();
 };

 const sigPreview = document.querySelector('#doSigPreview');
 const canvas = document.querySelector('#doSigCanvas');
 const ctx = canvas.getContext('2d');
 ctx.lineWidth = 2.2;
 ctx.lineCap = 'round';
 ctx.lineJoin = 'round';
 ctx.strokeStyle = '#111';

 const syncSigPreview = () => {
  sigPreview.innerHTML = currentSig
   ? `<img src="${currentSig}" alt="Preview TTD" style="max-height:80px;max-width:100%;object-fit:contain">`
   : '<span class="muted" style="font-size:12px">Belum ada TTD terpasang</span>';
 };
 syncSigPreview();

 let drawing = false;
 let hasDrawn = false;
 const pt = e => {
  const r = canvas.getBoundingClientRect();
  const src = e.touches ? e.touches[0] : e;
  return { x: (src.clientX - r.left) * (canvas.width / r.width), y: (src.clientY - r.top) * (canvas.height / r.height) };
 };
 const startDraw = e => { drawing = true; hasDrawn = true; const p = pt(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); };
 const moveDraw = e => { if (!drawing) return; e.preventDefault(); const p = pt(e); ctx.lineTo(p.x, p.y); ctx.stroke(); };
 const endDraw = () => { if (!drawing) return; drawing = false; if (hasDrawn) { currentSig = canvas.toDataURL('image/png'); syncSigPreview(); } };
 canvas.addEventListener('mousedown', startDraw);
 canvas.addEventListener('mousemove', moveDraw);
 window.addEventListener('mouseup', endDraw);
 canvas.addEventListener('touchstart', startDraw, { passive: false });
 canvas.addEventListener('touchmove', moveDraw, { passive: false });
 canvas.addEventListener('touchend', endDraw);

 document.querySelector('#doSigToggleDrawBtn').onclick = () => {
  const wrap = document.querySelector('#doSigCanvasWrap');
  if (wrap) wrap.hidden = !wrap.hidden;
 };
 document.querySelector('#doSigFileInput').onchange = e => {
  adoReadSignatureFile(e.target.files?.[0], dataUrl => {
   ctx.clearRect(0, 0, canvas.width, canvas.height);
   currentSig = dataUrl;
   syncSigPreview();
  });
 };
 document.querySelector('#doSigClearBtn').onclick = () => {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  currentSig = '';
  hasDrawn = false;
  syncSigPreview();
 };

 const buildPayload = () => {
  const fd = new FormData(document.querySelector('#adoConfirmDoForm'));
  return {
   do_number: String(fd.get('do_number') || '').trim(),
   delivery_date: String(fd.get('delivery_date') || '').trim(),
   store_id: Number(fd.get('store_id')),
   store_type: String(fd.get('store_type') || 'Existing Store'),
   ts_name: String(fd.get('ts_name') || '').trim(),
   confirmed_by: String(fd.get('confirmed_by') || '').trim(),
   approved_signature: currentSig,
   save_user_signature: Boolean(document.querySelector('#saveUserSigCheck')?.checked),
   items: draftItems.map(it => ({
    category: it.category,
    device_name: it.device_name,
    brand: it.brand || '',
    serial_number: it.serial_number || '',
    purchase_year: Number(it.purchase_year) || new Date().getFullYear(),
    notes: it.notes || '',
   })),
  };
 };

 document.querySelector('#saveDoDraftBtn').onclick = async () => {
  try {
   const res = await adoApi(`do/${order.id}`, buildPayload(), 'PUT');
   document.querySelector('dialog')?.close();
   toast(`Perubahan DO ${res.do_number} berhasil disimpan.`);
   await renderAdo();
  } catch (err) { toast(err.message, 'error'); }
 };

 document.querySelector('#adoConfirmDoForm').onsubmit = async e => {
  e.preventDefault();
  const payload = buildPayload();
  const btn = document.querySelector('#submitConfirmDoBtn');
  btn.disabled = true;
  try {
   const res = await adoApi(`do/${order.id}/confirm`, payload, 'POST');
   if (payload.save_user_signature && payload.approved_signature && adoMe) {
    adoMe.signature_data = payload.approved_signature;
   }
   document.querySelector('dialog')?.close();
   toast(`DO ${res.do_number} dikonfirmasi oleh ${res.confirmed_by}! ${res.added_assets || 0} perangkat masuk ke aset store.`);
   await renderAdo();
  } catch (err) {
   toast(err.message, 'error');
   btn.disabled = false;
  }
 };
}

function showAdoDoDetailModal(order) {
 modal(`<h2>Delivery Order Form: ${esc(order.do_number)}</h2>
  <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin:8px 0 12px">
   <div>
    <span class="role-badge">${esc(order.store_type)}</span>
    <span style="margin-left:8px;font-size:13px"><b>[${esc(order.store_code)}] ${esc(order.store_name)}</b> &middot; TS: <b>${esc(order.ts_name)}</b></span>
   </div>
   <div style="display:flex;gap:8px;flex-wrap:wrap">
    <a class="download-button" style="margin:0;padding:8px 14px;font-size:12.5px" href="/api/ado/do/${order.id}/print?autoprint=1" target="_blank" rel="noopener">&#128424; Print / Simpan PDF</a>
    <a class="secondary compact" style="text-decoration:none;padding:8px 12px;border-radius:8px;font-size:12.5px" href="/api/ado/do/${order.id}/print" target="_blank" rel="noopener">Buka Tab Penuh &nearr;</a>
    ${order.status !== 'confirmed' && adoIsAdminOrIt() ? `<button type="button" id="modalConfirmDoBtn" class="ado-confirm-btn">&#10004; Review, Edit &amp; Konfirmasi</button>` : ''}
   </div>
  </div>
  <div style="border:1px solid var(--border);border-radius:10px;overflow:hidden;background:#eef2f5">
   <iframe src="/api/ado/do/${order.id}/print" title="Preview Delivery Order ${esc(order.do_number)}" style="width:100%;height:68vh;border:0;display:block"></iframe>
  </div>`);
 const dlg = document.querySelector('dialog');
 if (dlg) dlg.style.maxWidth = '880px';
 document.querySelector('#modalConfirmDoBtn')?.addEventListener('click', () => {
  document.querySelector('dialog')?.close();
  showAdoConfirmModal(order);
 });
}

function showAdoMutationModal() {
 if (!adoAssets.length || adoStores.length < 2) {
  toast('Minimal harus ada 2 store dan perangkat terdaftar untuk melakukan mutasi.', 'error');
  return;
 }
 modal(`<h2>Mutasi Perangkat Antar Store</h2>
  <form id="adoMutationForm">
   <label>Pilih Perangkat yang Akan Dipindahkan</label>
   <select name="asset_id" required>${adoAssets.map(a => `<option value="${a.id}">[${esc(a.store_code)} - ${esc(a.store_name)}] ${esc(a.device_name)} (${esc(a.brand)} / SN: ${esc(a.serial_number)})</option>`).join('')}</select>
   <label>Pindahkan ke Store Tujuan</label>
   <select name="to_store_id" required>${adoStores.map(st => `<option value="${st.id}">[${esc(st.store_code)}] ${esc(st.name)}</option>`).join('')}</select>
   <label>Alasan / Keterangan Mutasi</label>
   <input name="notes" placeholder="Contoh: Backup pengganti unit rusak / relokasi store" required>
   <p><button>Proses Mutasi Perangkat</button></p>
  </form>`);
 document.querySelector('#adoMutationForm').onsubmit = async e => {
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(e.target));
  fd.asset_id = Number(fd.asset_id);
  fd.to_store_id = Number(fd.to_store_id);
  try {
   await adoApi('mutations', fd);
   document.querySelector('dialog')?.close();
   toast('Mutasi perangkat berhasil dicatat & lokasi store diperbarui.');
   await renderAdo();
  } catch (err) { toast(err.message, 'error'); }
 };
}

function showAdoMySignatureModal() {
 let mySig = adoMe?.signature_data || '';
 modal(`<h2>Attachment Tanda Tangan (TTD) Saya</h2>
  <p class="muted" style="margin-top:0">Attach gambar TTD untuk akun <b>${esc(adoMe?.name || '')}</b>. TTD ini otomatis terpasang saat konfirmasi / ACC Delivery Order.</p>
  <div class="ado-sig-panel" style="margin-top:10px">
   <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px">
    <b>Attachment File Gambar TTD</b>
    <div style="display:flex;gap:8px;align-items:center">
     <button type="button" id="mySigToggleDrawBtn" class="secondary compact">Atau Gambar Manual</button>
     <button type="button" id="mySigClearBtn" class="secondary compact">Hapus TTD</button>
    </div>
   </div>
   <div class="ado-sig-body">
    <label class="ado-sig-upload-box" for="mySigFileInput">
     <b>&#128206; Pilih / Attach File Gambar TTD</b>
     <small>Format PNG, JPG, atau WEBP</small>
     <input type="file" id="mySigFileInput" accept="image/png,image/jpeg,image/webp" hidden>
    </label>
    <div id="mySigPreview" class="ado-sig-preview"></div>
   </div>
   <div id="mySigCanvasWrap" hidden style="margin-top:10px">
    <small class="muted" style="display:block;margin-bottom:4px">Gambar TTD manual di kotak ini:</small>
    <canvas id="mySigCanvas" width="320" height="105" class="ado-sig-canvas"></canvas>
   </div>
  </div>
  <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:14px">
   <button type="button" id="saveMySigBtn">Simpan TTD Saya</button>
  </div>`);
 const dlg = document.querySelector('dialog');
 if (dlg) dlg.style.maxWidth = '720px';
 const preview = document.querySelector('#mySigPreview');
 const canvas = document.querySelector('#mySigCanvas');
 const ctx = canvas.getContext('2d');
 ctx.lineWidth = 2.2; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#111';
 const sync = () => {
  preview.innerHTML = mySig
   ? `<img src="${mySig}" alt="Preview TTD" style="max-height:80px;max-width:100%;object-fit:contain">`
   : '<span class="muted" style="font-size:12px">Belum ada TTD terpasang</span>';
 };
 sync();
 let drawing = false, hasDrawn = false;
 const pt = e => {
  const r = canvas.getBoundingClientRect();
  const s = e.touches ? e.touches[0] : e;
  return { x: (s.clientX - r.left) * (canvas.width / r.width), y: (s.clientY - r.top) * (canvas.height / r.height) };
 };
 const startDraw = e => { drawing = true; hasDrawn = true; const p = pt(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); };
 const moveDraw = e => { if (!drawing) return; e.preventDefault(); const p = pt(e); ctx.lineTo(p.x, p.y); ctx.stroke(); };
 const endDraw = () => { if (!drawing) return; drawing = false; if (hasDrawn) { mySig = canvas.toDataURL('image/png'); sync(); } };
 canvas.addEventListener('mousedown', startDraw);
 canvas.addEventListener('mousemove', moveDraw);
 window.addEventListener('mouseup', endDraw);
 canvas.addEventListener('touchstart', startDraw, { passive: false });
 canvas.addEventListener('touchmove', moveDraw, { passive: false });
 canvas.addEventListener('touchend', endDraw);
 document.querySelector('#mySigToggleDrawBtn').onclick = () => {
  const wrap = document.querySelector('#mySigCanvasWrap');
  if (wrap) wrap.hidden = !wrap.hidden;
 };
 document.querySelector('#mySigFileInput').onchange = e => {
  adoReadSignatureFile(e.target.files?.[0], dataUrl => { ctx.clearRect(0, 0, canvas.width, canvas.height); mySig = dataUrl; sync(); });
 };
 document.querySelector('#mySigClearBtn').onclick = () => { ctx.clearRect(0, 0, canvas.width, canvas.height); mySig = ''; hasDrawn = false; sync(); };
 document.querySelector('#saveMySigBtn').onclick = async () => {
  try {
   await adoApi('me/signature', { signature_data: mySig }, 'PUT');
   if (adoMe) adoMe.signature_data = mySig;
   document.querySelector('dialog')?.close();
   toast('TTD default berhasil disimpan.');
   await renderAdo();
  } catch (err) { toast(err.message, 'error'); }
 };
}

function showAdoUserModal(u = {}) {
 let userSig = u.signature_data || '';
 modal(`<h2>${u.id ? 'Edit' : 'Tambah'} User ADO</h2>
  <form id="adoUserForm">
   <label>Nama Lengkap</label>
   <input name="name" value="${esc(u.name || '')}" required>
   <label>Username</label>
   <input name="username" value="${esc(u.username || '')}" required>
   <label>Password ${u.id ? 'baru (kosongkan jika tidak diubah)' : ''}</label>
   <input name="password" type="password" ${u.id ? '' : 'required'} minlength="1">
   <label>Role di ADO</label>
   <select name="role" id="adoUserRoleSelect">
    <option value="ts" ${u.role === 'ts' || !u.role ? 'selected' : ''}>TS (Technical Support)</option>
    <option value="admin_it" ${u.role === 'admin_it' ? 'selected' : ''}>Admin IT (Konfirmasi DO &amp; Kelola Store)</option>
    <option value="super_admin" ${u.role === 'super_admin' ? 'selected' : ''}>Super Admin (Akses Penuh)</option>
   </select>
   <div id="adoUserStoreAssignBox">
    <label>Pilih Store Pegangan TS</label>
    <div class="pc-access">${adoStores.map(st => `<label><input style="width:auto" type="checkbox" name="store_ids" value="${st.id}" ${(u.store_ids || []).includes(st.id) ? 'checked' : ''}> <b>[${esc(st.store_code)}]</b> ${esc(st.name)} (${esc(st.region)})</label>`).join('') || '<p class="muted">Belum ada store. Tambahkan di menu Data Store.</p>'}</div>
   </div>
   <div style="margin-top:10px">
    <label>Tanda Tangan Default (Admin IT / Super Admin)</label>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
     <label class="secondary compact" style="margin:0;cursor:pointer;padding:6px 10px;border-radius:8px;border:1px solid var(--border);font-size:12px">
      Upload Gambar TTD
      <input type="file" id="adoUserSigFile" accept="image/png,image/jpeg,image/webp" hidden>
     </label>
     <button type="button" id="adoUserSigClear" class="secondary compact">Hapus TTD</button>
     <span id="adoUserSigPreview">${userSig ? `<img src="${userSig}" style="max-height:36px;border:1px solid var(--border);border-radius:6px;padding:2px;background:#fff">` : '<small class="muted">Belum ada TTD</small>'}</span>
    </div>
   </div>
   <label style="margin-top:10px"><input style="width:auto" type="checkbox" name="active" ${u.active !== false ? 'checked' : ''}> Akun Aktif</label>
   <p><button>Simpan User ADO</button></p>
  </form>`);
 document.querySelector('#adoUserSigFile')?.addEventListener('change', e => {
  adoReadSignatureFile(e.target.files?.[0], dataUrl => {
   userSig = dataUrl;
   document.querySelector('#adoUserSigPreview').innerHTML = `<img src="${userSig}" style="max-height:36px;border:1px solid var(--border);border-radius:6px;padding:2px;background:#fff">`;
  });
 });
 document.querySelector('#adoUserSigClear')?.addEventListener('click', () => {
  userSig = '';
  document.querySelector('#adoUserSigPreview').innerHTML = '<small class="muted">Belum ada TTD</small>';
 });
 const roleSelect = document.querySelector('#adoUserRoleSelect');
 const storeBox = document.querySelector('#adoUserStoreAssignBox');
 const syncRole = () => { storeBox.hidden = roleSelect.value !== 'ts'; };
 roleSelect.onchange = syncRole;
 syncRole();
 document.querySelector('#adoUserForm').onsubmit = async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = {
   name: fd.get('name'),
   username: fd.get('username'),
   role: fd.get('role'),
   active: e.target.active.checked,
   store_ids: fd.getAll('store_ids').map(Number),
   signature_data: userSig,
  };
  if (fd.get('password')) payload.password = fd.get('password');
  try {
   await adoApi('users' + (u.id ? '/' + u.id : ''), payload, u.id ? 'PUT' : 'POST');
   document.querySelector('dialog')?.close();
   toast('User ADO berhasil disimpan.');
   await renderAdo();
  } catch (err) { toast(err.message, 'error'); }
 };
}
