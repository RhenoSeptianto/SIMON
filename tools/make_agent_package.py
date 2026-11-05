"""Attach ONLY office public CA to the built template. No private keys/data export."""
from pathlib import Path
import shutil,zipfile,datetime
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
 shutil.copy2(ca,target/'ca.crt')
 if any(target.rglob('*.key')) or any(target.rglob('identity.json')) or any(target.rglob('*.db')):raise RuntimeError('Paket mengandung data privat yang tidak boleh dibagikan')
 archive=shutil.make_archive(str(root/'release'/'SIMONAgent-store'),'zip',target)
 return Path(archive)

if __name__=='__main__':print('Paket siap disebar:',make_package())
