"""Attach ONLY office public CA to the built template. No private keys/data export."""
from pathlib import Path
import shutil,zipfile,datetime,json,hashlib
ROOT=Path(__file__).resolve().parents[1]

def make_package(root=ROOT):
 root=Path(root)
 ca=root/'data'/'tls'/'ca.crt'
 if not ca.exists():raise RuntimeError('Jalankan setup-server.bat pada PC kantor terlebih dahulu')
 template=root/'release'/'SIMONAgent-template.zip'
 if not template.exists():raise RuntimeError('Letakkan SIMONAgent-template.zip hasil build/GitHub Actions di release/')
 target=root/'release'/('office-agent-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'));target.mkdir(parents=True)
 with zipfile.ZipFile(template) as archive:
  for member in archive.infolist():
   path=(target/member.filename).resolve()
   if not path.is_relative_to(target.resolve()):raise RuntimeError('Unsafe archive path')
  archive.extractall(target)
 if not (target/'SIMONAgent'/'SIMONAgent.exe').exists():raise RuntimeError('Template tidak lengkap')
 manifest=target/'agent-build.json'
 if not manifest.exists() or not {'sentinel_xml','store_code','reenrollment_after_delete','ten_second_metrics','in_place_install','native_user_startup'}.issubset(json.loads(manifest.read_text(encoding='utf-8')) .get('capabilities',[])):
  raise RuntimeError('Template agent lama. Build ulang lewat tools/build-agent.bat atau download artifact GitHub terbaru untuk Startup native EXE tanpa PowerShell (manifest 6/native_user_startup).')
 metadata=json.loads(manifest.read_text(encoding='utf-8'))
 if metadata.get('exe_sha256')!=hashlib.sha256((target/'SIMONAgent'/'SIMONAgent.exe').read_bytes()).hexdigest():raise RuntimeError('Checksum executable template tidak sesuai manifest')

 # Refresh installer scripts from this checkout even when the EXE template is older.
 installers=root/'deployment'/'agent'
 if installers.is_dir():
  for file in installers.iterdir():
   if file.is_file() and file.suffix.lower() in ('.ps1','.bat','.md'):shutil.copy2(file,target/file.name)
 shutil.copy2(ca,target/'ca.crt')
 if any(target.rglob('*.key')) or any(target.rglob('identity.json')) or any(target.rglob('*.db')):raise RuntimeError('Paket mengandung data privat yang tidak boleh dibagikan')
 archive=shutil.make_archive(str(root/'release'/'SIMONAgent-store'),'zip',target)
 return Path(archive)

if __name__=='__main__':print('Paket siap disebar:',make_package())
