"""Bounded HTTPS check with complete errors on stdout for Windows PowerShell 5.1."""
import argparse,ssl,time,urllib.request,json,hashlib,os
from pathlib import Path

def check_https(ca,url,attempts=20,delay=1,timeout=2,expected_version=None,expected_database=None):
    try: context=ssl.create_default_context(cafile=ca)
    except (OSError,ssl.SSLError) as error:
        print(f'HEALTH_CHECK_FAILED: CA {ca}: {type(error).__name__}: {error}',flush=True)
        return 1
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url,context=context,timeout=timeout) as response:
                if response.status!=200:raise RuntimeError(f'HTTP {response.status}')
                if expected_version is not None or expected_database is not None:
                    payload=json.load(response)
                    if not payload.get('ok'):raise RuntimeError('Server belum siap')
                    if expected_version is not None and payload.get('version')!=expected_version:raise RuntimeError('Versi server tidak sesuai snapshot yang dipasang')
                    if expected_database is not None:
                        identifier=hashlib.sha256(os.path.normcase(str(Path(expected_database).resolve())).encode()).hexdigest()
                        if payload.get('database_kind')!='sqlite' or payload.get('database_id')!=identifier:raise RuntimeError('Database server aktif berbeda dari database helper. Konfigurasi server tidak diubah.')
                print(f'HTTPS OK: HTTP {response.status}',flush=True)
                return 0
        except Exception as error:
            if attempt==attempts-1:
                print(f'HEALTH_CHECK_FAILED: {url}: {type(error).__name__}: {error}',flush=True)
                return 1
            time.sleep(delay)
    return 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ca',required=True);parser.add_argument('--url',required=True);parser.add_argument('--expected-version');parser.add_argument('--expected-database')
    args=parser.parse_args()
    raise SystemExit(check_https(args.ca,args.url,expected_version=args.expected_version,expected_database=args.expected_database))
