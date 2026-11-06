# Mode default: Startup user (tanpa Administrator)

Ekstrak ke D:\SIMONAgent-store, klik dua kali install.bat (atau install-user.bat) sebagai user biasa, isi kode store. Installer membuat shortcut SIMON Agent.lnk di Startup user dan menjalankan peluncur tersembunyi. EXE tetap di SIMONAgent/SIMONAgent.exe; XML tetap di SIMONAgent/HDSentinel.xml. Tidak membuat service atau mengubah kebijakan antivirus.

Konfigurasi, CA dan log pemasangan/startup ada di %LOCALAPPDATA%/SIMON; identitas/antrean/log agent di %LOCALAPPDATA%/SIMON/data. Lokasi ini sama dengan percobaan manual store 417: jangan dihapus supaya UUID tetap. Jalankan installer di akun Windows yang biasa dipakai store. Agent otomatis aktif setelah akun itu login, tetap berjalan saat layar dikunci dan berhenti saat logout. PC yang otomatis masuk Desktop juga otomatis menjalankan Startup.

Installer tidak menjalankan salinan kedua bila EXE dari lokasi itu masih berjalan. Untuk beralih dari uji manual, tutup agent manual dengan Ctrl+C sebelum instalasi. Setelah instalasi, reboot/login untuk uji Startup. Jalankan check-agent.bat sebagai user biasa untuk memeriksa mode user; event Windows tertentu mungkin hanya tersedia untuk administrator. start-user.bat menjalankan peluncur lagi; uninstall-user.bat menghapus shortcut Startup (agent yang sudah berjalan berhenti saat logout). Jangan menjalankan start.bat/stop.bat/uninstall.bat untuk mode user: file itu khusus service.

Bila kebijakan organisasi memblokir PowerShell, Startup atau EXE, mode ini juga bisa gagal dan tercatat di log sejauh proses sempat berjalan. Script tidak menonaktifkan antivirus atau mengubah kebijakan organisasi. Local process ExecutionPolicy Bypass hanya dipakai oleh launcher BAT/shortcut seperti installer sebelumnya, tidak mengubah setting permanen Windows.

Untuk paket terbaru dari source server, cukup git pull lalu make-agent-package.bat bila EXE sudah mendukung in_place_install. Tidak perlu rebuild EXE untuk perubahan installer Startup ini. Paket pembaruan SIMON-startup-update.zip hanya berisi script/README; ekstrak ke folder paket agent yang sudah ada tanpa mengganti EXE, CA, XML atau data.

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
