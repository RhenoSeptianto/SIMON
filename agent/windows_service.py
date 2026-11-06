"""Run from its permanent package folder; worker only collects locally and sends outbound HTTPS."""
import os, sys, subprocess
from pathlib import Path
from agent.config import service_config,load_config
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
        config=service_config(executable)
        settings=load_config(config)
        log_dir=Path(settings['state']);log_dir.mkdir(parents=True,exist_ok=True)
        output=log_dir/'service-worker.log'
        if output.exists() and output.stat().st_size>1048576:
            output.replace(log_dir/'service-worker.previous.log')
        # Capture startup/config/import errors that occur before agent.log exists.
        with output.open('ab',buffering=0) as stream:
            self.worker=subprocess.Popen([str(executable),'--config',str(config)],cwd=executable.parent,env={**os.environ,'SIAMS_WORKER_CAPTURE':'1'},stdout=stream,stderr=subprocess.STDOUT,creationflags=0x08000000)

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
