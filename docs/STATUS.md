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

## Koreksi lokasi: seluruh runtime mode user di folder paket

Config/CA/launcher/log dipindahkan dari LocalAppData ke folder paket (contoh D:/SIMONAgent-store); state/UUID/queue/agent.log di SIMONAgent/data. Startup hanya menyimpan shortcut yang menunjuk start-user.ps1 di folder paket. start-user.bat/check-agent.bat mengikuti lokasi paket sendiri. Tidak membuat file operasional baru di LocalAppData. Installer menyalin state legacy LocalAppData jika belum punya identitas lokal; meminta agent lama dihentikan sebelum migrasi bila masih aktif, dan mempertahankan sumber lama. Tidak mengganti XML/CA dengan data generik. Error launcher BAT dicatat ke install-launcher.log di folder paket bila dapat ditulis, selain transcript install-user.log.

Tes migrasi installer dan peluncur lulus, termasuk UUID tetap sama, Startup menunjuk paket, launch ganda dicegah, dan stderr/exit code tertangkap. Seluruh script lolos parser PowerShell. Izin tulis folder D tetap diperlukan; penolakan tidak dialihkan diam-diam ke lokasi lain. Uji store/login aktual dilakukan pengguna.

## Perbaikan final Startup: langsung dari EXE, tanpa PowerShell

Execution Policy terbukti menolak peluncur .ps1 di PC store, sedangkan EXE/HTTPS/telemetry bekerja. Installer dan Startup kini langsung memakai EXE: install.bat -> --install-user; shortcut SIMON Agent.lnk -> EXE --background --config. Native installer membuat config/shortcut lewat Windows COM, memigrasikan identitas lama bila perlu, mencatat log dan memulai worker CREATE_NO_WINDOW. Worker memakai mutex per state untuk mencegah proses ganda. Semua config/data/log tetap di D. Tidak perlu jendela PowerShell terbuka. Script PS lama hanya wrapper kompatibilitas manual, bukan target Startup.

Manifest format 6/native_user_startup mewajibkan EXE baru; update script saja tidak cukup. Pipeline build menyertakan win32com.client. Mode service tetap tersedia. check-agent membaca config native tanpa bergantung launcher.json lama. Startup native tetap setelah login, bukan sebelum login; kebijakan endpoint yang memblokir EXE tetap dapat menolaknya.

Validasi: 46 pytest lulus (dua tes launcher PS lama diganti satu tes native COM aktual). Uji EXE final memakai HTTPS/DB/folder Startup sementara: installer EXE sungguhan membuat shortcut/config dan memulai worker; shortcut .lnk sungguhan berhasil dijalankan; peluncur selesai tetapi worker tetap hidup, tidak memiliki visible window; pemanggilan ulang menyisakan satu worker; agent mengirim data dan otomatis reenroll setelah dashboard delete dengan UUID/kode store sama. Tidak mengubah Startup asli atau service operasional pada mesin pengembangan. Uji boot/login nyata pada PC store tetap perlu pilot.

## Duplikat NBICT-14: penyebab dan pembersihan aktual

Ditemukan service lama aktif dari D:/Desktop/SIMONAgent-store, ditambah worker user dari D:/STORE/SIMONAgent-store dan D:/SIMONAgent-store. Dua folder user memiliki UUID berbeda, sedangkan mutex versi lama dibatasi state sehingga tidak saling menolak. Dua proses uji user dihentikan; service lama dipertahankan Running. Shortcut user yang menunjuk agent uji dilepas setelah disalin ke D:/SIMONAgent-store/previous-startup.lnk agar tidak kembali berjalan saat login.

Dashboard server diverifikasi melalui API admin: tiga record memiliki hostname NBICT-14 dan serial GWT7JG3 yang sama. Backup database dibuat melalui endpoint resmi sebelum pembersihan dan salinan disimpan di data/backups (ignored Git). Assignment TS digabung ke record service aktif ID 2. Record uji ID 3/4 dengan UUID yang sudah diverifikasi cocok dengan state dua proses berhenti dihapus; perangkat lain tidak diubah. NBICT-14 tersisa satu record. Data monitoring yang dihapus tersedia dalam backup, file identitas lokal tidak dihapus.

Pencegahan: mutex Windows Global memakai server sebagai namespace, bukan folder state; melintasi sesi user/service. DACL mengizinkan pemakaian oleh user terautentikasi dan SYSTEM. Installer/runtime user memeriksa service SIMON yang masih aktif dan agent legacy yang memakai config/server sama dari folder lain. Mode service ditandai eksplisit pada worker agar tidak memblokir dirinya sendiri. Manifest 7/machine_single_instance menolak paket lama tanpa fitur ini.

