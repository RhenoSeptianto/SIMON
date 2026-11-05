"""Installed under Program Files; worker only collects locally and sends outbound HTTPS."""
import os, sys, subprocess
from pathlib import Path
import servicemanager,win32event,win32service,win32serviceutil

class SIMONService(win32serviceutil.ServiceFramework):
    _svc_name_='SIMONAgent'
    _svc_display_name_='SIMON Hardware Agent'
    _svc_description_='Read-only hardware monitoring. Outbound HTTPS only.'
    def __init__(self,args):
        super().__init__(args)
        self.stop_event=win32event.CreateEvent(None,0,0,None)
        self.worker=None
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING,waitHint=20000)
        win32event.SetEvent(self.stop_event)
    def SvcDoRun(self):
        executable=Path(sys.executable)
        config=Path(os.environ['PROGRAMDATA'])/'SIMON'/'config.json'
        self.worker=subprocess.Popen([str(executable),'--config',str(config)],cwd=executable.parent,creationflags=0x08000000)
        servicemanager.LogInfoMsg('SIMONAgent started')
        while win32event.WaitForSingleObject(self.stop_event,1000)==win32event.WAIT_TIMEOUT:
            if self.worker.poll() is not None:
                self.ReportServiceStatus(win32service.SERVICE_STOPPED,win32ExitCode=1066,svcExitCode=1)
                raise RuntimeError('SIMON worker exited; SCM recovery can restart service')
        # Queue commits are atomic; stopping never changes device identity.
        self.worker.terminate()
        self.worker.wait(timeout=15)
        servicemanager.LogInfoMsg('SIMONAgent stopped')

def dispatch():
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(SIMONService)
    servicemanager.StartServiceCtrlDispatcher()
