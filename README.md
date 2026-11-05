# SIMON - Sistem Monitoring

Monitoring hardware PC store dengan agent Windows ringan. Super Admin melihat semua PC dan mengelola assignment; TS hanya melihat PC yang diberikan. Dashboard dan API FastAPI memakai SQLite lokal. Tidak membutuhkan Node, Docker, atau layanan cloud berbayar.

## Server PC kantor

IP: **172.18.123.92**. Repo: https://github.com/RhenoSeptianto/SIMON.git

```powershell
New-Item -ItemType Directory -Force D:\IT | Out-Null
Set-Location D:\IT
git clone https://github.com/RhenoSeptianto/SIMON.git simon
```

1. Pasang Python **3.12 x64** dan Git for Windows.
2. Jika ingin membawa akun/data saat ini, salin folder `data` secara privat ke `D:\IT\simon\data` sebelum setup. Folder ini tidak masuk GitHub. Hentikan backend sumber saat menyalin database. Jangan salin `.venv`.
3. Klik kanan `deployment\server\setup-server.bat` -> **Run as administrator**.
4. Buka **https://172.18.123.92:8443**. Pada instalasi baru, setup meminta password admin (username `admin`) dan password awal 9 akun TS. Database yang sudah ada tidak diubah passwordnya.

Setup memakai Python 3.12 x64, memeriksa dependency dan kesehatan backend, serta mencadangkan `.venv` yang tidak valid sebelum membuat ulang. Semua path operasional dihitung relatif dari root proyek `D:\IT\simon`; database, konfigurasi, sertifikat, dan credential tidak dihapus. Server otomatis hidup saat boot melalui Task Scheduler, tanpa perlu login atau terminal terbuka. Matikan sleep PC kantor. Tidak ada jadwal backup harian otomatis. Log: `data\logs\server.log`. Backup manual tersedia di menu Database (Super Admin).

**Panduan lengkap:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Paket agent store

1. Download build GitHub Actions `SIMONAgent-template.zip`, atau build di Windows lewat `tools\build-agent.bat`.
2. Simpan template di `D:\IT\simon\release\SIMONAgent-template.zip` pada PC kantor.
3. Jalankan `deployment\server\make-agent-package.bat`. Hasil: **release\SIMONAgent-store.zip**, berisi binary dan sertifikat **publik** server kantor.
4. Bagikan ZIP store, ekstrak, klik kanan **install.bat -> Run as administrator** sekali pada setiap PC store.

Agent berupa `.exe` dengan Windows Service `SIMONAgent`, otomatis aktif saat Windows dinyalakan, tanpa login dan tanpa Python di store. Binary di `Program Files\SIMON\Agent`; config di `ProgramData\SIMON`; state/UUID/credential/queue/log di `ProgramData\SIAMS` agar kompatibel dengan agent lama. Jangan salin state antarkomputer. Installer update mempertahankan UUID. `status.bat`, `start.bat`, `stop.bat`, `diagnose.bat`, `uninstall.bat` tersedia dalam paket.

PC store harus Windows 10/11 **x64** dan bisa menjangkau `172.18.123.92:8443` melalui LAN/VPN. IP private tersebut tidak bisa diakses melalui internet biasa tanpa routing/VPN. Koneksi agent outbound HTTPS; tidak membuka port inbound pada PC store. Verifikasi sertifikat selalu aktif. Sertifikat/private key kantor dibuat saat setup, tidak disimpan di GitHub. Hanya `ca.crt` publik yang masuk paket store.

## Jadwal dan data

- Status koneksi: sekitar **2 menit**.
- CPU/RAM/sisa drive: sekitar **5 menit**.
- Suhu/health SSD: **saat agent mulai dan pukul 16.00 WIB**.
- Inventory statis: saat mulai dan setiap 24 jam.

Interval heartbeat/metrics/inventory memakai jitter 10%, dapat dikonfigurasi lewat `SIAMS_INTERVAL_HEARTBEAT`, `SIAMS_INTERVAL_METRICS`, `SIAMS_INTERVAL_INVENTORY` (detik). Jadwal SSD menggunakan WIB eksplisit dan mengabaikan `SIAMS_INTERVAL_STORAGE` lama. Sensor tidak tersedia = N/A. Wear nol bukan berarti sisa umur 100%. Refresh dashboard mengambil kiriman terakhir, tidak menjalankan koleksi paksa.

Antrean offline dibatasi 2.000 event (event tertua dibuang saat penuh), timeout HTTP 15 detik, collector PowerShell 35 detik. Retry backoff maksimal 300 detik. Log agent berotasi 1 MiB, 4 file. Histori telemetry disimpan default 30 hari, dibersihkan saat ingestion. UUID stabil meskipun IP/hostname berubah.

## Dashboard

Overview, Devices dengan pencarian/status/pagination, detail PC bertab, grafik CPU/RAM interaktif, assignment TS melalui dropdown, Users, Alerts storage, CSV/XLSX Reports, Audit, dan Database backup/reset. Reset memerlukan konfirmasi RESET, membuat backup terlebih dahulu, menghapus data monitoring tetapi mempertahankan akun/password dan audit. Semua user bisa mengganti password sendiri, minimal satu karakter. Perubahan password mengakhiri seluruh sesi akun.

Hapus PC menghapus histori, alert dan assignment serta memblokir UUID lama agar agent tidak muncul kembali otomatis. Revoke mencabut credential tetapi mempertahankan data. Menghapus dan revoke tidak menghentikan service Windows dari jarak jauh.

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

HTTP hanya diizinkan untuk loopback development. Agent juga mendukung `--config`, `--ca-file`, `--state`, `--once`, dan `--diagnose`. OpenAPI: `/docs`. Config/environment teknis tetap memakai beberapa nama SIAMS untuk kompatibilitas instalasi/data lama, termasuk SQLite `data/siams.db` dan cookie sesi. Environment server: `SIAMS_DATA`, `DATABASE_URL`, `OFFLINE_SECONDS` (420), `RETENTION_DAYS` (30), `SIAMS_PRODUCTION` (otomatis 1 pada runner kantor).

## Tes dan build

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests\browser_details.py
```

Browser test opsional memakai Microsoft Edge dan database sementara. Build agent memerlukan Windows x64: jalankan `tools/build-agent.bat`; hasil template tidak berisi sertifikat/credential kantor. Smoke test executable (sesudah build) menggunakan `python tests/frozen_smoke.py`, memerlukan cryptography dan backend dependencies serta memakai database/HTTPS sementara.

`python -m tools.package_source` membuat `release/SIMON-source.zip` dengan source terpilih untuk upload GitHub. Jangan upload seluruh folder proyek sebagai ZIP: `.venv`, `data`, `release`, database, private key dan credential harus tetap lokal. CI otomatis membuild template agent melalui GitHub Actions setelah source diupload. Panduan restore dan update ada pada docs/DEPLOYMENT.md.

Binary berhasil dibuild dan diuji mengirim hardware aktual melalui HTTPS, namun service startup/recovery/reboot, koneksi VPN, dan dampak CPU/RAM pada PC store tetap perlu pilot sebelum rollout. Binary belum code-signed. [Status implementasi](docs/STATUS.md) mencatat batas fitur produksi yang belum selesai.
