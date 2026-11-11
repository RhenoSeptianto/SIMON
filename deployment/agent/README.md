# Startup native EXE - tidak memakai PowerShell

Build terbaru wajib: manifest format 6, capability native_user_startup. install.bat langsung menjalankan SIMONAgent.exe --install-user. Isi kode store; EXE menyimpan config/data/log di folder paket, membuat shortcut Startup yang langsung menunjuk EXE --background --config, lalu meluncurkan worker Windows tanpa jendela. Tidak perlu PowerShell dibiarkan terbuka. Agent aktif setelah user login, tetap aktif saat layar terkunci, berhenti saat logout.

Update di server: git pull, tools/build-agent.bat, deployment/server/make-agent-package.bat. Build EXE WAJIB untuk fitur ini; mengganti script saja tidak cukup. Ekstrak paket baru di folder lama, pertahankan XML/config/data. Pastikan agent lama berhenti sebelum mengganti binary, kemudian klik install.bat biasa dan isi kode store atau Enter mempertahankan kode lama. Identitas di SIMONAgent/data dipertahankan; LocalAppData hanya dibaca untuk migrasi identitas bila belum ada di D.

Semua file tetap di folder paket seperti D:/SIMONAgent-store: config.json, ca.crt, install-user.log, startup.log, background.pid, serta SIMONAgent/SIMONAgent.exe, SIMONAgent/HDSentinel.xml, SIMONAgent/data (UUID/queue/agent.log). Folder Windows Startup hanya berisi shortcut SIMON Agent.lnk. Jangan pindahkan folder atau menyalin identitas antar-PC.

start-user.bat menjalankan EXE background langsung. install-user.ps1/start-user.ps1 hanya wrapper kompatibilitas manual, bukan target Startup. install-service.bat tetap pilihan service/admin. uninstall-user.bat menghapus shortcut; identitas tetap. Saat update konfigurasi, hentikan agent lama atau logout/login agar proses membaca nilai baru. Perlindungan instance tunggal mencegah proses ganda untuk state yang sama.

Log instalasi: install-user.log; kegagalan EXE sebelum masuk installer dicatat BAT sebisa mungkin pada install-launcher.log. Log peluncuran/startup error: startup.log, log data: SIMONAgent/data/agent.log. check-agent.bat adalah diagnostik opsional berbasis PowerShell; Startup dan agent tidak bergantung padanya. Akses tulis folder D tetap diperlukan, kebijakan keamanan organisasi tetap berlaku, antivirus tidak dinonaktifkan.

Validasi lokal memakai shortcut COM sungguhan di folder tes, EXE final, HTTPS/DB sementara: worker tetap hidup setelah peluncur selesai, tanpa jendela worker, tanpa proses ganda, dan UUID tetap saat restart/reenrollment. Reboot/login serta kebijakan keamanan aktual PC store tetap perlu uji pilot.

Pencegahan duplikat terbaru (manifest 7/machine_single_instance): kunci Windows Global berlaku per PC/server lintas folder data dan sesi Windows. Installer mode user menolak jika service SIMON lama masih berjalan atau agent dari konfigurasi folder lain terdeteksi aktif untuk server yang sama. Worker service memakai penanda mode service, sehingga tidak menolak dirinya sendiri. Jangan menjalankan service dan Startup bersamaan; pilih satu mode. Update ini wajib rebuild EXE, lalu buat paket baru.

## Kode store unik

Satu kode store nonkosong hanya untuk satu identitas PC, termasuk perangkat Offline. Spasi tepi dan perbedaan huruf besar/kecil tidak membuat kode baru; nol di depan tetap dipertahankan. Instal ulang dengan UUID/claim sama boleh memakai kode lama. PC berbeda ditolak HTTP 409 dengan nama PC pemilik; tidak menimpa akun/assignment/histori. Hentikan agent lama sebelum melepas/menghapus record untuk penggantian PC. Jangan menghapus identitas lokal saat update.

Update backend lalu restart server untuk mengaktifkan validasi dan migrasi kolom/index database tanpa menghapus data. Agent lama tetap dapat mengirim data untuk kode yang sah. Agar install.bat memeriksa kode sebelum membuat Startup dan menampilkan pesan jelas, build EXE baru (manifest 8/unique_store_code), lalu make-agent-package.bat dan sebar paket baru. Pemeriksaan installer memerlukan koneksi HTTPS/CA yang valid; jika konflik atau pemeriksaan gagal, konfigurasi/Startup belum diperbarui. Duplikat legacy yang sudah ada tidak dihapus otomatis dan tetap perlu ditinjau admin.

## Identitas PC saat folder agent tersalin

Build terbaru wajib manifest 9/machine_bound_identity. UUID/claim disimpan bersama hash MachineGuid Windows (nilai registry asli tidak dikirim). Instal ulang pada Windows yang sama mempertahankan identitas. Bila data berasal dari PC lain, installer membuat identitas terpisah dan mengarantina credential/queue lama ke data-other-machine-* tanpa mengirim antrean PC asal. Untuk state legacy tanpa binding, server memeriksa identitas hardware pada preflight; mismatch ditolak, installer menyimpan backup lokal lalu mencoba UUID baru sekali. Kode store unik tetap berlaku, tidak otomatis mengambil kode PC lain.

Server menolak enrollment/inventory yang memakai UUID lama tetapi Machine ID atau serial BIOS valid berbeda, sehingga hostname/serial/kode perangkat asal tidak tertimpa. Rename hostname pada hardware yang sama tetap diperbolehkan. Perangkat lama yang masih berjalan dengan credential tersalin perlu dihentikan dan diperbarui; reset database saja tidak memperbaiki file identitas tersalin dan agent aktif bisa langsung mendaftar kembali. Sebarkan ZIP bersih hasil server, bukan folder instalasi yang sudah berisi data.

Urutan rollout: hentikan agent lama; update source server dan restart backend; build EXE baru lalu buat paket dari CA server kantor; instal paket baru di tiap PC dengan kode store masing-masing; uji dua perangkat muncul bersamaan sebelum penyebaran luas. Semua config/data/log tetap di drive D.

SIMON 1.0 memakai manifest format 10/capability `agent_build_identity`. Agent mengirim versi dan SHA build di inventory agar dashboard dapat menunjukkan Agent terbaru/perlu diperbarui tanpa polling tambahan. Instal ulang pada PC yang sama tetap mempertahankan `config.json`, `SIMONAgent/data`, dan `HDSentinel.xml`.
