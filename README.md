# SIMON - Sistem Monitoring

Monitoring hardware PC store dengan agent Windows ringan. Super Admin melihat semua PC dan mengelola assignment; TS hanya melihat PC yang diberikan. Instalasi kecil dapat memakai SQLite; deployment kantor hingga ratusan store memakai PostgreSQL lokal. Tidak membutuhkan Node, Docker, atau layanan cloud berbayar.

## Server PC kantor

IP: **172.18.123.92**. Repo: https://github.com/RhenoSeptianto/SIMON.git

```powershell
New-Item -ItemType Directory -Force D:\IT | Out-Null
Set-Location D:\IT
git clone https://github.com/RhenoSeptianto/SIMON.git simon
```

1. Pasang Git for Windows. Setup otomatis memasang Python **3.12 x64** lewat `winget` jika belum tersedia; PC perlu internet dan `winget`/App Installer.
2. Jika ingin membawa akun/data saat ini, salin folder `data` secara privat ke `D:\IT\simon\data` sebelum setup. Folder ini tidak masuk GitHub. Hentikan backend sumber saat menyalin database. Jangan salin `.venv`.
3. Klik kanan `deployment\server\setup-server.bat` -> **Run as administrator**.
4. Buka **https://172.18.123.92:8443**. Pada instalasi baru, setup meminta password admin (username `admin`) dan password awal 9 akun TS. Database yang sudah ada tidak diubah passwordnya.

Setup memasang Python 3.12 x64 dan dependency server secara otomatis jika runtime atau Python Launcher belum tersedia, memeriksa dependency dan kesehatan backend, serta mencadangkan `.venv` yang tidak valid sebelum membuat ulang. Jika `winget` tidak ada, setup menampilkan petunjuk instalasi manual. PC perlu internet untuk mengunduh komponen. Semua path operasional dihitung relatif dari root proyek `D:\IT\simon`; database, konfigurasi, sertifikat, dan credential tidak dihapus. Server otomatis hidup saat boot melalui Task Scheduler, tanpa perlu login atau terminal terbuka. Matikan sleep PC kantor. Tidak ada jadwal backup harian otomatis. Log: `data\logs\server.log`. Backup manual tersedia di menu Database (Super Admin).

Untuk deployment kantor berskala besar, update SIMON ke versi 1.1.1 dahulu, jalankan `git pull --ff-only origin main` pada checkout server, instal PostgreSQL for Windows, lalu klik kanan `deployment\server\migrate-postgresql.bat` → **Run as administrator**. Script meminta password administrator PostgreSQL, menghentikan server sebentar, membuat backup SQLite, memindahkan seluruh data dalam transaksi, mengaktifkan PostgreSQL, memeriksa HTTPS/database, dan memasang ulang helper UpdateSimon. File SQLite lama tidak dihapus dan agent store tidak perlu dipasang ulang. Panduan: [Migrasi PostgreSQL](docs/POSTGRESQL.md).

**Panduan lengkap:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Paket agent store

1. Download build GitHub Actions `SIMONAgent-template.zip`, atau build di Windows lewat `tools\build-agent.bat`.
2. Simpan template di `D:\IT\simon\release\SIMONAgent-template.zip` pada PC kantor.
3. Jalankan `deployment\server\make-agent-package.bat`. Hasil: **release\SIMONAgent-store.zip**, berisi binary dan sertifikat **publik** server kantor.
4. Bagikan ZIP store, ekstrak, klik kanan **install.bat -> Run as administrator** sekali pada setiap PC store.

Agent berupa `.exe` dengan Windows Service `SIMONAgent`, otomatis aktif saat Windows dinyalakan, tanpa login dan tanpa Python di store. Ekstrak ke lokasi permanen seperti `D:\SIMONAgent-store`: EXE, config, XML dan folder data tetap di dalam subfolder `SIMONAgent`. Identitas lama di ProgramData disalin saat migrasi tanpa menghapus sumber. Jangan pindahkan folder setelah instalasi. Jangan salin state antarkomputer. Installer update mempertahankan UUID. `status.bat`, `start.bat`, `stop.bat`, `diagnose.bat`, `uninstall.bat` tersedia dalam paket.

