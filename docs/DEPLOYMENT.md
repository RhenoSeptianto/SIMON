# Deploy SIMON ke PC kantor dan PC store

Repo: https://github.com/RhenoSeptianto/SIMON.git
Server: https://172.18.123.92:8443 (LAN/VPN kantor; bukan internet publik).

## 1. PC kantor

Pasang Git for Windows. Setup dapat memasang Python 3.12 x64 secara otomatis lewat `winget`; PC harus terhubung internet dan memiliki App Installer/`winget`. Bila `winget` tidak tersedia, setup menampilkan petunjuk instalasi manual Python dari python.org. Buka terminal:

```powershell
New-Item -ItemType Directory -Force D:\IT | Out-Null
Set-Location D:\IT
git clone https://github.com/RhenoSeptianto/SIMON.git simon
```

Folder proyek menjadi D:\IT\simon. Klik kanan `deployment\server\setup-server.bat` -> Run as administrator. Saat instalasi baru, isi password Super Admin (username admin) dan password awal 9 user TS. Jika ingin sama seperti sekarang, masukkan password yang sebelumnya disepakati; password tidak di-hardcode ke repo publik. Jika database sudah ada, setup tidak mengubah akun/password.

Setup otomatis memasang Python 3.12 x64 untuk semua pengguna lewat `winget` jika Python Launcher atau runtime Python 3.12 belum tersedia, kemudian memasang dependency aplikasi melalui pip. Proses memerlukan hak Administrator, koneksi internet, dan App Installer/`winget`; jika instalasi otomatis tidak tersedia/gagal, pesan error memberi langkah instalasi manual. Setup memvalidasi Python 3.12 x64 sebelum membuat `.venv`, menjalankan `pip check` dan validasi backend HTTPS. Jika `.venv` rusak atau memakai versi Python lain, setup menghentikan server, mengganti namanya menjadi `.venv.backup-<timestamp>`, lalu membuat virtualenv baru; backup tidak dihapus. Database, konfigurasi, sertifikat, credential, dan data operasional tetap berada di `data`. Setup mempertahankan Task Scheduler SIMONServer beserta konfigurasi yang valid; semua lokasi dihitung relatif dari root proyek. Setup membuat sertifikat kantor di `data/tls`, mengaktifkan firewall TCP8443 hanya untuk rentang private, lalu menjalankan HTTPS. Setup mencoba menambahkan CA publik ke Windows Trusted Root; jika kebijakan PC menolak akses, setup menampilkan peringatan dan tetap menjalankan server. Impor `data/tls/ca.crt` melalui `certlm.msc` ke Local Computer > Trusted Root Certification Authorities jika browser PC server harus mempercayai sertifikat. CA hanya untuk SIMON, jaga private key di folder data. Tidak membuat jadwal backup harian. Matikan sleep PC server melalui Settings Windows. PC mati/server mati berarti store mengantre telemetry hingga server kembali aktif.

Dashboard: https://172.18.123.92:8443. Browser PC admin lain perlu mengimpor **public** data/tls/ca.crt ke Trusted Root melalui kebijakan IT; agent memakai file CA sendiri sehingga tidak perlu import sertifikat ke Windows store. Tidak boleh mengubah verify=False. Sertifikat server berlaku 825 hari dan CA 10 tahun; rencanakan pembaruan sebelum habis masa berlaku.

Gunakan status-server.bat/stop-server.bat. Untuk menyalakan kembali task: Task Scheduler -> SIMONServer -> Run, atau `Start-ScheduledTask SIMONServer` sebagai admin. Log server berotasi di data/logs/server.log. Hindari menjalankan start-server.bat manual bersamaan dengan task karena port sama.

Saat setup membuat akun/database, akun Windows yang menjalankan setup diberi akses sementara ke folder data dan lokasi database SQLite yang benar-benar dipakai (`SIAMS_DATA`/`DATABASE_URL`); koneksi SQLite diuji sebelum prompt akun. Sesudah validasi, permission dikembalikan hanya ke SYSTEM dan Administrators. Jika setup bootstrap gagal, permission aman tersebut tetap dipulihkan.

