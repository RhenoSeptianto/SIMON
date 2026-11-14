"""Configuration for source and standalone agent. Never disables certificate validation."""
import json, os, ssl, sys
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_SERVER='https://172.18.123.92:8443'
DEFAULT_CONFIG=Path(os.getenv('PROGRAMDATA',str(Path.home())))/'SIMON'/'config.json'

def _readable_file(path):
    try:
        if not path.is_file(): return False
        with path.open('rb') as handle: handle.read(1)
        return True
    except OSError:
        return False

def service_config(executable=None):
    exe_dir=Path(executable or sys.executable).resolve().parent
    candidates=[exe_dir/'config.json',exe_dir.parent/'config.json',DEFAULT_CONFIG]
    local_app=os.getenv('LOCALAPPDATA')
    if local_app: candidates.append(Path(local_app)/'SIMON'/'config.json')
    for candidate in candidates:
        if _readable_file(candidate): return candidate
    return DEFAULT_CONFIG

def default_ca_file(executable=None):
    exe_dir=Path(executable or sys.executable).resolve().parent
    candidates=[exe_dir/'ca.crt',exe_dir.parent/'ca.crt']
    local_app=os.getenv('LOCALAPPDATA')
    if local_app: candidates.append(Path(local_app)/'SIMON'/'ca.crt')
    candidates.append(DEFAULT_CONFIG.parent/'ca.crt')
    for candidate in candidates:
        if _readable_file(candidate): return str(candidate)
    return None

def load_config(path=None):
    target=Path(path) if path else (service_config() if getattr(sys,'frozen',False) else DEFAULT_CONFIG)
    if not target.exists():
        if path: raise ValueError(f'Config tidak ditemukan: {target}')
        return {}
    result=json.loads(target.read_text(encoding='utf-8-sig'))
    if not isinstance(result,dict): raise ValueError('Config harus berupa JSON object')
    for key in ('ca_file','state','sentinel_xml'):
        if result.get(key) and not Path(result[key]).is_absolute(): result[key]=str(target.parent/result[key])
    return result

def validate_server(url):
    parsed=urlsplit(url)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('URL server tidak valid')
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1','::1')):
        raise ValueError('HTTPS wajib selain loopback development')
    return url.rstrip('/')

def tls_context(ca_file=None):
    return ssl.create_default_context(cafile=ca_file) if ca_file else None
