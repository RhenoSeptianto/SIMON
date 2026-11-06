import sqlite3,stat
from pathlib import Path
from contextlib import closing
import pytest
from tools.database_doctor import check_database


def test_existing_database_is_preserved(tmp_path,capsys):
    file=tmp_path/'siams.db'
    with closing(sqlite3.connect(file)) as db, db:
        db.execute('create table users(name text)');db.execute("insert into users values ('kept')")
    check_database(file)
    with closing(sqlite3.connect(file)) as db, db:
        assert db.execute('select name from users').fetchone()==('kept',)
        assert db.execute("select name from sqlite_master where type='table'").fetchall()==[('users',)]
    assert not list(tmp_path.glob('.simon-access-*'))
    assert 'Folder write + new SQLite: OK' in capsys.readouterr().out


def test_missing_parent_is_reported_without_creating_wrong_database(tmp_path):
    file=tmp_path/'missing'/'siams.db'
    with pytest.raises(RuntimeError,match='Folder database tidak ditemukan'):check_database(file)
    assert not file.parent.exists()


def test_directory_named_db_is_not_removed(tmp_path):
    folder=tmp_path/'siams.db';folder.mkdir();(folder/'keep.txt').write_text('keep')
    with pytest.raises(RuntimeError,match='FOLDER'):check_database(folder)
    assert (folder/'keep.txt').read_text()=='keep'


def test_readonly_attribute_repaired_only_when_requested(tmp_path):
    file=tmp_path/'siams.db'
    with closing(sqlite3.connect(file)) as db, db:db.execute('create table kept(value integer)')
    original=file.stat().st_mode;file.chmod(stat.S_IREAD)
    try:
        with pytest.raises(RuntimeError,match='read-only'):check_database(file)
        check_database(file,repair_readonly=True)
        with closing(sqlite3.connect(file)) as db, db:
            assert db.execute("select name from sqlite_master where name='kept'").fetchone()==('kept',)
    finally:file.chmod(original)


def test_invalid_file_reports_error_and_preserves_bytes(tmp_path):
    file=tmp_path/'siams.db';file.write_bytes(b'not a SQLite database; keep this file')
    before=file.read_bytes()
    with pytest.raises(RuntimeError,match='Folder dapat ditulis'):check_database(file)
    assert file.read_bytes()==before
    assert not list(tmp_path.glob('.simon-access-*'))