## 2. Akun/data yang sudah ada di PC pengembangan

GitHub berisi source, **bukan database dan credential**. Untuk membawa akun/password/inventory yang sekarang: hentikan backend PC pengembangan, salin folder data lewat media/jalur internal secara terpisah ke D:\IT\simon\data **sebelum setup kantor**. Jangan overwrite data PC kantor yang sudah beroperasi. Jangan salin .venv. Jangan salin folder agent state ke PC store lain. Jika tidak membawa data, setup membuat akun baru melalui prompt.

## 3. Buat paket agent

Opsi A: GitHub -> Actions -> Build SIMON Windows agent -> Run workflow. Download artifact `SIMONAgent-template-Windows-x64`; ekstrak ZIP artifact luarnya sehingga memperoleh file `SIMONAgent-template.zip`. Simpan file itu ke D:\IT\simon\release\SIMONAgent-template.zip (buat folder release bila belum ada).

Opsi B: di PC build Windows x64 jalankan tools/build-agent.bat. Ini membuat virtualenv build terpisah; hasil sama di release/SIMONAgent-template.zip. Python tidak dibutuhkan di PC store.

Pada **PC kantor**, jalankan deployment/server/make-agent-package.bat. Script menambahkan hanya public ca.crt ke template. Hasil: release/SIMONAgent-store.zip. File ini yang dibagikan ke seluruh store. Private ca.key/server.key tidak ikut paket. Jangan membagikan folder data atau seluruh repo sebagai paket agent.

## 4. Pasang di store (satu kali)

Ekstrak SIMONAgent-store.zip. Klik kanan install.bat -> Run as administrator. Service SIMONAgent langsung mulai, lalu otomatis menyala saat Windows boot tanpa login. Ekstrak ke lokasi permanen (contoh D:/SIMONAgent-store). Binary, konfigurasi, XML dan folder data tetap di subfolder SIMONAgent dalam paket. Installer memigrasikan identitas lama dari ProgramData/SIAMS bila state lokal belum ada. Folder tidak boleh dipindahkan setelah service didaftarkan.

Buka status.bat. Perangkat muncul otomatis di SIMON, Super Admin memilih TS langsung pada detail PC. Installer dapat dijalankan kembali untuk update binary/config sambil mempertahankan UUID dan antrean. Uninstaller hanya menghapus service; state/binary tetap tersedia untuk reinstall.

PC store harus Windows 10/11 **x64** dan bisa menjangkau 172.18.123.92 melalui LAN/VPN. Tes `Test-NetConnection 172.18.123.92 -Port 8443`. Tidak membuka port inbound di store. Jika gagal, perbaiki routing/VPN/firewall; IP private tidak dapat diakses lewat internet biasa. Store yang tidak terhubung jaringan kantor belum bisa rollout.

Data disk: mengikuti perubahan XML Sentinel (sekitar 10 detik); CPU/RAM/drive sekitar 10 detik; heartbeat sekitar 10 detik. Log berotasi, queue 2.000 event. Service LocalSystem dipakai untuk boot tanpa login dan akses konfigurasi/state yang dilindungi. Pembacaan SMART hardware dilakukan Sentinel, bukan agent. Binary belum code-signed. Uji pilot 1–2 PC store, reboot, offline/reconnect dan beban CPU/RAM sebelum rollout masal. Installer/service tidak boleh dianggap lulus uji boot hanya karena binary berhasil dibuild.

## 5. Update source kantor

Sebagai Administrator, hentikan task SIMONServer, jalankan git pull di D:\IT\simon, lalu jalankan setup-server.bat. Ini mempertahankan database/sertifikat/akun dan konfigurasi task yang valid; virtualenv lama hanya diganti jika tidak sehat/kompatibel dan selalu dicadangkan terlebih dahulu. Jangan pindah folder setelah task terdaftar. Untuk agent yang sudah terpasang, kirim paket store versi baru dan jalankan install.bat lagi; tidak perlu membuat UUID baru.

