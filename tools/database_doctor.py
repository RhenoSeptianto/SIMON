"""Explain SQLite startup failures without deleting or resetting the database."""
import argparse,ctypes,os,sqlite3,stat,subprocess,sys,tempfile
from pathlib import Path
from contextlib import closing


def check_database(database,repair_readonly=False):
    path=Path(database).resolve()
    parent=path.parent
    print('=== SIMON SQLite check ===',flush=True)
    print('Python:',sys.executable,flush=True)
    print('Database:',str(path),flush=True)
    if os.name=='nt':
        print('Administrator:',bool(ctypes.windll.shell32.IsUserAnAdmin()),flush=True)
    if not parent.is_dir():
        raise RuntimeError(f'Folder database tidak ditemukan: {parent}. Periksa DATABASE_URL/SIAMS_DATA.')
    if path.is_dir():
        raise RuntimeError(f'{path} adalah FOLDER, bukan file SQLite. Jangan hapus data; periksa isi folder dan koreksi lokasi database.')
    existed=path.exists()
    print('File exists:',existed,flush=True)
    if existed:
        info=path.stat()
        print('Size:',info.st_size,'bytes',flush=True)
        readonly=bool(getattr(info,'st_file_attributes',0)&stat.FILE_ATTRIBUTE_READONLY) if os.name=='nt' else not bool(info.st_mode&stat.S_IWUSR)
        print('Read-only attribute:',readonly,flush=True)
        if readonly:
            if not repair_readonly: raise RuntimeError('File database beratribut read-only. Buka Properties file dan hilangkan Read-only.')
            if os.name=='nt':
                attributes=ctypes.windll.kernel32.GetFileAttributesW(str(path))
                if attributes==-1 or not ctypes.windll.kernel32.SetFileAttributesW(str(path),attributes & ~stat.FILE_ATTRIBUTE_READONLY):
                    raise ctypes.WinError()
            else: path.chmod(info.st_mode|stat.S_IWUSR)
            print('Read-only file database dilepas; isi database tidak diubah.',flush=True)
    # Probe a NEW disposable SQLite file to distinguish folder access from DB-file problems.
    temp_path=None
    try:
        fd,name=tempfile.mkstemp(prefix='.simon-access-',suffix='.db',dir=parent)
        os.close(fd);temp_path=Path(name)
        with closing(sqlite3.connect(temp_path,timeout=5)) as connection, connection:
            connection.execute('create table probe(value integer)')
            connection.execute('insert into probe values (1)')
        print('Folder write + new SQLite: OK',flush=True)
    except (OSError,sqlite3.Error) as error:
        raise RuntimeError(f'Python tidak dapat membuat/menulis database uji di folder {parent}: {type(error).__name__}: {error}. Periksa ACL/explicit Deny dan kebijakan proteksi folder.') from error
    finally:
        if temp_path is not None:
            # Only remove files created by this probe, never operational DB or its sidecars.
            for suffix in ('','-journal','-wal','-shm'):
                candidate=Path(str(temp_path)+suffix)
                if candidate.exists():candidate.unlink()
    try:
        connection=sqlite3.connect(str(path),timeout=5)
        try:
            connection.execute('pragma schema_version').fetchone()
            connection.execute('begin immediate')
            connection.rollback()
        finally:connection.close()
    except sqlite3.Error as error:
        code=getattr(error,'sqlite_errorname','unknown')
        raise RuntimeError(f'Folder dapat ditulis, tetapi database {path} gagal dibuka/diakses: {code}: {error}. Periksa atribut/ACL file siams.db serta file journal/WAL jika ada. Database tidak dihapus.') from error
    print('Existing database + write lock: OK' if existed else 'New database created: OK',flush=True)
    return path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--database',required=True)
    parser.add_argument('--repair-readonly',action='store_true')
    args=parser.parse_args()
    try:check_database(args.database,args.repair_readonly)
    except (OSError,RuntimeError) as error:
        print('GAGAL:',error,flush=True)
        if os.name=='nt':
            path=Path(args.database).resolve()
            for item in (path.parent,path):
                if item.exists():subprocess.run(['icacls.exe',str(item)],check=False)
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
