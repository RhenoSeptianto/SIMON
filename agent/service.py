"""Optional Windows service wrapper; install pywin32 first."""
import sys,subprocess
from pathlib import Path
import win32serviceutil,win32service,win32event
class SIAMSService(win32serviceutil.ServiceFramework):
 _svc_name_='SIAMSAgent'; _svc_display_name_='SIMON Hardware Agent'
 _svc_description_='Read-only outbound hardware monitoring agent'
 def __init__(self,args):
  super().__init__(args); self.stop_event=win32event.CreateEvent(None,0,0,None); self.child=None
 def SvcStop(self):
  self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING); win32event.SetEvent(self.stop_event)
 def SvcDoRun(self):
  root=Path(__file__).resolve().parents[1]
  self.child=subprocess.Popen([str(root/'.venv'/'Scripts'/'python.exe'),'-m','agent.main'],cwd=root,creationflags=0x08000000)
  while win32event.WaitForSingleObject(self.stop_event,1000)==win32event.WAIT_TIMEOUT:
   if self.child.poll() is not None: raise RuntimeError('Agent exited unexpectedly')
  self.child.terminate(); self.child.wait(timeout=20)
if __name__=='__main__': win32serviceutil.HandleCommandLine(SIAMSService)