## GitHub

Upload source saja. .gitignore mengecualikan .venv, data, release, binaries, config, SQLite, log dan private key. Jangan upload ZIP seluruh folder D:\APPWEB\siams-lite; itu dapat membawa data/credential tersembunyi. Template executable diunduh lewat Actions artifact; paket store berisi CA publik dibuat lokal di kantor.

### SQLite unable to open database file saat setup

Installer terbaru mencetak SIMON SQLite check: path database, jenis file/folder, atribut read-only, hasil membuat database uji di folder yang sama, dan hasil membuka/menulis transaksi yang dibatalkan pada database operasional. File siams.db tidak dihapus atau direset. Untuk database di dalam folder data yang dikelola SIMON, installer dapat melepas atribut read-only file; database eksternal tidak diubah atributnya otomatis. Bila gagal, ACL folder/file ditampilkan agar explicit Deny atau masalah lokasi terlihat. Keberhasilan icacls saja belum membuktikan SQLite dapat menulis.

Tarik update kemudian jalankan setup-server.bat sebagai Administrator. Bila masih gagal, kirim seluruh bagian mulai SIMON SQLite check sampai GAGAL beserta output ACL. Jangan membuat database kosong pengganti atau menghapus folder data sebelum penyebabnya diketahui.

### Perbaikan ACL file database/sertifikat

Akar masalah SQLITE_CANTOPEN dan sertifikat yang tidak dapat dibaca berhasil direproduksi pada Windows: `icacls` mengabaikan grant `(OI)(CI)F` bila targetnya file. Skrip lama menghapus inheritance file lalu memakai grant tersebut sehingga DACL file dapat kosong, walaupun command melaporkan sukses. Skrip terbaru memakai `(OI)(CI)F` hanya pada folder, dan `F` pada file. Sebelum bootstrap, grant sementara `F` dipasang ke file yang sudah terlanjur terkunci supaya rerun dapat memulihkan akses tanpa menghapus data atau sertifikat. Sesudah setup, akses file dilindungi untuk SYSTEM dan Administrators.

Health check memakai modul `tools.server_healthcheck` agar kesalahan membaca CA/koneksi dilaporkan lengkap melalui stdout. Windows PowerShell 5.1 tidak lagi memotong traceback di NativeCommandError akibat redirect stderr. Certificate validation tetap aktif dan kegagalan HTTP/TLS tetap membuat setup gagal. Peringatan import Windows Trusted Root tetap ditampilkan bila dibatasi kebijakan kantor.

Tarik update, lalu jalankan ulang setup-server.bat sebagai Administrator di folder proyek yang sama. Tidak perlu pindah folder atau membuat database kosong lagi. Tes regresi memuat fungsi ACL asli melalui PowerShell AST dan memeriksa ACE file database/CA nyata dalam folder uji; tidak memasang task/firewall operasional.

### Agent gagal Copy-Item ProgramData/SIMON/ca.crt

Installer agent diperbaiki agar memulihkan akses file config/CA/state yang terkunci sebelum copy. Grant file memakai F; grant folder memakai (OI)(CI)F. State/UUID/queue dipertahankan, bukan dihapus. Proteksi akhir SYSTEM/Administrators diterapkan di finally meskipun copy gagal. Jangan menjalankan installer lama dari ZIP lama setelah update.

Setelah git pull pada PC kantor, jalankan make-agent-package.bat sebagai Administrator untuk membuat ulang SIMONAgent-store.zip. Binary EXE tidak perlu dibuild ulang: script packaging sekarang menimpa installer dari source checkout terbaru, meskipun template ZIP lama. Kirim paket baru dan jalankan install.bat sebagai Administrator di store. Pengujian mencakup pemulihan file CA dengan DACL kosong dan verifikasi grant SYSTEM/Administrators pada file. Tidak memasang service pada PC developer saat pengujian.


## Sentinel XML dan kode store (versi terbaru)

