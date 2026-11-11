"""Install stable updater files/config. Task registration is handled by the admin PowerShell wrapper."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from tools.update_worker import read_json,write_json,git,extract_commit,assert_repo

def install(root,data,git_path,task_state,database_url_file=None):
 root=Path(root).resolve();data=Path(data).resolve();folder=data/'updater';folder.mkdir(parents=True,exist_ok=True)
 if not (root/'.git').exists():raise RuntimeError('Folder sumber bukan checkout Git. Clone repo SIMON terlebih dahulu.')
 if database_url_file:
  database_url_file=Path(database_url_file).resolve()
  if not database_url_file.is_file():raise RuntimeError('File koneksi PostgreSQL tidak ditemukan: '+str(database_url_file))
  raw=database_url_file.read_text(encoding='utf-8-sig').strip()
 else:
  if not (data/'siams.db').exists():raise RuntimeError('Database server belum ada. Jalankan setup-server.bat terlebih dahulu.')
  raw='sqlite:///'+str(data/'siams.db')
 from backend.database import database_descriptor
 descriptor=database_descriptor(raw)
 if (folder/'request.json').exists() or (folder/'maintenance.json').exists():raise RuntimeError('Update/pemulihan sedang berlangsung; jangan memasang helper ulang.')
 config={'repo':str(root),'data':str(data),'database':descriptor.get('path'),'database_kind':descriptor['kind'],'database_id':descriptor['id'],'database_url_file':str(database_url_file) if database_url_file else None,'folder':str(folder),'git':str(Path(git_path).resolve()),'bootstrap_python':sys.executable,'health_url':'https://127.0.0.1:8443/api/health'}
 if descriptor['kind'].startswith('postgresql'):
  from tools.postgres_tools import find_program
  config.update(pg_dump=find_program('pg_dump'),pg_restore=find_program('pg_restore'))
 assert_repo(config)
 remote=git(config,'remote','get-url','origin')
 if remote.rstrip('/').removesuffix('.git').casefold()!='https://github.com/rhenoseptianto/simon':raise RuntimeError('Remote Git bukan repo SIMON yang disepakati.')
 shutil.copy2(root/'tools'/'update_worker.py',folder/'worker.py')
 shutil.copy2(root/'deployment'/'server'/'update-task-control.ps1',folder/'task-control.ps1')
 write_json(folder/'config.json',config)
 state=read_json(task_state)
 if not (folder/'current.json').exists():
  # Freeze the initial application too: later manual pulls cannot corrupt rollback source.
  sha=git(config,'rev-parse','HEAD');baseline=folder/'releases'/(sha[:12]+'-bootstrap')
  baseline.parent.mkdir(parents=True,exist_ok=True)
  if not baseline.exists():extract_commit(config,sha,baseline)
  database_args=['--database-url-file',str(database_url_file)] if database_url_file else ['--database',str(data/'siams.db')]
  arguments=subprocess.list2cmdline(['-m','backend.run_server','--data',str(data),*database_args,'--version',sha])
  write_json(folder/'current.json',{'sha':sha,'health_sha':sha,'root':str(baseline),'python':sys.executable,'arguments':arguments})
 else:
  current=read_json(folder/'current.json');current.update(root=state.get('root',current.get('root')),python=state.get('python',current.get('python')),arguments=state.get('arguments',current.get('arguments')));write_json(folder/'current.json',current)
 print('Helper siap:',folder)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--data',required=True);p.add_argument('--git',required=True);p.add_argument('--task-state',required=True);p.add_argument('--database-url-file');a=p.parse_args()
 install(a.root,a.data,a.git,a.task_state,a.database_url_file)