PC store harus Windows 10/11 **x64** dan bisa menjangkau `172.18.123.92:8443` melalui LAN/VPN. IP private tersebut tidak bisa diakses melalui internet biasa tanpa routing/VPN. Koneksi agent outbound HTTPS; tidak membuka port inbound pada PC store. Verifikasi sertifikat selalu aktif. Sertifikat/private key kantor dibuat saat setup, tidak disimpan di GitHub. Hanya `ca.crt` publik yang masuk paket store.

## Jadwal dan data

- Status koneksi: sekitar **10 detik**.
- CPU/RAM/sisa drive: sekitar **10 detik**.
- Suhu/health SSD/HDD: **mengikuti perubahan HDSentinel.xml**, umumnya setiap 10 detik sesuai ekspor Sentinel.
- Inventory statis: saat mulai dan setiap 24 jam.

Interval heartbeat/metrics/inventory memakai jitter 10%, dapat dikonfigurasi lewat `SIAMS_INTERVAL_HEARTBEAT`, `SIAMS_INTERVAL_METRICS`, `SIAMS_INTERVAL_INVENTORY` (detik). Pemeriksaan disk tidak lagi memakai jadwal 16.00 atau PowerShell; agent hanya membaca XML saat file berubah. Variabel `SIAMS_INTERVAL_STORAGE` lama diabaikan. Sensor tidak tersedia = N/A. Wear nol bukan berarti sisa umur 100%. Refresh dashboard mengambil kiriman terakhir, tidak menjalankan koleksi paksa.

Antrean offline dibatasi 2.000 event (event tertua dibuang saat penuh), timeout HTTP 15 detik, collector PowerShell 35 detik. Retry backoff maksimal 300 detik. Log agent berotasi 1 MiB, 4 file. Histori telemetry disimpan default 30 hari, dibersihkan saat ingestion. UUID stabil meskipun IP/hostname berubah.

## Dashboard

Overview, Devices dengan pencarian/status/pagination, detail PC bertab, grafik CPU/RAM interaktif, assignment TS melalui dropdown, Users, Alerts storage, Laporan Excel tiga sheet, Audit, dan Database backup/reset. Reset memerlukan konfirmasi RESET, membuat backup terlebih dahulu, menghapus data monitoring tetapi mempertahankan akun/password dan audit. Semua user bisa mengganti password sendiri, minimal satu karakter. Perubahan password mengakhiri seluruh sesi akun.

Hapus PC menghapus histori, alert dan assignment. Jika agent masih aktif, perangkat otomatis mendaftar dan mengirim data kembali dengan UUID/kode store yang sama; assignment TS perlu diberikan lagi. Tidak ada tombol Revoke. Untuk menghentikan pengiriman seterusnya, hentikan/uninstall service pada PC store. Menghapus dari dashboard tidak menghentikan service Windows dari jarak jauh.

## Development lokal

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m backend.create_admin admin
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Terminal kedua:

```powershell
.\.venv\Scripts\python.exe -m agent.main --server http://127.0.0.1:8000
```

HTTP hanya diizinkan untuk loopback development. Agent juga mendukung `--config`, `--ca-file`, `--state`, `--once`, dan `--diagnose`. OpenAPI: `/docs`. Config/environment teknis tetap memakai beberapa nama SIAMS untuk kompatibilitas instalasi/data lama, termasuk SQLite `data/siams.db` dan cookie sesi. Environment server: `SIAMS_DATA`, `DATABASE_URL`, `OFFLINE_SECONDS` (override; default agent baru sekitar 45 detik, agent lama 420 detik), `RETENTION_DAYS` (30), `SIAMS_PRODUCTION` (otomatis 1 pada runner kantor).