1. Update server lebih dahulu: git pull, lalu setup-server.bat. Kolom store_code ditambahkan pada database lama secara idempotent, tanpa menghapus device, akun, atau assignment.
2. Build template EXE baru melalui tools/build-agent.bat atau artifact GitHub Actions terbaru. Binary lama belum mendukung Sentinel/kode store; make-agent-package.bat menolak template tanpa capability manifest dan checksum yang sesuai.
3. Buat ulang paket store dan jalankan install.bat sebagai Administrator. Isi kode store (contoh 00115). Update berikutnya dapat memakai Enter untuk mempertahankan kode lama.
4. Atur Sentinel mengekspor XML setiap 10 detik ke D:\SIMONAgent-store\SIMONAgent\HDSentinel.xml (sesuaikan lokasi paket). Pastikan Sentinel juga berjalan otomatis serta memiliki izin menulis di folder tersebut. Agent tidak menginstal/mengonfigurasi Sentinel atau mengubah frekuensi scan Sentinel. Jika Sentinel belum berjalan setelah boot, status missing/stale muncul dan agent terus memantau sampai XML tersedia.

Agent memantau metadata file sekitar satu detik, membaca perubahan lengkap dan mengirim snapshot disk. Tidak ada lagi jadwal 16.00/pemeriksaan storage lewat PowerShell. CPU/RAM/drive tetap sekitar 10 detik, heartbeat sekitar 10 detik. Dashboard detail mengambil nilai disk terbaru setiap 10 detik tanpa mereset tab atau dropdown assignment.

Disk diidentifikasi berdasarkan serial (fallback model+lokasi hanya jika tersedia). Health/performance tidak ditafsirkan sebagai wear. Ringkasan hanya mengambil field disk/report yang diperlukan; informasi registrasi Sentinel tidak dikirim. XML missing/partial/stale lebih dari 2 menit ditandai, data valid terakhir dipertahankan. Ekspor XML tiap 10 detik bukan jaminan hardware Sentinel benar-benar melakukan scan tiap 10 detik; waktu/status pemantauan dari laporan tetap ditampilkan.

Tidak menyimpan histori snapshot disk. Antrean storage offline digabung menjadi snapshot terakhir. Histori CPU/RAM tetap, serta riwayat alert deduplicated untuk suhu >65 C, health di bawah batas (default 80%), health turun, dan perubahan identitas disk. Perubahan sementara selama offline mungkin tidak masuk riwayat karena snapshot offline digabung. Kode store hanya metadata tampilan/filter/ekspor; akses TS tetap berdasarkan assignment PC langsung.


## Hapus perangkat dan otomatis kembali

Versi terbaru menyederhanakan pengelolaan perangkat menjadi Hapus saja; tombol/API Revoke tidak digunakan. Penghapusan menghapus histori/alert/assignment, tetapi agent yang masih berjalan dapat mendaftar kembali memakai UUID/kode store yang sama pada pengiriman berikutnya. Credential lama tidak berlaku setelah delete; EXE baru menangani 401 dengan enrollment ulang, mempertahankan identity dan queue serta memaksa pembaruan metrics/Sentinel. Assignment TS yang dihapus tidak dikembalikan otomatis. Untuk PC yang tidak ingin muncul kembali, hentikan/uninstall service secara lokal.

Update server lalu gunakan template EXE terbaru (manifest format 3, capability reenrollment_after_delete), buat ulang paket dan install ulang di store. Installer mempertahankan UUID/config/kode store. Paket menolak executable lama yang belum mendukung pemulihan credential. Perubahan UI suhu: simbol derajat ditulis dengan entity HTML untuk menghindari '?C' akibat encoding; sensor kosong tetap N/A.


## Update bahasa dan laporan Excel (server saja)

Tarik source terbaru lalu jalankan setup-server.bat sebagai Administrator untuk memulai ulang backend. Browser Ctrl+F5. Agent tidak perlu diubah/dibuild ulang untuk fitur ini. UI Storage menerjemahkan pesan Sentinel di server, menyimpan teks sumber asli. Jika pesan belum dikenali, tampil pemberitahuan bahasa Indonesia untuk memeriksa Sentinel; tidak menyimpulkan disk sehat.