Validasi: 48 pytest lulus termasuk penolakan service legacy dan agent beda folder/server sama. Uji EXE final diperluas: salinan executable di folder kedua dengan state berbeda ditolak sebelum membuat UUID, satu worker asli tetap mengirim data. Login/reboot aktual lintas akun store tetap perlu pilot; pengujian otomatis memakai folder/DB/server sementara.

## Agent baru muncul otomatis di web

Auto-refresh Overview sebelumnya bisa berhenti saat fokus tertinggal pada summary/button di content. Selain itu Overview memotong delapan item pertama sehingga perangkat baru di akhir daftar tidak terlihat. Refresh kini hanya memperbarui angka KPI, jumlah dan tabel perangkat, tanpa merender ulang jadwal/form/fokus. Overview menampilkan delapan PC dengan ID terbaru. Devices tetap memperbarui tabel sambil mempertahankan teks dan fokus pencarian. Polling 10 detik dilindungi flag in-flight dan guard perubahan view/sesi/dialog; kembali ke tab/window memicu pemeriksaan langsung. Cache aset dinaikkan ke v21.

Validasi browser aktual: enroll lewat API tanpa reload/navigasi, agent baru muncul otomatis saat summary jadwal tetap fokus; agent terbaru tetap terlihat dengan lebih dari delapan perangkat; agent baru di Devices muncul otomatis dengan search aktif dan nilai/fokus tetap. Seluruh alur browser desktop/mobile/light/dark, detail, metrics/history/assignment/laporan/login lulus tanpa JavaScript error. Perubahan tampilan ini tidak memerlukan rebuild atau instalasi ulang agent. Setelah update server, reload sekali untuk memuat JavaScript v21; enrollment berikutnya otomatis terlihat.

## Satu kode store untuk satu perangkat

Backend menolak enrollment/update inventory dengan kode store nonkosong yang dimiliki UUID lain (HTTP 409, menyebut nama PC). Perbandingan strip+casefold, nol depan tetap. Instal ulang UUID/claim sama diperbolehkan; Offline tetap memegang kode. Kolom nullable store_code_key + unique index melindungi klaim bersamaan. Pemeriksaan juga membaca raw store_code baris legacy yang belum punya key; duplikat lama tidak dihapus otomatis. Migrasi menambah kolom/index tanpa menghapus data. Commit collision diterjemahkan menjadi 409, bukan error 500.

Installer native memeriksa/reservasi lewat enrollment HTTPS memakai identitas lokal yang sama sebelum menulis config/shortcut. Identitas dibuat sekali jika belum ada. Penolakan/CA/network failure dicatat jelas; config dan Startup belum diganti, tidak mengambil alih perangkat lama. Agent runtime mencatat detail konflik kode dari server dan memperlambat retry agar tidak terus membanjiri endpoint. Template format 8/unique_store_code mewajibkan binary baru untuk pesan/preflight installer. Backend yang diperbarui juga menolak duplikat dari agent lama.

Validasi: 52 pytest lulus, termasuk duplikat case/spasi, PC Offline, reinstall, penolakan takeover dari inventory/enroll, kode dilepas saat pemilik berganti kode, baris legacy dan dua klaim paralel (satu sukses/satu 409). EXE final lewat HTTPS/DB/Startup sementara lulus: duplicate install menampilkan nama pemilik, tidak membuat shortcut/record baru dan tidak menimpa config; reinstall identitas sama serta Startup tersembunyi/dedupe lintas folder/re-enroll tetap bekerja. Browser desktop/mobile/light/dark lulus termasuk enrollment baru otomatis dan laporan/assignment. Server kantor belum di-restart dari sini; update backend/restart dan build/package agent baru diperlukan untuk rollout.

## Reset diminta pengguna dan perbaikan UUID tersalin antar-PC

Pemeriksaan langsung membuktikan NBICT-14 dan PANJOEL-REBORN mengirim UUID 0df3c8ce-fcf7-4a9e-a02a-795daed97645 yang sama, dengan serial BIOS/IP berbeda. Perangkat tidak terhapus oleh uniqueness; inventory dari credential tersalin memperbarui record yang sama. Paket template lokal diperiksa dan tidak berisi identity.json/database, sehingga paket bersih tetap harus dibedakan dari folder instalasi aktif.

Atas permintaan pengguna data monitoring server direset melalui endpoint resmi (backup simon-20261107-144041-07f9652b.db). Akun/audit dipertahankan sesuai pembahasan. Agent lokal yang aktif dihentikan. Total devices tepat setelah reset 0; agent lama Panjul yang masih aktif kemudian otomatis enrollment ulang menjadi 1. Pengguna diminta menghentikan agent remote sebelum reset akhir. Tidak ada klaim bahwa server tetap kosong selama pengirim lama hidup.

