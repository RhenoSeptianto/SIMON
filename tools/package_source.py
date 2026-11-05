"""Produce GitHub-ready source archive by allowlist; never copies runtime data."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
DIRECTORIES=('agent','backend','frontend','docs','tests','tools','deployment','.github')
TOP_FILES=('.gitignore','README.md','requirements.txt','requirements-dev.txt','setup.ps1','start.ps1')
SUFFIXES={'.py','.ps1','.bat','.md','.txt','.html','.css','.js','.yml','.yaml'}

def source_files(root=ROOT):
 root=Path(root).resolve()
 for name in TOP_FILES:
  p=root/name
  if p.is_file():yield p
 for directory in DIRECTORIES:
  for p in (root/directory).rglob('*'):
   if p.is_file() and p.suffix.lower() in SUFFIXES and '__pycache__' not in p.parts and p.resolve().is_relative_to(root):yield p

def package_source(root=ROOT):
 root=Path(root);release=root/'release';release.mkdir(exist_ok=True)
 target=release/'SIMON-source.zip'
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
  for file in source_files(root):archive.write(file,file.relative_to(root).as_posix())
 return target
if __name__=='__main__':print(package_source())
