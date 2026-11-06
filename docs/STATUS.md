# Status terbaru

Role yang didukung hanya super_admin dan ts. Role lain di database dikonversi menjadi ts saat startup, akses PC lama dipertahankan. Super Admin melihat semua PC tanpa assignment; TS perlu assignment langsung. Hanya Super Admin dapat mengelola user, backup dan reset database.

Password minimal satu karakter. Sembilan akun TS yang diminta pengguna sudah dibuat di database lokal. Tidak ada seed password otomatis pada startup.

Menu Database menyediakan download backup SQLite konsisten menggunakan SQLite online backup API. Reset data monitoring memerlukan konfirmasi RESET dan backup otomatis sebelum transaksi penghapusan. Akun/password dan audit dipertahankan. Reset hanya diimplementasikan dan diuji pada database tes, tidak dieksekusi terhadap database pengguna.

Lima tes integrasi lulus: authentication/CSRF, izin PC, enrollment/telemetry, penghapusan PC, sesi Super Admin, password pendek, role TS, backup yang dapat dibuka SQLite dan reset dengan preservasi akun. Browser otomatis, installer/service Windows, packaging executable serta PostgreSQL belum diuji. Sensor disk yang tak tersedia bernilai null. Alert CPU/RAM sustained dan konfigurasi threshold UI belum tersedia.

Detail alur operasional tersedia pada README. Frontend dilayani langsung FastAPI, database default SQLite, agent Python outbound-only. Tidak memerlukan Node atau Docker.

Fitur ganti password sendiri tersedia melalui POST /api/me/password dan tombol topbar. Memerlukan autentikasi, header CSRF dan verifikasi password lama, menerima password baru minimal 1 karakter. Seluruh sesi user dicabut setelah berhasil. Tujuh tes lulus termasuk TS/Super Admin, password lama salah, password kosong, CSRF, pencabutan seluruh sesi dan login menggunakan password baru.

Assignment user langsung pada dialog detail PC tersedia untuk Super Admin, dengan checkbox TS dan tombol simpan. Mendukung banyak user serta pencabutan akses, tanpa mengubah akses PC lain atau mengakhiri sesi. Delapan tes pytest lulus termasuk authorization endpoint assignment, validasi role, duplicate ID, grant/revoke akses dan preservasi assignment PC lain. Browser belum diuji otomatis.

## Detail PC interaktif

Modal responsif dengan empat tab, CPU/RAM dalam persen, keterangan kecil, drive free GiB/persen, indikator warna storage dan kartu setiap physical disk. Grafik SVG memiliki skala persen/waktu, tooltip sampel lewat pointer/sentuhan, slider keyboard dan filter 1/24/168 jam. API histori memvalidasi rentang 1–168 jam dan mengembalikan sampel secara kronologis. Refresh tetap di tab aktif. Tanggal sampel dan last seen terpisah; tidak mengklaim refresh memicu koleksi agent.

Validasi terbaru: 9 tes pytest lulus. Tes browser Microsoft Edge headless lulus pada desktop dan mobile, termasuk tab, persentase, slider/tooltip, filter periode dengan empty state, refresh, assignment dan penyembunyian tab Akses User bagi TS. Tidak ditemukan JavaScript error. Screenshot inspeksi lokal tersedia di data/qa. Database tes sementara tidak digunakan oleh aplikasi operasional.

## Jadwal SSD terbaru

Pemeriksaan suhu dan kondisi SSD dilakukan saat agent mulai dan setiap pukul 16.00 WIB (UTC+7 eksplisit). Tidak lagi setiap 30 menit; SIAMS_INTERVAL_STORAGE lama diabaikan. Pemeriksaan CPU/RAM/drive tetap default 300 detik dengan jitter, heartbeat 120 detik. Dashboard menampilkan jadwal baru. Restart agent yang sudah berjalan untuk menerapkannya.

17 tes pytest lulus, termasuk batas sebelum/tepat/setelah 16.00 WIB, startup, resume setelah melewati jadwal, konversi UTC, serta pengujian loop agent dengan kolektor/transport palsu yang membuktikan SSD hanya dipanggil saat startup/16.00 sementara metrics tetap setiap 5 menit. Jam nyata pukul 16.00 belum ditunggu langsung; diuji dengan clock simulasi. Jika koleksi gagal, jadwal dimajukan agar PowerShell tidak dipanggil terus-menerus; error dicatat di log.

## Pembaruan UI/UX dashboard

Sidebar berikon SVG lokal, topbar akun/role, latar memenuhi viewport untuk light/dark mode, kartu KPI, tabel dengan indikator CPU/RAM, badge status, empty state sesuai halaman, kartu download laporan dan penanda reset database. Navigasi responsif dapat digeser di ponsel dan mengikuti halaman aktif. Kontrol memiliki focus keyboard dan label aksesibilitas; tombol pagination dinonaktifkan bila tidak ada halaman berikutnya/sebelumnya. Overview memperbarui konten tanpa menggambar ulang topbar dan mempertahankan ekspansi jadwal saat refresh otomatis.

Semua ikon/gaya disajikan lokal, tanpa font/CDN/dependensi frontend tambahan. Browser check mencakup seluruh 7 halaman pada light/dark mode serta desktop/mobile tanpa overflow horizontal halaman, latar penuh viewport, empty state Alerts yang sesuai konteks, pencarian kosong, acknowledge alert, penyimpanan pilihan tema, dan regresi detail PC/assignment. Pemeriksaan menggunakan database sementara, tidak mengubah data operasional.


Nama aplikasi diperbarui menjadi SIMON - Sistem Monitoring pada seluruh branding pengguna, API title dan file ekspor/backup baru. Identitas teknis lama dipertahankan untuk kompatibilitas data, credential dan deployment.

