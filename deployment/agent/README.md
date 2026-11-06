# Paket agent SIMON (Windows 10/11 x64)

1. Pastikan server https://172.18.123.92:8443 dapat dijangkau lewat LAN/VPN kantor.
2. Paket harus berisi folder SIMONAgent/ lengkap, ca.crt, dan installer. Jangan hanya menyalin exe.
3. Klik kanan install.bat -> Run as administrator, isi kode store. Saat update, Enter mempertahankan kode lama.
4. Cek status.bat. Perangkat muncul otomatis di dashboard; Super Admin assign ke TS.

Tidak perlu Python pada PC store. Tidak perlu port inbound di PC store. Service berjalan sebagai LocalSystem agar reliability counter Windows dapat dibaca. State/credential disimpan di ProgramData/SIAMS dengan ACL administrator/SYSTEM; konfigurasi di ProgramData/SIMON. Jangan salin folder state antarkomputer. Install ulang mempertahankan UUID. Uninstall hanya melepas service dan mempertahankan state/binary.

SSD/HDD: mengikuti ekspor otomatis HDSentinel.xml (sekitar 10 detik). Arahkan ekspor Sentinel ke C:\Program Files\SIMON\HDSentinel.xml. Kondisi disk terbaru saja; riwayat alert penting tetap dicatat. CPU/RAM/drive: sekitar 5 menit. Heartbeat: sekitar 2 menit. Internet/server putus: antrean offline terbatas 2.000 event dan retry otomatis. CPU store tetap perlu diukur lewat pilot beberapa PC.

stop.bat/start.bat/uninstall.bat memerlukan Administrator. diagnose.bat membaca hardware tanpa mengirim data; jangan menyebarkan hasil diagnostik berisi serial/IP ke publik. Binary belum ditandatangani; uji pilot dan kebijakan Windows kantor sebelum rollout luas. Jangan mematikan antivirus.
