"""Attach ONLY office public CA to the built template. No private keys/data export."""
from pathlib import Path
import shutil,zipfile,json,hashlib,tempfile
ROOT=Path(__file__).resolve().parents[1]
REQUIRED_CAPABILITIES={'sentinel_xml','store_code','reenrollment_after_delete','ten_second_metrics','in_place_install','native_user_startup','machine_single_instance','unique_store_code','machine_bound_identity','agent_build_identity'}

def make_package(root=ROOT,template_path=None,ca_path=None,output_path=None):
 root=Path(root)
 ca=Path(ca_path) if ca_path else root/'data'/'tls'/'ca.crt'
 if not ca.exists():raise RuntimeError('Jalankan setup-server.bat pada PC kantor terlebih dahulu')
 template=Path(template_path) if template_path else root/'release'/'SIMONAgent-template.zip'
 if not template.exists():raise RuntimeError('Letakkan SIMONAgent-template.zip hasil build/GitHub Actions di release/')
 output=Path(output_path) if output_path else root/'release'/'SIMONAgent-store.zip';output.parent.mkdir(parents=True,exist_ok=True)
 target=Path(tempfile.mkdtemp(prefix='simon-agent-package-',dir=output.parent))
 try:
  with zipfile.ZipFile(template) as archive:
   for member in archive.infolist():
    path=(target/member.filename).resolve()
    if not path.is_relative_to(target.resolve()):raise RuntimeError('Unsafe archive path')
   archive.extractall(target)
  exe=target/'SIMONAgent'/'SIMONAgent.exe'
  if not exe.exists():raise RuntimeError('Template tidak lengkap')
  manifest=target/'agent-build.json'
  metadata=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
  if not REQUIRED_CAPABILITIES.issubset(metadata.get('capabilities',[])):raise RuntimeError('Template agent lama. Build ulang lewat tools/build-agent.bat atau ambil artifact GitHub terbaru (manifest 10/agent_build_identity).')
  if metadata.get('exe_sha256')!=hashlib.sha256(exe.read_bytes()).hexdigest():raise RuntimeError('Checksum executable template tidak sesuai manifest')
  installers=root/'deployment'/'agent'
  if installers.is_dir():
   for file in installers.iterdir():
    if file.is_file() and file.suffix.lower() in ('.ps1','.bat','.md'):shutil.copy2(file,target/file.name)
  shutil.copy2(ca,target/'ca.crt')
  if any(target.rglob('*.key')) or any(target.rglob('identity.json')) or any(target.rglob('*.db')):raise RuntimeError('Paket mengandung data privat yang tidak boleh dibagikan')
  temporary=Path(shutil.make_archive(str(output.with_suffix(''))+'.tmp','zip',target))
  temporary.replace(output)
  return output
 finally:shutil.rmtree(target,ignore_errors=True)

if __name__=='__main__':print('Paket siap disebar:',make_package())
