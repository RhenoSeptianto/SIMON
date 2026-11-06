# Startup native EXE - tidak memakai PowerShell

Build terbaru wajib: manifest format 6, capability native_user_startup. install.bat langsung menjalankan SIMONAgent.exe --install-user. Isi kode store; EXE menyimpan config/data/log di folder paket, membuat shortcut Startup yang langsung menunjuk EXE --background --config, lalu meluncurkan worker Windows tanpa jendela. Tidak perlu PowerShell dibiarkan terbuka. Agent aktif setelah user login, tetap aktif saat layar terkunci, berhenti saat logout.

Update di server: git pull, tools/build-agent.bat, deployment/server/make-agent-package.bat. Build EXE WAJIB untuk fitur ini; mengganti script saja tidak cukup. Ekstrak paket baru di folder lama, pertahankan XML/config/data. Pastikan agent lama berhenti sebelum mengganti binary, kemudian klik install.bat biasa dan isi kode store atau Enter mempertahankan kode lama. Identitas di SIMONAgent/data dipertahankan; LocalAppData hanya dibaca untuk migrasi identitas bila belum ada di D.

Semua file tetap di folder paket seperti D:/SIMONAgent-store: config.json, ca.crt, install-user.log, startup.log, background.pid, serta SIMONAgent/SIMONAgent.exe, SIMONAgent/HDSentinel.xml, SIMONAgent/data (UUID/queue/agent.log). Folder Windows Startup hanya berisi shortcut SIMON Agent.lnk. Jangan pindahkan folder atau menyalin identitas antar-PC.

start-user.bat menjalankan EXE background langsung. install-user.ps1/start-user.ps1 hanya wrapper kompatibilitas manual, bukan target Startup. install-service.bat tetap pilihan service/admin. uninstall-user.bat menghapus shortcut; identitas tetap. Saat update konfigurasi, hentikan agent lama atau logout/login agar proses membaca nilai baru. Perlindungan instance tunggal mencegah proses ganda untuk state yang sama.

Log instalasi: install-user.log; kegagalan EXE sebelum masuk installer dicatat BAT sebisa mungkin pada install-launcher.log. Log peluncuran/startup error: startup.log, log data: SIMONAgent/data/agent.log. check-agent.bat adalah diagnostik opsional berbasis PowerShell; Startup dan agent tidak bergantung padanya. Akses tulis folder D tetap diperlukan, kebijakan keamanan organisasi tetap berlaku, antivirus tidak dinonaktifkan.

Validasi lokal memakai shortcut COM sungguhan di folder tes, EXE final, HTTPS/DB sementara: worker tetap hidup setelah peluncur selesai, tanpa jendela worker, tanpa proses ganda, dan UUID tetap saat restart/reenrollment. Reboot/login serta kebijakan keamanan aktual PC store tetap perlu uji pilot.