Menu Laporan mengekspor XLSX saja dengan tiga sheet Perangkat, SSD-HDD, Kapasitas Drive. CSV dinonaktifkan. Semua sheet dibatasi oleh akses PC user, termasuk disk/volume. Kode store string menjaga nol di depan; sel numerik/tanggal memiliki tipe yang benar, filter dan freeze header tersedia, teks asing tidak dijalankan sebagai formula. File menggunakan tanggal WIB.


## Interval angka terbaru 10 detik

Default interval CPU/RAM/drive dan heartbeat pada agent terbaru adalah 10 detik. Perlu EXE baru (manifest format 5, capability ten_second_metrics dan in_place_install). Update backend dengan setup-server.bat, build template baru, buat paket store lalu install ulang. Metadata interval disertakan dalam inventory agar server memakai toleransi offline sekitar 45 detik untuk agent baru; agent lama tetap memakai toleransi lamanya sampai diupdate. Override OFFLINE_SECONDS tetap didukung.

Histori CPU/RAM dipadatkan per 5 menit (HISTORY_INTERVAL_SECONDS default 300) agar database tetap ringan; kondisi terbaru untuk dashboard/laporan tetap setiap 10 detik. Detail PC memperbarui CPU/RAM, sisa drive, koneksi, dan Sentinel otomatis tanpa menutup dialog atau mereset assignment.

### Log instalasi dan pemeriksaan agent

install.log mencatat tahap instalasi dan error; check-agent.bat/status.bat menghasilkan check-agent.log dengan pemeriksaan file, service/path/exit code, akses tulis, EXE/HTTPS terverifikasi CA, log agent dan startup worker, serta event Windows terkait. Tidak mengubah kebijakan antivirus. Sangfor mungkin menyimpan blokir hanya di konsol pengelola. Bila PowerShell tidak boleh dijalankan, launcher BAT mencatat kode keluar sebisa mungkin.

### Default terbaru: mode Startup user

Install.bat kini memasang Startup akun Windows tanpa administrator. Isi kode store, EXE/XML tetap di folder paket dan config/data/log di LocalAppData/SIMON. install-service.bat adalah pilihan service lama yang perlu admin. Untuk store 417, tutup agent manual dengan Ctrl+C sebelum install.bat, pertahankan LocalAppData/SIMON/data. Update script saja cukup git pull dan make-agent-package.bat; tidak perlu rebuild EXE. Uji reboot/login untuk memastikan Startup diizinkan kebijakan PC.

Pembaruan lokasi mode Startup: semua config/CA/launcher/log kini di folder paket drive D, state di SIMONAgent/data. LocalAppData hanya dibaca untuk migrasi identitas lama, tanpa menulis data baru di sana. Tutup agent lama sebelum migrasi dan jalankan install.bat untuk memperbarui shortcut.

## Startup native EXE terbaru

Installer dan Startup kini langsung menjalankan SIMONAgent.exe tanpa PowerShell: install.bat -> --install-user; shortcut -> --background --config. Update ini wajib rebuild EXE (manifest 6/native_user_startup), lalu make-agent-package.bat. Semua data/config/log tetap di D. Tidak perlu membiarkan jendela console terbuka. Validasi lokal lewat shortcut sungguhan telah dilakukan; reboot/login store tetap perlu dicoba.

Pencegahan duplikat terbaru (manifest 7/machine_single_instance): kunci Windows Global berlaku per PC/server lintas folder data dan sesi Windows. Installer mode user menolak jika service SIMON lama masih berjalan atau agent dari konfigurasi folder lain terdeteksi aktif untuk server yang sama. Worker service memakai penanda mode service, sehingga tidak menolak dirinya sendiri. Jangan menjalankan service dan Startup bersamaan; pilih satu mode. Update ini wajib rebuild EXE, lalu buat paket baru.
