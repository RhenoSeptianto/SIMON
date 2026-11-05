# Deploy SIMON ke PC kantor dan PC store

Repo: https://github.com/RhenoSeptianto/SIMON.git
Server: https://172.18.123.92:8443 (LAN/VPN kantor; bukan internet publik).

## 1. PC kantor

Pasang Git for Windows dan Python 3.12 x64 (python.org). Buka terminal:

```powershell
New-Item -ItemType Directory -Force D:\IT | Out-Null
Set-Location D:\IT
git clone https://github.com/RhenoSeptianto/SIMON.git simon
```

Folder proyek menjadi D:\IT\simon. Klik kanan `deployment\server\setup-server.bat` -> Run as administrator. Saat instalasi baru, isi password Super Admin (username admin) dan password awal 9 user TS. Jika ingin sama seperti sekarang, masukkan password yang sebelumnya disepakati; password tidak di-hardcode ke repo publik. Jika database sudah ada, setup tidak mengubah akun/password.

Setup memvalidasi Python 3.12 x64 sebelum membuat `.venv`, memasang dependency server, menjalankan `pip check` dan validasi backend HTTPS. Jika `.venv` rusak atau memakai versi Python lain, setup menghentikan server, mengganti namanya menjadi `.venv.backup-<timestamp>`, lalu membuat virtualenv baru; backup tidak dihapus. Database, konfigurasi, sertifikat, credential, dan data operasional tetap berada di `data`. Setup mempertahankan Task Scheduler SIMONServer beserta konfigurasi yang valid; semua lokasi dihitung relatif dari root proyek. Setup membuat sertifikat kantor di `data/tls`, mengaktifkan firewall TCP8443 hanya untuk rentang private, lalu menjalankan HTTPS. Root CA kantor ditambahkan ke trust Windows pada PC server agar browser kantor mengenali HTTPS. CA hanya untuk SIMON, jaga private key di folder data. Tidak membuat jadwal backup harian. Matikan sleep PC server melalui Settings Windows. PC mati/server mati berarti store mengantre telemetry hingga server kembali aktif.

Dashboard: https://172.18.123.92:8443. Browser PC admin lain perlu mengimpor **public** data/tls/ca.crt ke Trusted Root melalui kebijakan IT; agent memakai file CA sendiri sehingga tidak perlu import sertifikat ke Windows store. Tidak boleh mengubah verify=False. Sertifikat server berlaku 825 hari dan CA 10 tahun; rencanakan pembaruan sebelum habis masa berlaku.

Gunakan status-server.bat/stop-server.bat. Untuk menyalakan kembali task: Task Scheduler -> SIMONServer -> Run, atau `Start-ScheduledTask SIMONServer` sebagai admin. Log server berotasi di data/logs/server.log. Hindari menjalankan start-server.bat manual bersamaan dengan task karena port sama.

## 2. Akun/data yang sudah ada di PC pengembangan

GitHub berisi source, **bukan database dan credential**. Untuk membawa akun/password/inventory yang sekarang: hentikan backend PC pengembangan, salin folder data lewat media/jalur internal secara terpisah ke D:\IT\simon\data **sebelum setup kantor**. Jangan overwrite data PC kantor yang sudah beroperasi. Jangan salin .venv. Jangan salin folder agent state ke PC store lain. Jika tidak membawa data, setup membuat akun baru melalui prompt.

## 3. Buat paket agent

Opsi A: GitHub -> Actions -> Build SIMON Windows agent -> Run workflow. Download artifact `SIMONAgent-template-Windows-x64`; ekstrak ZIP artifact luarnya sehingga memperoleh file `SIMONAgent-template.zip`. Simpan file itu ke D:\IT\simon\release\SIMONAgent-template.zip (buat folder release bila belum ada).

Opsi B: di PC build Windows x64 jalankan tools/build-agent.bat. Ini membuat virtualenv build terpisah; hasil sama di release/SIMONAgent-template.zip. Python tidak dibutuhkan di PC store.

Pada **PC kantor**, jalankan deployment/server/make-agent-package.bat. Script menambahkan hanya public ca.crt ke template. Hasil: release/SIMONAgent-store.zip. File ini yang dibagikan ke seluruh store. Private ca.key/server.key tidak ikut paket. Jangan membagikan folder data atau seluruh repo sebagai paket agent.

## 4. Pasang di store (satu kali)

Ekstrak SIMONAgent-store.zip. Klik kanan install.bat -> Run as administrator. Service SIMONAgent langsung mulai, lalu otomatis menyala saat Windows boot tanpa login. Installer menyimpan binary di Program Files/SIMON/Agent, konfigurasi di ProgramData/SIMON, identitas/queue/log di ProgramData/SIAMS. Nama folder SIAMS dipertahankan supaya identitas agent lama tidak berubah.

Buka status.bat. Perangkat muncul otomatis di SIMON, Super Admin memilih TS langsung pada detail PC. Installer dapat dijalankan kembali untuk update binary/config sambil mempertahankan UUID dan antrean. Uninstaller hanya menghapus service; state/binary tetap tersedia untuk reinstall.

PC store harus Windows 10/11 **x64** dan bisa menjangkau 172.18.123.92 melalui LAN/VPN. Tes `Test-NetConnection 172.18.123.92 -Port 8443`. Tidak membuka port inbound di store. Jika gagal, perbaiki routing/VPN/firewall; IP private tidak dapat diakses lewat internet biasa. Store yang tidak terhubung jaringan kantor belum bisa rollout.

Jadwal: SSD saat agent mulai dan 16.00 WIB; CPU/RAM/drive sekitar 5 menit; heartbeat sekitar 2 menit. Log berotasi, queue 2.000 event. Service LocalSystem diperlukan untuk pembacaan reliability counter. Binary belum code-signed. Uji pilot 1–2 PC store, reboot, offline/reconnect dan beban CPU/RAM sebelum rollout masal. Installer/service tidak boleh dianggap lulus uji boot hanya karena binary berhasil dibuild.

## 5. Update source kantor

Sebagai Administrator, hentikan task SIMONServer, jalankan git pull di D:\IT\simon, lalu jalankan setup-server.bat. Ini mempertahankan database/sertifikat/akun dan konfigurasi task yang valid; virtualenv lama hanya diganti jika tidak sehat/kompatibel dan selalu dicadangkan terlebih dahulu. Jangan pindah folder setelah task terdaftar. Untuk agent yang sudah terpasang, kirim paket store versi baru dan jalankan install.bat lagi; tidak perlu membuat UUID baru.

## GitHub

Upload source saja. .gitignore mengecualikan .venv, data, release, binaries, config, SQLite, log dan private key. Jangan upload ZIP seluruh folder D:\APPWEB\siams-lite; itu dapat membawa data/credential tersembunyi. Template executable diunduh lewat Actions artifact; paket store berisi CA publik dibuat lokal di kantor.
