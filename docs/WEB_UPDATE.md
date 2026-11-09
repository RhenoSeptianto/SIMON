# Update SIMON dari Dashboard

Versi awal fitur: **0.2.0**. Khusus **Super Admin**. Sumber update adalah repo `RhenoSeptianto/SIMON`, branch `main`. Fitur ini memperbarui web/backend server; EXE agent store tidak diganti otomatis.

## Pemasangan awal satu kali di server kantor

1. Buka PowerShell pada PC server dan tarik source:

   ```powershell
   git -C D:\IT\simon-baru pull --ff-only origin main
   ```

2. Buka folder `D:\IT\simon-baru\deployment\server`, klik kanan **setup-updater.bat → Run as administrator**. Server SIMON harus sudah terpasang lewat setup-server.bat. Installer helper akan memulai ulang server sementara untuk verifikasi dan pemasangan snapshot awal.
3. Setelah muncul pesan helper siap, buka dashboard sebagai Super Admin dan tekan **Ctrl+F5 sekali**. Pilih **Pembaruan**.
4. Klik **Cek update**. Setelah fitur ini baru dipasang, hasil "versi terbaru" adalah normal: versi berikutnya harus di-push ke main dahulu.

Tidak perlu build atau memasang ulang agent untuk memasang fitur update web. Jangan memasang helper pada PC store. Helper menggunakan task Windows `SIMONUpdater`; server tetap menggunakan task `SIMONServer` sebagai SYSTEM. Git harus tersedia saat pemasangan; path Git disimpan supaya dapat dipakai SYSTEM.

Untuk lokasi data nonstandar, gunakan parameter `-DataPath` pada setup-updater.ps1. Database harus SQLite bernama siams.db pada lokasi data tersebut dan harus cocok dengan database server aktif. PostgreSQL/lokasi database yang tidak cocok akan ditolak, bukan diam-diam direset.

## Pembaruan berikutnya

1. Login Super Admin → **Pembaruan → Cek update**.
2. Jika ada update, periksa ringkasan perubahan dan klik **Update sekarang**.
3. Tunggu hasilnya. Koneksi halaman boleh terputus sementara saat restart; halaman mencoba tersambung kembali. Setelah sukses, halaman memuat ulang otomatis untuk memakai web terbaru.
4. Jika update gagal, hasilnya menunjukkan apakah versi lama berhasil dipulihkan. Log dapat dibuka lewat **Lihat log**.

Sebelum tombol update digunakan, Git harus bersih dari perubahan source lokal. Update tidak menjalankan git reset --hard dan tidak menimpa source yang sedang berjalan. Dibutuhkan akses jaringan ke GitHub serta sumber paket Python/PyPI saat menyiapkan environment versi baru.

## Cara kerja dan rollback

- Helper stabil disimpan di `data/updater`, terpisah dari proses web. Task helper dijalankan atas permintaan dan saat boot untuk memulihkan pekerjaan yang terputus; tidak membuat backup harian atau memeriksa Git otomatis setiap hari.
- Bahkan aplikasi awal dibuatkan snapshot source. Versi baru diekstrak dari SHA Git yang telah diperiksa ke folder release tersendiri, dengan virtual environment Python sendiri. Versi lama tetap ada.
- Sebelum mematikan server, helper memasang dependensi dan menguji versi baru memakai database sementara yang terpisah. Versi lama masih melayani pengguna selama persiapan ini.
- Pada fase pemasangan, API perubahan data dan kiriman agent ditahan dengan HTTP 503. Status update, identitas sesi dan health check tetap dapat dibaca. Agent akan mencoba mengirim kembali; status perangkat dapat sementara Offline.
- Server dihentikan, backup SQLite dibuat lewat API backup SQLite dan diperiksa, lalu task server diarahkan ke versi baru dengan lokasi data/database absolut yang sama.
- Pemeriksaan HTTPS memverifikasi CA, akses database dan SHA versi baru. Keberhasilan proses saja tidak dianggap cukup.
- Jika pemasangan/migrasi/health check gagal, helper menghentikan versi gagal, memulihkan database dan task/environment versi sebelumnya, lalu memeriksa HTTPS versi lama. Akses perubahan data baru dibuka setelah pemulihan berhasil.
- Jika rollback juga gagal, status menjadi **Pemulihan perlu diperiksa**, log berisi penyebab, dan maintenance tetap aktif. Sistem tidak mengklaim update berhasil. Setelah penyebab diperbaiki admin dapat menjalankan task SIMONUpdater lagi untuk mencoba pemulihan jurnal.
- Jurnal transaksi disimpan atomik. Pekerjaan yang terputus sebelum selesai dipulihkan saat helper berjalan lagi/boot. Transaksi yang sudah selesai tidak diterapkan ulang.

Rollback otomatis didasarkan pada kegagalan pemasangan dan pemeriksaan server/versi/database yang dapat dideteksi. Itu bukan jaminan mendeteksi setiap bug fungsi atau tampilan pada kode baru; perubahan tetap harus diuji sebelum di-push.

Jangan menghapus `data/updater`, virtual environment awal, folder release atau backup saat masih dipakai. Jangan menjalankan setup-server.bat lagi hanya untuk update rutin; gunakan tombol dashboard. Source Git awal tetap menjadi tempat fetch/build agent manual, sedangkan task web memakai snapshot release.

## Log dan pemulihan manual

- `data/updater/update.log`: tahap dan hasil update; tersedia lewat dashboard Super Admin.
- `data/updater/status.json`: status terakhir.
- `data/updater/journal.json`: konfigurasi versi sebelum update dan backup untuk rollback.
- `data/updater/backups/<job>/database.db`: backup sebelum pemasangan.
- `data/logs/server.log`: log server.

Jika rollback belum berhasil, jangan reset database. Periksa log/izin/disk terlebih dahulu. Setelah penyebab diperbaiki, jalankan PowerShell sebagai Administrator:

```powershell
Start-ScheduledTask -TaskName SIMONUpdater
```

Pemasangan pertama dan uji restart/login nyata pada server kantor tetap perlu dilakukan oleh admin. Pengujian otomatis tidak memasang task atau mengubah database server kantor.

## Verifikasi pengembangan

- `python -m pytest -q`: auth/CSRF, pekerjaan ganda, sukses/gagal, restore data dan schema, kegagalan rollback serta pemulihan power loss.
- `python tests/update_smoke.py`: archive Git dan proses HTTPS aplikasi SIMON asli pada database sementara; update sukses mempertahankan akun/session/perangkat, migrasi gagal dipulihkan.
- `python tests/browser_details.py`: desktop/mobile/light/dark, tombol check/update, putus koneksi, hasil rollback, reload otomatis dan pembatasan TS.

Dasar mekanisme: [Microsoft Set-ScheduledTask](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/set-scheduledtask) dan [SQLite Online Backup API](https://sqlite.org/backup.html).
