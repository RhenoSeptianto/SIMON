# Mode default: semua file di folder paket drive D

1. Ekstrak paket ke D:\SIMONAgent-store (atau folder permanen lain).
2. Tutup agent manual dengan Ctrl+C; jika agent lama tersembunyi masih aktif, logout/login dahulu.
3. Klik dua kali install.bat biasa, isi kode store. Installer membuat Startup dan menjalankan agent.
4. EXE/XML tetap di SIMONAgent/. Config, CA, launcher dan log instalasi/Startup di folder utama paket. Identitas, antrean, agent.log di SIMONAgent/data/.
5. XML Sentinel: D:\SIMONAgent-store\SIMONAgent\HDSentinel.xml. Arahkan ekspor setiap 10 detik.

Semua file operasional berada di D; Windows hanya menyimpan shortcut standar SIMON Agent.lnk pada Startup user. Installer membaca identitas lama dari LocalAppData/SIMON/data hanya saat migrasi dan menyalinnya ke D bila belum ada identitas lokal. Sumber lama tidak dihapus. Jika agent masih berjalan saat perlu migrasi, installer meminta dihentikan dahulu agar antrean/UUID tidak rusak. Jangan menyalin folder terpasang beserta data ke PC lain.

Log langsung di folder paket: install-user.log, install-launcher.log (kode kegagalan launcher BAT), startup.log, worker-stderr.log dan check-agent.log. Log agent: SIMONAgent/data/agent.log. Jalankan check-agent.bat untuk pemeriksaan; start-user.bat untuk menjalankan lagi; uninstall-user.bat menghapus Startup saja. Folder D harus dapat ditulis oleh user. Bila akses ditolak, pesan terlihat di jendela installer; log hanya dapat dibuat jika folder mengizinkan penulisan. Tidak diam-diam memakai LocalAppData sebagai fallback.

Setelah instalasi, uji reboot/login. Agent otomatis setelah user login, tetap aktif saat layar dikunci dan berhenti saat logout. Jangan pindahkan folder setelah instalasi. Pengaturan keamanan enterprise tetap dapat memblokir aplikasi/script; installer tidak menonaktifkan antivirus atau mengubah kebijakan permanen Windows.

Update script Startup tidak memerlukan rebuild EXE. Pada server: git pull, lalu make-agent-package.bat. Untuk PC lama, ekstrak SIMON-startup-update.zip ke folder paket, jangan menghapus XML/data, kemudian install.bat.

## Mode service opsional (memerlukan Administrator)

Gunakan install-service.bat bila memang ingin service otomatis sebelum login. Instruksi berikut berlaku untuk mode service:

# Paket agent SIMON (Windows 10/11 x64)

1. Ekstrak paket ke lokasi permanen, contoh D:\SIMONAgent-store. Jangan menjalankan langsung dari ZIP.
2. Klik kanan install.bat -> Run as administrator, isi kode store. Enter saat update mempertahankan kode lama.
3. EXE tetap di SIMONAgent/SIMONAgent.exe; installer tidak menyalin ke Program Files atau membuat state baru di ProgramData.
4. Arahkan ekspor otomatis HDD Sentinel setiap 10 detik ke D:\SIMONAgent-store\SIMONAgent\HDSentinel.xml (sesuaikan lokasi paket).
5. Service otomatis berjalan saat Windows menyala, tanpa login. Super Admin bisa assign PC ke TS.

Di sebelah EXE terdapat config.json, ca.crt, HDSentinel.xml dan folder data (identitas/credential, antrean, log). Nama folder paket boleh berbeda; installer mengikuti lokasi sendiri. Jangan memindahkan folder setelah instalasi. Jangan membagikan folder yang SUDAH dipasang ke PC lain karena berisi identitas PC. Sebarkan ZIP bersih hasil make-agent-package.bat.

Update: stop.bat sebagai Administrator sebelum menimpa binary dengan paket baru pada lokasi yang sama, lalu install.bat. Jangan hapus config.json, data atau XML. Installer memigrasikan state dari ProgramData/SIAMS jika folder lokal belum punya identitas, mempertahankan kode store, lalu mengubah path service lama dari Program Files. Data lama tidak dihapus. Jika service mengarah ke folder paket lain, installer berhenti agar identitas tidak tertukar.

CPU/RAM/drive dan heartbeat sekitar 10 detik. Sentinel dibaca saat XML berubah. Histori CPU/RAM 5 menit; disk hanya kondisi terbaru dan alert penting. Antrean offline maksimal 2.000 event. Server default https://172.18.123.92:8443 melalui LAN/VPN; verifikasi CA tetap aktif.

## Memeriksa masalah

- install.log di folder paket mencatat tahap instalasi, output dan pesan kegagalan.
- Jalankan check-agent.bat sebagai Administrator (status.bat juga menjalankan pemeriksaan yang sama). Hasil ditambahkan ke check-agent.log: file/akses, service/path/exit code, akses tulis data, percobaan EXE dan HTTPS, log agent terakhir, serta event Windows terkait SIMON selama 2 jam terakhir.
- Log worker berada di SIMONAgent/data/agent.log dengan rotasi ukuran. diagnose.bat memeriksa hardware tanpa mengirim data.
- Jika EXE hilang, periksa kelengkapan paket dan karantina antivirus. Access denied belum membuktikan pemblokiran antivirus. Event Sangfor tidak selalu tersedia lewat log Windows; pengelola perlu memeriksa konsol Sangfor sesuai waktu kejadian. Jangan mematikan antivirus.
- Jika PowerShell sendiri diblokir sebelum script berjalan, install.bat mencatat kode keluar sebisa mungkin; check-agent.ps1 juga mungkin diblokir dan perlu diperiksa pengelola keamanan.

Service berjalan sebagai LocalSystem. EXE/config/data dilindungi untuk Administrator dan SYSTEM; file XML disediakan agar pengguna Windows dapat memperbarui laporan Sentinel. Bila Sentinel memakai ekspor melalui file sementara/rename dan ditolak, jalankan Sentinel dengan akun Administrator atau minta pengelola menyesuaikan izin ekspor secara khusus. Jangan membuka akses tulis EXE/config ke semua pengguna.

Uninstall hanya melepas service. Jika PC dihapus dari dashboard sementara agent aktif, agent otomatis mendaftar ulang dengan UUID/kode store sama; histori/assignment lama tidak kembali. Pengujian service/reboot dan kebijakan Sangfor tetap perlu pilot di PC store.
