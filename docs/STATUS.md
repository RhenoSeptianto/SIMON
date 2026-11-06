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


## Pengelolaan perangkat dan tampilan suhu terbaru

Tombol serta API Revoke dihapus. Hapus perangkat membersihkan record/histori/alert/assignment tanpa memblokir UUID. Agent yang menerima 401 membuang credential saja, mempertahankan UUID/claim/store code dan queue, lalu mendaftar ulang otomatis pada siklus berikutnya tanpa restart. Snapshot Sentinel dan metrics dikirim ulang. Penanda deleted lama tidak lagi menghalangi enrollment. Identitas disimpan atomik menggunakan replace file sementara. Assignment TS yang dihapus tidak otomatis kembali.

Tampilan suhu menggunakan &deg;C agar tidak berubah menjadi ?C karena encoding. Nilai kosong N/A; suhu di atas threshold diberi warna berbeda. UI menampilkan satu tindakan Hapus dengan penjelasan/konfirmasi bahwa agent aktif bisa muncul kembali. Template executable ditandai manifest format 3 dengan capability reenrollment_after_delete untuk menolak paket lama yang belum mendukung pemulihan credential.

Validasi unit/integrasi: 38 tes lulus, termasuk 401 recovery tanpa mengganti UUID, delete/re-enroll, penanda deleted lama, penghapusan assignment, serta regresi seluruh alur lain. Tes browser memastikan simbol derajat tampil benar dan tidak ada tombol Revoke. Uji EXE hidup melalui HTTPS dilakukan terpisah menggunakan server/database sementara; tidak memasang service pada sistem operasional.

Uji EXE final lulus: satu proses agent tetap hidup, PC dihapus lewat API dashboard, XML berubah, agent menerima 401 lalu kembali terdaftar dengan UUID/kode store yang sama dan mengirim metrics/Sentinel baru. Server tes menggunakan HTTPS dengan CA tervalidasi; database tes memastikan hanya histori CPU baru yang tersisa.


## Lokalisasi Sentinel dan Excel saja

Terjemahan offline/server untuk pesan umum Sentinel, status pemantauan dengan tanggal/jam Indonesia, perkiraan umur dan saran. Deskripsi masalah mempertahankan jumlah/severity yang dikenali. Pesan yang tidak dikenali menggunakan pemberitahuan untuk memeriksa Sentinel; teks sumber tidak ditimpa. Dua disk pada XML contoh lokal berhasil diterjemahkan penuh. Label Kesehatan/Performa/catatan diperbarui pada Storage.

Menu Laporan dan ekspor XLSX tunggal dengan tiga sheet terstruktur: Perangkat, SSD-HDD, Kapasitas Drive. Seluruh sheet dibatasi visible devices, satu disk/volume per baris, nilai GiB/persen bertipe angka, timestamp Excel WIB, kode store teks, filter/freeze header/style/wrapping, mitigasi formula dan control character. Endpoint CSV mengembalikan 404. Filename SIMON-Inventaris-YYYY-MM-DD.xlsx. Agent tidak berubah/tidak perlu rebuild.

Validasi: 41 pytest lulus termasuk terjemahan sehat/bermasalah/jumlah error/unknown, report 3 sheet, pemisahan disk/drive, nilai/satuan/tanggal, leading zeros, formula safety, akses user dan workbook kosong. Browser desktop/mobile/light/dark lulus, mengunduh file Excel aktual dan memeriksa sheet, memastikan CSV tidak tampil, serta memeriksa teks Indonesia pada detail Sentinel dan pembaruan live. Tidak ada JavaScript error. Koneksi/boot service agent tidak diuji ulang karena tidak diubah.

## Pembaruan langsung sekitar 10 detik

Default heartbeat dan CPU/RAM/kapasitas drive agent menjadi 10 detik (jitter kecil untuk menghindari kiriman serentak). Sentinel tetap mengikuti perubahan XML. Dashboard dan detail PC memperbarui nilai terbaru setiap 10 detik. Histori CPU/RAM dibatasi satu sampel per 5 menit agar database tidak cepat membesar; nilai terkini tetap diterima setiap pengiriman.

Agent mengiklankan interval heartbeat dalam inventory. Server menggunakan ambang offline minimal 45 detik untuk agent baru, mempertahankan 420 detik bagi agent lama tanpa metadata; OFFLINE_SECONDS tetap dapat menggantikan nilai tersebut. Manifest EXE format 4 menambahkan capability ten_second_metrics, sehingga paket store menolak EXE lama. Perubahan ini memerlukan pembaruan server dan EXE agent; identitas serta kode store tetap dipertahankan saat update instalasi.

Validasi: 43 pytest lulus, browser desktop/mobile/light/dark lulus termasuk pembaruan CPU otomatis tanpa menutup dialog. EXE final melalui HTTPS tervalidasi berhasil enroll/report, mempertahankan UUID/kode store saat restart, dan otomatis mendaftar kembali setelah dihapus dari dashboard. Histori yang masuk dalam rentang 5 menit tidak digandakan. Instalasi service/reboot pada PC store tetap dilakukan pengguna.

