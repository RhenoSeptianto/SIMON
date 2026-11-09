"""Install stable updater files/config. Task registration is handled by the admin PowerShell wrapper."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from tools.update_worker import read_json,write_json,git,extract_commit,assert_repo

def install(root,data,git_path,task_state):
 root=Path(root).resolve();data=Path(data).resolve();folder=data/'updater';folder.mkdir(parents=True,exist_ok=True)
 if not (root/'.git').exists():raise RuntimeError('Folder sumber bukan checkout Git. Clone repo SIMON terlebih dahulu.')
 if not (data/'siams.db').exists():raise RuntimeError('Database server belum ada. Jalankan setup-server.bat terlebih dahulu.')
 if (folder/'request.json').exists() or (folder/'maintenance.json').exists():raise RuntimeError('Update/pemulihan sedang berlangsung; jangan memasang helper ulang.')
 config={'repo':str(root),'data':str(data),'database':str(data/'siams.db'),'folder':str(folder),'git':str(Path(git_path).resolve()),'bootstrap_python':sys.executable,'health_url':'https://127.0.0.1:8443/api/health'}
 assert_repo(config)
 remote=git(config,'remote','get-url','origin')
 if remote.rstrip('/').removesuffix('.git').casefold()!='https://github.com/rhenoseptianto/simon':raise RuntimeError('Remote Git bukan repo SIMON yang disepakati.')
 shutil.copy2(root/'tools'/'update_worker.py',folder/'worker.py')
 shutil.copy2(root/'deployment'/'server'/'update-task-control.ps1',folder/'task-control.ps1')
 write_json(folder/'config.json',config)
 if not (folder/'current.json').exists():
  # Freeze the initial application too: later manual pulls cannot corrupt rollback source.
  sha=git(config,'rev-parse','HEAD');baseline=folder/'releases'/(sha[:12]+'-bootstrap')
  baseline.parent.mkdir(parents=True,exist_ok=True)
  if not baseline.exists():extract_commit(config,sha,baseline)
  arguments=subprocess.list2cmdline(['-m','backend.run_server','--data',str(data),'--database',str(data/'siams.db'),'--version',sha])
  write_json(folder/'current.json',{'sha':sha,'health_sha':sha,'root':str(baseline),'python':sys.executable,'arguments':arguments})
 print('Helper siap:',folder)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--data',required=True);p.add_argument('--git',required=True);p.add_argument('--task-state',required=True);a=p.parse_args()
 install(a.root,a.data,a.git,a.task_state)
