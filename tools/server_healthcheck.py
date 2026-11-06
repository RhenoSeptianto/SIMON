"""Bounded HTTPS check with complete errors on stdout for Windows PowerShell 5.1."""
import argparse,ssl,time,urllib.request

def check_https(ca,url,attempts=20,delay=1,timeout=2):
    try: context=ssl.create_default_context(cafile=ca)
    except (OSError,ssl.SSLError) as error:
        print(f'HEALTH_CHECK_FAILED: CA {ca}: {type(error).__name__}: {error}',flush=True)
        return 1
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url,context=context,timeout=timeout) as response:
                if response.status!=200:raise RuntimeError(f'HTTP {response.status}')
                print(f'HTTPS OK: HTTP {response.status}',flush=True)
                return 0
        except Exception as error:
            if attempt==attempts-1:
                print(f'HEALTH_CHECK_FAILED: {url}: {type(error).__name__}: {error}',flush=True)
                return 1
            time.sleep(delay)
    return 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ca',required=True);parser.add_argument('--url',required=True)
    args=parser.parse_args()
    raise SystemExit(check_https(args.ca,args.url))
