"""Build a single universal onedir Windows agent; excludes backend dependencies."""
import subprocess,sys,shutil,hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if sys.platform!='win32':raise SystemExit('Build di Windows x64 dengan Python 3.12 x64')
try:source_sha=os.getenv('GITHUB_SHA') or subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
except Exception:source_sha=''
version=(ROOT/'VERSION').read_text(encoding='utf-8-sig').strip()
build_info=ROOT/'agent'/'build_info.py';original=build_info.read_text(encoding='utf-8')
build_info.write_text(f'"""Generated for the frozen SIMON agent."""\nVERSION={version!r}\nSOURCE_SHA={source_sha!r}\n',encoding='utf-8')
try:subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--console','--name','SIMONAgent','--paths',str(ROOT),'--hidden-import','win32com.client','--hidden-import','win32timezone','--hidden-import','servicemanager','--hidden-import','win32service','--hidden-import','win32serviceutil','--hidden-import','win32event','--exclude-module','pytest','--exclude-module','fastapi','--exclude-module','sqlalchemy','--exclude-module','openpyxl',str(ROOT/'agent'/'windows_entry.py')],cwd=ROOT,check=True)
finally:build_info.write_text(original,encoding='utf-8')
release=ROOT/'release'/'SIMONAgent';release.mkdir(parents=True,exist_ok=True)
shutil.copytree(ROOT/'dist'/'SIMONAgent',release/'SIMONAgent',dirs_exist_ok=True)
for source in (ROOT/'deployment'/'agent').iterdir():
 if source.is_file():shutil.copy2(source,release/source.name)
exe=release/'SIMONAgent'/'SIMONAgent.exe'
metadata={'format':10,'source_sha':source_sha,'version':version,'capabilities':['sentinel_xml','store_code','reenrollment_after_delete','ten_second_metrics','in_place_install','native_user_startup','machine_single_instance','unique_store_code','machine_bound_identity','agent_build_identity'],'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
(release/'agent-build.json').write_text(json.dumps(metadata),encoding='utf-8')
(release/'SHA256.txt').write_text(metadata['exe_sha256']+'  SIMONAgent/SIMONAgent.exe\n')
archive=shutil.make_archive(str(ROOT/'release'/'SIMONAgent-template'),'zip',release)
print('Template agent (belum termasuk public CA kantor):',archive)
