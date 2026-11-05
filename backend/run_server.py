"""Office HTTPS server runner, used by Windows Task Scheduler."""
import os,logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
ROOT=Path(__file__).resolve().parents[1]
os.environ['SIAMS_PRODUCTION']='1'

def main():
 import uvicorn
 data=Path(os.getenv('SIAMS_DATA',str(ROOT/'data')))
 tls=data/'tls'
 for name in ('server.key','server.crt'):
  if not (tls/name).exists():raise SystemExit('Jalankan deployment/server/setup-server.bat terlebih dahulu')
 logs=data/'logs';logs.mkdir(parents=True,exist_ok=True)
 handler=RotatingFileHandler(logs/'server.log',maxBytes=5242880,backupCount=3,encoding='utf8')
 handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
 for name in ('uvicorn','uvicorn.error','uvicorn.access'):
  logger=logging.getLogger(name);logger.handlers=[handler];logger.propagate=False;logger.setLevel(logging.INFO)
 uvicorn.run('backend.main:app',host='0.0.0.0',port=8443,ssl_keyfile=str(tls/'server.key'),ssl_certfile=str(tls/'server.crt'),log_config=None,proxy_headers=False)
if __name__=='__main__':main()