Perbaikan: identitas lokal mengikat UUID/claim ke hash MachineGuid (bukan registry asli). Folder yang tersalin dari Windows berbeda memperoleh UUID/claim baru; credential dan queue asing dipindah ke backup data-other-machine-* sebelum dipakai. State legacy tanpa binding ditangani preflight installer: server menolak fingerprint/serial BIOS berbeda dengan kode identity_mismatch, installer mengarantina state lama dan mencoba UUID baru satu kali. Kode store unik tetap diperiksa. Server tidak memperbolehkan enrollment/inventory credential tersalin mengubah hostname/serial/store milik hardware berbeda. Binding server yang sudah ada tidak dapat dihapus oleh inventory legacy. Rename pada hardware sama tetap diperbolehkan. Manifest 9/machine_bound_identity memerlukan build EXE baru dan backend yang sudah direstart; agent lama dengan credential tersalin perlu dihentikan/diperbarui.

Validasi final: 56 pytest lulus. Simulasi dua PC dengan UUID/claim sama ditolak sebelum inventory/store asli berubah; dua UUID dan kode berbeda kemudian tersimpan bersamaan. Tes copy antar-PC memeriksa UUID/claim berbeda, queue tidak terkirim dan backup tersedia; reinstall pada PC sama mempertahankan UUID. Native installer juga diuji merespons mismatch legacy dengan rotasi aman dan shortcut COM aktual. Uji EXE final lewat HTTPS/DB/Startup sementara lulus: UUID tersalin dengan fingerprint lain tidak menimpa PC asal, kode duplikat ditolak tanpa config/Startup overwrite, Startup native tersembunyi dan dedupe lintas folder/re-enrollment tetap bekerja. Pengujian memakai lingkungan sementara, bukan menginstal paket baru ke PC store. Source perlu ditarik dan backend direstart di kantor sebelum rollout EXE terbaru.

## Dashboard menjelaskan cakupan akses admin/TS

Pemeriksaan read-only pada server 9 November mengonfirmasi 3 perangkat Online dengan UUID berbeda (NBICT-14/001, HB-BOARION/401, P11501/115). Data saat itu tidak saling menimpa. Akun dovi hanya diassign device Arion, sehingga tampilan satu PC sesuai izin. Pengguna menyetujui assignment tersebut tetap; tidak ada perubahan assignment atau reset data.

Overview/Devices kini menampilkan keterangan cakupan: Super Admin melihat semua PC tanpa assignment; TS hanya perangkat yang diassign ke akun tersebut. KPI TS memakai Perangkat saya dan Store dipantau, bukan angka Belum diassign yang tidak relevan untuk TS. Tabel Overview menjelaskan delapan perangkat terbaru dan badge menunjukkan 8 terbaru dari N perangkat bila dibatasi, serta petunjuk daftar lengkap di Devices. TS tanpa assignment mendapat instruksi meminta assignment, bukan disuruh menginstal ulang agent. Cache aset v22; auto-refresh tetap mempertahankan fokus dan filter.

Validasi browser sungguhan pada database/server sementara: admin melihat dua PC bersamaan, TS hanya satu PC yang diassign dan tidak melihat PC lain; jumlah dan keterangan cakupan sesuai role. Regresi enrollment otomatis, mobile/desktop/light/dark, detail, metrics/history, assignment, laporan Excel dan login lulus tanpa JavaScript error. Agent/backend/assignment produksi tidak diubah. Setelah git pull di server, reload sekali untuk memuat JS/CSS v22; tidak perlu build atau install ulang agent.

## 0.2.0 — Pembaruan web dari dashboard dengan helper dan rollback

Menu Pembaruan khusus Super Admin: status versi/SHA, Cek update ke origin main yang disepakati, ringkasan commit, Update sekarang dan Lihat log. Tidak ada auto-fetch harian. TS ditolak oleh API dan tidak mendapat menu. Check/start memakai POST dengan CSRF; target harus sama dengan hasil pemeriksaan yang belum kedaluwarsa. Satu request aktif saja; worker memakai lock OS dan jurnal agar job terputus dapat dipulihkan tanpa diterapkan ulang.