## Distribusi agent dan server kantor

Agent standalone Windows x64 dibuild dengan PyInstaller onedir, entrypoint Windows SCM terpisah dan worker subprocess. Installer menyediakan service auto-start/recovery, config HTTPS, ACL ProgramData dan preservation UUID/queue. Binary ditempatkan di Program Files. Server menggunakan Task Scheduler SYSTEM, auto-start/restart, HTTPS langsung Uvicorn, log berotasi dan firewall private networks port8443. Tidak ada backup harian otomatis.

Sertifikat root/server dibuat di PC kantor, private key tetap dalam data/tls; paket store hanya mendapat ca.crt publik dan memverifikasi server melalui SSLContext, tanpa verify=False. IP default 172.18.123.92. GitHub Actions dan build-agent.bat menghasilkan template; make-agent-package.bat menambahkan CA kantor. Source archive memakai daftar direktori/ekstensi yang diizinkan dan tidak menyertakan data/.venv/config/credential/private key.

25 tes pytest lulus, termasuk config/path/HTTPS restriction, sertifikat SAN IP, idempotent generation, public-CA-only packaging dan zip traversal rejection. PowerShell installer/setup lulus parsing. Test executable HTTPS dan lifecycle Windows Service dilaporkan terpisah setelah validasi; instalasi service/Task Scheduler/reboot pada kantor/store tetap perlu pilot, bukan otomatis dianggap lulus karena build berhasil.


Validasi distribusi final: 26 tes pytest lulus. Executable release/SIMONAgent/SIMONAgent/SIMONAgent.exe diuji dua kali terhadap server HTTPS sementara dengan CA tervalidasi, berhasil mendaftar/mengirim hardware Windows aktual dan mempertahankan satu UUID. ZIP template sekitar 14 MB, tanpa sertifikat privat. Service SCM, startup/recovery/reboot dan Task Scheduler instalasi kantor belum dijalankan pada PC ini; perlu pilot kantor/store. Source ZIP diverifikasi berisi workflow GitHub dan source saja, tanpa data, .venv, credential atau private key. Source disiapkan untuk repo RhenoSeptianto/SIMON; belum dipush dari sesi ini.

Perbaikan installer terbaru: bug ACL Windows terkonfirmasi/reproduced, grant inheritance direktori `(OI)(CI)F` tidak berlaku pada file. Protect-OperationalData sekarang memakai grant `F` untuk file, grant inheritance hanya untuk folder. Rerun memulihkan grant file lama sebelum bootstrap. Health check modul Python melaporkan pesan lengkap ke stdout, mempertahankan verifikasi CA dan tidak melewati kegagalan TLS/HTTP. 33 tes lulus termasuk pengujian DACL Windows menggunakan fungsi installer asli. Health check HTTPS lokal tervalidasi menghasilkan HTTP 200. Instalasi end-to-end Task Scheduler pada PC kantor tetap perlu dijalankan pengguna.

Installer agent juga diperbaiki untuk kasus CA/config/state lama terkunci: grant akses setup ke file sebelum copy, lalu proteksi per jenis target file/folder. Identitas/queue dipertahankan. Pembuatan paket store mengambil installer terbaru dari source tanpa rebuild EXE. Test scheduler/smoke menggunakan config sementara eksplisit agar tidak membaca config ProgramData dari instalasi PC pengujian. Installer lokal D:/Desktop/SIMONAgent-store/install.ps1 diperbarui setelah diverifikasi cocok dengan versi lama; sertifikat dan executable tidak diganti. 35 tes pytest lulus termasuk pemulihan ACL CA file dan pembaruan installer dalam paket lama.


## Sentinel XML dan kode store - implementasi terbaru

Agent disk memakai HDSentinel.xml di Program Files/SIMON, membaca perubahan metadata file dan mengirim ringkasan saat XML berubah. Tidak lagi menjalankan PowerShell storage atau jadwal 16.00. Encoding XML dihormati; parser membatasi ukuran, menolak DTD/entity, memeriksa penulisan stabil dan mempertahankan data terakhir pada partial/missing/stale/error. Identitas berdasarkan serial, dengan fallback model+lokasi yang jelas; tidak bergantung urutan disk. Informasi registrasi Sentinel tidak dikirim.

Snapshot storage hanya mengubah kondisi terbaru di device, tanpa Sample/history baru. Offline storage digabung menjadi satu snapshot terbaru. CPU/RAM/volume history tetap 5 menit. Alert menyimpan penurunan health, health di bawah batas, suhu tinggi dan perubahan identitas disk, deduplicated. Retensi telemetry diperiksa paling sering sekali per jam untuk mengurangi pekerjaan pada update disk tiap 10 detik.

Installer meminta kode store dan mempertahankan nilai lama saat update. Kode adalah string (leading zero dipertahankan), tampil/cari di daftar dan detail PC serta CSV/XLSX. Kolom database ditambahkan secara idempotent tanpa menghapus device. Akses TS tetap assignment PC langsung, tidak otomatis berdasarkan kode store.

Validasi: 36 tes pytest lulus, termasuk parser, partial/recovery/stale, encoding, serial/order, latest-only storage, alert dedup/recovery/component change, antrean offline, migrasi database lama, pencarian/ekspor kode store dan permission PC. Tes browser desktop/mobile lulus termasuk live update Health 95->94 tanpa menutup dialog, serta dropdown assignment. EXE baru dibuild dengan capability manifest + checksum; paket menolak template jadwal lama. EXE diuji dengan XML fixture melalui HTTPS server/DB sementara. XML contoh lokal asli juga berhasil dibaca terpisah untuk dua disk; file asli tidak masuk GitHub. Service install/reboot/Sentinel auto-export di PC store masih perlu pilot.