## Agent berjalan langsung dari folder paket

Installer memakai folder SIMONAgent di dalam paket sebagai lokasi permanen EXE/config/CA/XML/data. Tidak menyalin binary ke Program Files atau membuat state baru di ProgramData. Instalasi lama dengan path service standar dimigrasikan: hentikan service, salin identitas/antrean bila state lokal belum punya UUID, pertahankan kode store, perbarui path service. Folder lama tidak dihapus. Pemasangan ulang pada lokasi sama mempertahankan identitas lokal; path service lain ditolak. Config relatif di sebelah EXE diprioritaskan oleh worker/service frozen, dengan fallback legacy untuk kompatibilitas.

EXE/config/data dilindungi Administrator/SYSTEM; target XML disediakan dengan akses modify pengguna untuk ekspor Sentinel. Service tetap LocalSystem/automatic/recovery. Hentikan service sebelum menimpa binary saat update; folder permanen jangan dipindahkan. Manifest format 5 mewajibkan capability in_place_install sehingga template lama ditolak oleh pembuat paket store.

Log install.log mencatat tahap instalasi dan error; launcher BAT juga mencatat exit code bila script tidak berjalan. check-agent.bat/status.bat menghasilkan check-agent.log: keberadaan/baca file, service/path/exit code, akses tulis data, menjalankan EXE untuk probe HTTPS dengan verifikasi CA, ekor log agent/startup worker, serta event Windows terkait SIMON. Tidak mengklaim Access denied pasti akibat Sangfor; konsol Sangfor tetap perlu diperiksa untuk kejadian yang tidak tersedia lewat event Windows. Kegagalan jaringan tidak menghapus identitas atau menonaktifkan verifikasi TLS.

Validasi: 45 pytest lulus, mencakup config lokal/fallback, mock OS untuk menjalankan logika installer/migrasi/reinstall dan kegagalan startup dengan transcript, serta ACL Windows pada file fixture. Seluruh script PowerShell lolos parser dan modul Python lolos compile. Tidak memasang service operasional atau mengubah kebijakan keamanan pada PC pengembangan.

Uji EXE final lulus dari salinan paket di folder sementara: config/CA/XML/data relatif di sebelah EXE, probe HTTPS sukses tanpa membuat identitas, enrollment/report/restart dan delete-reenroll mempertahankan UUID/kode store. Pengujian menggunakan server/database/sertifikat sementara; service Windows sungguhan dan Sangfor pada PC store belum diuji. Template binary final tersedia secara lokal di release/SIMONAgent-template.zip; paket store harus dibuat pada server kantor agar memakai CA kantor yang benar.

## Startup user sekali install

Default install.bat menjalankan install-user.ps1 tanpa Administrator; mode service tetap tersedia lewat install-service.bat. EXE/XML tetap dalam paket di drive D, config/CA/launcher/log di LocalAppData/SIMON dan state LocalAppData/SIMON/data, persis lokasi percobaan manual store 417. Installer meminta kode store, membuat shortcut Startup user, langsung memulai peluncur tersembunyi dan mempertahankan identitas. Peluncur memakai mutex per user/session serta pemeriksaan proses dari lokasi EXE yang sama untuk menghindari duplikat. Error launch/exit code dan stderr worker tercatat; agent.log tetap memakai rotasi ukuran.

Agent berjalan setelah user login (termasuk auto-login), tetap aktif saat layar terkunci dan berhenti saat logout. Tidak membuat service/menonaktifkan antivirus/mengubah kebijakan permanen Windows. Kebijakan enterprise tetap dapat menolak PowerShell/Startup/EXE. check-agent.bat mengenali config mode user dan menampilkan log Startup. uninstall-user.bat menghapus shortcut saja; identitas dipertahankan, proses aktif berakhir saat logout.

Validasi: suite sebelumnya 45 ditambah tes installer user mempertahankan UUID/manual state/kode, membuat shortcut dan tidak menjalankan duplikat. Uji tambahan peluncur Windows dengan proses Python fixture menguji hidden launch, stderr dan exit code aktual (2). Suite final: 47 pytest lulus. Semua script lolos parser PowerShell. Startup/COM/launch installer dimock hanya pada fixture agar tidak mengubah Startup user pengembangan. Login/reboot serta Sangfor pada PC store tetap perlu diuji pengguna.

Pembaruan installer tidak memerlukan EXE baru; make-agent-package.bat mengambil script terbaru dari checkout. release/SIMON-startup-update.zip berisi hanya script/README untuk diekstrak menimpa folder paket store lama, tanpa EXE/CA/XML/config/data. Source/template lokal diperbarui; sertifikat kantor harus tetap berasal dari paket server kantor.