## Tes dan build

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests\browser_details.py
```

Browser test opsional memakai Microsoft Edge dan database sementara. Build agent memerlukan Windows x64: jalankan `tools/build-agent.bat`; hasil template tidak berisi sertifikat/credential kantor. Smoke test executable (sesudah build) menggunakan `python tests/frozen_smoke.py`, memerlukan cryptography dan backend dependencies serta memakai database/HTTPS sementara.

`python -m tools.package_source` membuat `release/SIMON-source.zip` dengan source terpilih untuk upload GitHub. Jangan upload seluruh folder proyek sebagai ZIP: `.venv`, `data`, `release`, database, private key dan credential harus tetap lokal. CI otomatis membuild template agent melalui GitHub Actions setelah source diupload. Panduan restore dan update ada pada docs/DEPLOYMENT.md.

Binary berhasil dibuild dan diuji mengirim hardware aktual melalui HTTPS, namun service startup/recovery/reboot, koneksi VPN, dan dampak CPU/RAM pada PC store tetap perlu pilot sebelum rollout. Binary belum code-signed. [Status implementasi](docs/STATUS.md) mencatat batas fitur produksi yang belum selesai.


## Hard Disk Sentinel dan kode store

Pada PC store, atur Sentinel untuk mengekspor XML otomatis tiap 10 detik ke `D:\SIMONAgent-store\SIMONAgent\HDSentinel.xml` (sesuaikan lokasi paket). Installer meminta kode store, mempertahankan nol di depan (contoh 00115), dan menyimpannya sebagai metadata perangkat. Saat update installer, Enter mempertahankan kode lama. Kode tampil di Devices/detail PC/Excel dan dapat dicari. Ini bukan relasi store-user: assignment user tetap langsung ke PC.

Agent memantau timestamp/ukuran file sekitar 5?8 detik sekali, membaca file yang berubah dengan validasi ukuran/stabilitas/XML, mencocokkan disk lewat serial, lalu mengirim ringkasan. Tidak menjalankan disk scan Windows/PowerShell. File missing/partial/error/stale (>2 menit) ditampilkan tanpa menghapus kondisi terakhir. Waktu laporan dan status pemantauan dari XML ditampilkan agar data tidak disalahartikan sebagai pengukuran langsung. Health dan performance adalah nilai Sentinel, bukan wear. Total kapasitas memakai jumlah sektor dikali bytes per sector jika tersedia. Data disk terbaru pada detail diperiksa ulang setiap 10 detik saat jendela terbuka.

Snapshot disk disimpan hanya sebagai kondisi terbaru, bukan baris histori. Antrean offline disk juga digabung menjadi snapshot terbaru. Histori CPU/RAM/drive tetap 5 menit. Alert menyimpan health turun dibanding laporan sebelumnya, health di bawah batas (default 80%, environment SENTINEL_HEALTH_WARNING), suhu >65 C, dan perubahan identitas disk; kondisi berulang dideduplikasi. Saat agent offline, perubahan sementara yang tidak sempat dikirim tidak dijamin masuk riwayat alert. File XML asli dan informasi registrasi Sentinel tidak diupload ke GitHub.

Update ini **memerlukan build EXE baru**. Urutan: git pull pada kantor, jalankan setup-server.bat untuk memperbarui server/migrasi kolom kode store, jalankan tools/build-agent.bat atau download template GitHub Actions terbaru, lalu make-agent-package.bat. Template lama ditolak lewat manifest/checksum agar agent jadwal lama tidak terselip dalam paket baru. Install ulang paket baru di store, isi kode store, dan pastikan Sentinel memperbarui XML. Identitas/queue/assignment tetap dipertahankan.


Pendaftaran ulang setelah hapus membutuhkan EXE terbaru dengan capability reenrollment_after_delete. Agent yang menerima HTTP 401 membuang credential yang tidak berlaku, menyimpan UUID/claim secara atomik, lalu enrollment ulang pada siklus berikutnya. Queue tetap dipertahankan, snapshot Sentinel dan metrics dipaksa dikirim lagi. Jika installer/agent lama masih terpasang, update paket agar mekanisme ini tersedia. Tampilan suhu memakai simbol derajat HTML (&deg;C) dan N/A untuk data kosong.


## Bahasa Indonesia dan laporan Excel

Keterangan, saran, status pemantauan, perkiraan sisa umur dan waktu laporan Sentinel ditampilkan dalam bahasa Indonesia. Terjemahan deterministik/offline dilakukan server saat penyajian; data sumber tetap disimpan untuk diagnosis. Pesan yang belum dikenali tidak ditebak sebagai kondisi sehat: pengguna diarahkan memeriksa laporan Sentinel. Atribut teknis yang belum mempunyai padanan dapat dipertahankan sebagai identitas agar dapat dicocokkan dengan Sentinel.

Menu Laporan hanya menyediakan Excel: endpoint /api/reports/xlsx. Format CSV tidak lagi tersedia. File SIMON-Inventaris-YYYY-MM-DD.xlsx menggunakan tanggal WIB dan memiliki sheet Perangkat, SSD-HDD (nama sheet Excel tidak mendukung karakter /), serta Kapasitas Drive. Satu disk/volume per baris, judul kolom bahasa Indonesia, satuan GiB/persen, header dibekukan, tabel/filter, lebar kolom dan pembungkusan teks. Kode store dipertahankan sebagai teks, nilai numerik tetap angka, tanggal menjadi tanggal Excel, dan teks dari perangkat tidak dieksekusi sebagai formula. Nilai kosong ditulis Tidak tersedia.

Terjemahan dan Excel ini hanya memerlukan update/restart server serta Ctrl+F5 pada browser. Tidak memerlukan perubahan config, installer atau rebuild agent.


## Pembaruan angka terbaru setiap 10 detik

Default heartbeat dan koleksi CPU/RAM/kapasitas drive menjadi 10 detik dengan jitter kecil. Tampilan daftar dan detail juga mengambil pembaruan sekitar 10 detik. XML Sentinel tetap mengikuti perubahan file. Historinya dipisahkan: server menyimpan sampel CPU/RAM setiap 300 detik (HISTORY_INTERVAL_SECONDS), tetapi kondisi terbaru tetap diupdate setiap kiriman. Ini mencegah histori membesar 30 kali lipat. Ketika agent baru berhenti, status offline memakai toleransi 45 detik agar kehilangan satu paket tidak langsung dianggap putus. Agent lama tanpa metadata interval tetap diberi jendela 420 detik saat rollout; OFFLINE_SECONDS dapat mengoverride toleransi.

Jadwal ada di EXE agent: build/pasang paket baru untuk menerapkan 10 detik. Template format 5 dengan capability ten_second_metrics dan in_place_install diperlukan. Update server lebih dahulu, lalu build agent, buat paket store dan install ulang. UUID/config/kode store dipertahankan. Tidak ada perubahan interval inventory statis (24 jam). Loop ringan memeriksa metadata XML sekitar satu detik; file diparse/dikirim hanya saat berubah. Tidak ada pemanggilan disk scan tambahan.

Log pemasangan: `install.log` di folder paket. Jalankan `check-agent.bat` sebagai Administrator untuk laporan `check-agent.log` berisi status service, akses file/data, koneksi HTTPS, log worker dan event keamanan Windows terkait. Access denied tidak otomatis berarti Sangfor memblokir; cocokkan dengan konsol Sangfor.

## Startup user tanpa service

Default install.bat kini memasang mode Startup user tanpa administrator. Isi kode store; installer menyimpan config/CA di LocalAppData/SIMON, memakai state LocalAppData/SIMON/data (kompatibel percobaan manual), membuat shortcut Startup dan menjalankan agent. EXE/XML tetap di folder paket drive D. Otomatis setelah user login, bukan sebelum login. install-service.bat tetap tersedia untuk mode service. Lihat deployment/agent/README.md untuk pembaruan dan pemeriksaan log.

Pembaruan lokasi mode Startup: semua config/CA/launcher/log kini di folder paket drive D, state di SIMONAgent/data. LocalAppData hanya dibaca untuk migrasi identitas lama, tanpa menulis data baru di sana. Tutup agent lama sebelum migrasi dan jalankan install.bat untuk memperbarui shortcut.

## Startup native EXE terbaru

Installer dan Startup kini langsung menjalankan SIMONAgent.exe tanpa PowerShell: install.bat -> --install-user; shortcut -> --background --config. Update ini wajib rebuild EXE (manifest 6/native_user_startup), lalu make-agent-package.bat. Semua data/config/log tetap di D. Tidak perlu membiarkan jendela console terbuka. Validasi lokal lewat shortcut sungguhan telah dilakukan; reboot/login store tetap perlu dicoba.

Pencegahan duplikat terbaru (manifest 7/machine_single_instance): kunci Windows Global berlaku per PC/server lintas folder data dan sesi Windows. Installer mode user menolak jika service SIMON lama masih berjalan atau agent dari konfigurasi folder lain terdeteksi aktif untuk server yang sama. Worker service memakai penanda mode service, sehingga tidak menolak dirinya sendiri. Jangan menjalankan service dan Startup bersamaan; pilih satu mode. Update ini wajib rebuild EXE, lalu buat paket baru.

## Kode store unik

Satu kode store nonkosong hanya untuk satu identitas PC, termasuk perangkat Offline. Spasi tepi dan perbedaan huruf besar/kecil tidak membuat kode baru; nol di depan tetap dipertahankan. Instal ulang dengan UUID/claim sama boleh memakai kode lama. PC berbeda ditolak HTTP 409 dengan nama PC pemilik; tidak menimpa akun/assignment/histori. Hentikan agent lama sebelum melepas/menghapus record untuk penggantian PC. Jangan menghapus identitas lokal saat update.

Update backend lalu restart server untuk mengaktifkan validasi dan migrasi kolom/index database tanpa menghapus data. Agent lama tetap dapat mengirim data untuk kode yang sah. Agar install.bat memeriksa kode sebelum membuat Startup dan menampilkan pesan jelas, build EXE baru (manifest 8/unique_store_code), lalu make-agent-package.bat dan sebar paket baru. Pemeriksaan installer memerlukan koneksi HTTPS/CA yang valid; jika konflik atau pemeriksaan gagal, konfigurasi/Startup belum diperbarui. Duplikat legacy yang sudah ada tidak dihapus otomatis dan tetap perlu ditinjau admin.

## Identitas PC saat folder agent tersalin

Build terbaru wajib manifest 9/machine_bound_identity. UUID/claim disimpan bersama hash MachineGuid Windows (nilai registry asli tidak dikirim). Instal ulang pada Windows yang sama mempertahankan identitas. Bila data berasal dari PC lain, installer membuat identitas terpisah dan mengarantina credential/queue lama ke data-other-machine-* tanpa mengirim antrean PC asal. Untuk state legacy tanpa binding, server memeriksa identitas hardware pada preflight; mismatch ditolak, installer menyimpan backup lokal lalu mencoba UUID baru sekali. Kode store unik tetap berlaku, tidak otomatis mengambil kode PC lain.

Server menolak enrollment/inventory yang memakai UUID lama tetapi Machine ID atau serial BIOS valid berbeda, sehingga hostname/serial/kode perangkat asal tidak tertimpa. Rename hostname pada hardware yang sama tetap diperbolehkan. Perangkat lama yang masih berjalan dengan credential tersalin perlu dihentikan dan diperbarui; reset database saja tidak memperbaiki file identitas tersalin dan agent aktif bisa langsung mendaftar kembali. Sebarkan ZIP bersih hasil server, bukan folder instalasi yang sudah berisi data.

Urutan rollout: hentikan agent lama; update source server dan restart backend; build EXE baru lalu buat paket dari CA server kantor; instal paket baru di tiap PC dengan kode store masing-masing; uji dua perangkat muncul bersamaan sebelum penyebaran luas. Semua config/data/log tetap di drive D.

## SIMON 1.0

Rilis 1.0 mempertahankan frontend HTML/CSS/JavaScript murni dan jadwal telemetry yang sama agar tetap ringan. Agent manifest format 10 (`agent_build_identity`) mengirim versi dan SHA build bersama inventory. Detail perangkat menampilkan kecocokan agent terhadap server tanpa request tambahan, nama TS, serta petunjuk bila model/CPU/serial belum lengkap. Agent lama tetap dapat mengirim data dan ditandai perlu diperbarui atau versi tidak diketahui. Update tidak menghapus database, UUID, kode store, histori, assignment, config maupun XML Sentinel.

## Update web dari dashboard (0.2.0)

Pemasangan awal: pull source terbaru lalu jalankan `deployment/server/setup-updater.bat` sebagai Administrator satu kali pada PC server. Setelah itu Super Admin membuka **UpdateSimon → Cek update → Update sekarang**. Helper terpisah menyiapkan release/environment, backup dan memulihkan versi/database lama bila pemasangan atau health check gagal. Fitur ini tidak memperbarui EXE agent store. Lihat [panduan update web](docs/WEB_UPDATE.md).
