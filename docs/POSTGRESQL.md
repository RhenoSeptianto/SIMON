# Migrasi SIMON dari SQLite ke PostgreSQL

PostgreSQL direkomendasikan untuk server kantor dengan ratusan agent. Migrasi hanya mengubah database server; URL HTTPS, CA, UUID, kode store, assignment, akun, histori, dan agent yang sudah tersebar tetap sama.

## Persiapan

1. Update SIMON ke versi 1.1.2 melalui UpdateSimon saat server masih memakai SQLite.
2. Pastikan menu dan agent kembali normal setelah update.
3. Sinkronkan checkout operasional karena UpdateSimon menjalankan snapshot release tanpa menimpa folder Git: `git pull --ff-only origin main` dari folder repo server.
4. Instal PostgreSQL for Windows pada PC server. Pertahankan port lokal default `5432` dan ingat password user administrator `postgres`.
5. PostgreSQL tidak perlu dibuka ke jaringan store. Agent tetap hanya mengakses HTTPS SIMON port 8443.

## Jalankan migrasi

Di PC server, buka `D:\IT\simon\deployment\server`, klik kanan `migrate-postgresql.bat`, lalu pilih **Run as administrator**. Masukkan password user PostgreSQL `postgres` saat diminta.

Proses otomatis:

- menghentikan task SIMONServer;
- membuat backup konsisten `data\backups\pre-postgresql-*.db`;
- membuat role `simon_app` dan database `simon` dengan password acak;
- menyalin seluruh tabel dalam satu transaksi dan menyesuaikan sequence ID;
- menyimpan koneksi di `data\database-url.txt` dengan ACL hanya SYSTEM/Administrators;
- menjalankan SIMON dengan PostgreSQL dan memverifikasi `/api/health`;
- memasang ulang helper UpdateSimon agar backup dan rollback berikutnya memakai `pg_dump`/`pg_restore`.

Jangan menyalin atau mengunggah `database-url.txt`. File tersebut berisi credential database. Jangan menghapus `siams.db` atau backup SQLite setelah migrasi sampai operasional sudah diverifikasi.

## Verifikasi

Login ke SIMON dan pastikan jumlah perangkat, pengguna, assignment, serta histori sama. Endpoint health harus melaporkan `database_kind: postgresql`. Agent akan menyambung kembali otomatis; tidak perlu install ulang.

```powershell
Invoke-RestMethod https://127.0.0.1:8443/api/health
```

Jika sertifikat lokal belum dipercaya, gunakan browser/dashboard untuk pemeriksaan atau sertakan CA SIMON dengan alat yang mendukungnya. Jangan menonaktifkan verifikasi TLS pada agent.

## Kegagalan dan pemulihan

Jika pemindahan atau health check gagal, script mengembalikan action Task Scheduler sebelumnya dan menjalankan server SQLite lama. Database SQLite tidak dihapus. Simpan seluruh pesan error serta `data\logs\server.log` sebelum mencoba ulang.

Migrasi ulang hanya mengganti database `simon` yang sebelumnya dibuat oleh proses migrasi apabila `data\database-url.txt` sudah ada. Database PostgreSQL lain tidak disentuh. Setelah PostgreSQL aktif, `setup-server.bat` dan UpdateSimon mempertahankan koneksi PostgreSQL.

Backup manual menu Database menghasilkan `.dump` PostgreSQL. Rollback UpdateSimon memakai backup custom PostgreSQL dan memverifikasi fingerprint database sebelum membuka kembali penulisan agent.
