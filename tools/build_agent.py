"""Build a single universal onedir Windows agent; excludes backend dependencies."""
import subprocess,sys,shutil,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if sys.platform!='win32':raise SystemExit('Build di Windows x64 dengan Python 3.12 x64')
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--console','--name','SIMONAgent','--paths',str(ROOT),'--hidden-import','win32timezone','--hidden-import','servicemanager','--hidden-import','win32service','--hidden-import','win32serviceutil','--hidden-import','win32event','--exclude-module','pytest','--exclude-module','fastapi','--exclude-module','sqlalchemy','--exclude-module','openpyxl',str(ROOT/'agent'/'windows_entry.py')],cwd=ROOT,check=True)
release=ROOT/'release'/'SIMONAgent';release.mkdir(parents=True,exist_ok=True)
shutil.copytree(ROOT/'dist'/'SIMONAgent',release/'SIMONAgent',dirs_exist_ok=True)
for source in (ROOT/'deployment'/'agent').iterdir():
 if source.is_file():shutil.copy2(source,release/source.name)
(release/'agent-build.json').write_text(json.dumps({'format':3,'capabilities':['sentinel_xml','store_code','reenrollment_after_delete'],'exe_sha256':hashlib.sha256((release/'SIMONAgent'/'SIMONAgent.exe').read_bytes()).hexdigest()}),encoding='utf-8')
exe=release/'SIMONAgent'/'SIMONAgent.exe'
(release/'SHA256.txt').write_text(hashlib.sha256(exe.read_bytes()).hexdigest()+'  SIMONAgent/SIMONAgent.exe\n')
archive=shutil.make_archive(str(ROOT/'release'/'SIMONAgent-template'),'zip',release)
print('Template agent (belum termasuk public CA kantor):',archive)