Helper stdlib disimpan di data/updater dan task SIMONUpdater terpisah, bukan child web yang ikut mati saat restart. setup-updater.bat dipasang sekali sebagai Admin; hanya untuk server Windows/SIMONServer SYSTEM. Installer memverifikasi database aktif via health fingerprint sebelum mengubah argumen database, membuat snapshot source awal immutable, menyimpan current SHA, memasang ACL SYSTEM/Admin serta task on-demand/boot recovery, lalu memverifikasi HTTPS/SHA/database sebelum menandai helper siap. Task awal dipulihkan bila transisi pemasangan helper gagal. Tidak memasang task operasional pada mesin pengembangan selama tes.

Update memakai git fetch/archive commit main yang diperiksa, fast-forward/ancestor guard dan penolakan source lokal kotor. Release diekstrak ke folder baru, dengan virtual environment/dependensi sendiri; source dan environment lama dipertahankan. Preflight memakai database sementara dan memeriksa API health/update serta aset web. Maintenance menahan API/agent writes selama stop/backup/migrasi/rollback, sedangkan auth read/status/health tetap tersedia. SQLite backup dibuat setelah server berhenti, koneksi ditutup sebelum rename Windows, diperiksa quick_check, lalu task diarahkan ke release dengan data/database absolut yang sama. TLS/key/config runtime tidak diganti.

Kegagalan setelah transisi memulihkan schema/data SQLite, action task, source/environment versi sebelumnya lalu HTTPS/SHA/database diperiksa kembali. Jika rollback gagal, status rollback_failed tetap jelas dan maintenance tidak dilepas. Jurnal/power-loss recovery termasuk transaksi yang sudah selesai tetapi status/cleanup terputus, sehingga hasil tidak diterapkan ulang. Antrean JSON tidak lengkap ditandai gagal dan dikarantina, bukan membuat update macet selamanya. Halaman pulih dari koneksi restart dan reload otomatis sekali setelah sukses agar web terbaru langsung dipakai. Peningkatan ini tidak mengubah EXE agent atau mereset data produksi.

Validasi final: 69 pytest lulus (auth/CSRF, queue tunggal, stage fail, restore schema/data, rollback fail, recovery/power loss, Git archive/check tanpa mengubah checkout, baseline immutable, path database/environment terpisah, health SHA/database match). Smoke menggunakan aplikasi SIMON asli, Git repo/archives, HTTPS dan database sementara: update sukses mempertahankan akun/session/perangkat; candidate yang lolos preflight fresh DB tetapi merusak existing DB lalu crash dipulihkan ke versi/app/data/schema/session sebelumnya. Browser desktop/mobile/light/dark lulus, termasuk setup notice, cek/start, putus koneksi, rollback, reload otomatis sukses dan menu tersembunyi untuk TS. Semua script baru lolos parser PowerShell; modul Python lolos compile.

Batas verifikasi: registrasi dan kontrol Scheduled Task nyata pada PC kantor belum dijalankan; tes tidak mengubah task/service/database kantor. Pemasangan awal manual: pull lalu setup-updater.bat Run as administrator, Ctrl+F5 dan buka Pembaruan. Setelah versi ini terpasang, versi berikutnya baru dibuat untuk pilot tombol update. SQLite saja; database noncocok/non-SQLite ditolak, bukan dialihkan/direset. Panduan operasi/pemulihan: docs/WEB_UPDATE.md.

## 0.2.1 — Health disk dan identitas versi

Menu **Pembaruan** berganti nama menjadi **UpdateSimon**. Versi web yang benar-benar sedang berjalan ditampilkan di kiri bawah sidebar dan berasal dari file `VERSION` server, termasuk untuk akun TS.

Tabel perangkat di Overview dan Devices sekarang menampilkan Health Disk untuk setiap physical disk yang dilaporkan Hard Disk Sentinel, misalnya Disk 1 dan Disk 2 secara terpisah. Nilai tidak ditebak dari status Windows atau persentase wear: data yang tidak tersedia tetap ditulis Belum tersedia, 0% tetap valid, dan nilai Sentinel terakhir yang sudah tidak fresh diberi keterangan Data terakhir. Perubahan tabel ikut mekanisme refresh sekitar 10 detik yang sudah ada.

Release ini hanya mengubah web/backend dan tidak mengubah protokol agent, format database, helper update, atau paket agent store. Karena itu EXE agent tidak perlu dibangun atau dipasang ulang.

## 0.2.2 — Prioritas health disk

Health Disk di bawah batas Sentinel (default 80%, mengikuti `SENTINEL_HEALTH_WARNING`) ditandai merah. Perangkat yang memiliki minimal satu disk di bawah batas diprioritaskan ke baris teratas; perangkat kritis diurutkan dari health terendah, sedangkan urutan perangkat lain tetap dipertahankan. Nilai kosong tidak dianggap kritis dan tepat 80% tidak ditandai karena alert berlaku untuk nilai di bawah batas.
