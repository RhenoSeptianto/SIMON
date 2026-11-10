import json, socket, platform, subprocess, time, os
import psutil

def registry_inventory():
 if os.name!='nt':return {}
 import winreg
 def values(path,names):
  try:
   with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,path) as key:
    result={}
    for target,source in names.items():
     try:value=str(winreg.QueryValueEx(key,source)[0]).strip()
     except OSError:continue
     if value:result[target]=value
    return result
  except OSError:return {}
 bios=values(r'HARDWARE\DESCRIPTION\System\BIOS',{'manufacturer':'SystemManufacturer','model':'SystemProductName','bios_serial':'SystemSerialNumber'})
 cpu=values(r'HARDWARE\DESCRIPTION\System\CentralProcessor\0',{'cpu':'ProcessorNameString'})
 windows=values(r'SOFTWARE\Microsoft\Windows NT\CurrentVersion',{'windows_product':'ProductName','windows_display':'DisplayVersion','windows_build':'CurrentBuildNumber'})
 if windows.get('windows_product'):
  parts=[windows.pop('windows_product'),windows.pop('windows_display',None)]
  build=windows.pop('windows_build',None)
  if build:parts.append('build '+build)
  windows['os_name']=' '.join(x for x in parts if x)
 return {**bios,**cpu,**windows}

def com_inventory():
 if os.name!='nt':return {}
 try:
  import win32com.client
  service=win32com.client.GetObject(r'winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2')
  result={}
  queries=(('SELECT Manufacturer,Model FROM Win32_ComputerSystem',{'manufacturer':'Manufacturer','model':'Model'}),('SELECT SerialNumber FROM Win32_BIOS',{'bios_serial':'SerialNumber'}),('SELECT Name FROM Win32_Processor',{'cpu':'Name'}))
  for query,fields in queries:
   try:item=next(iter(service.ExecQuery(query)),None)
   except Exception:continue
   if item is None:continue
   for target,source in fields.items():
    value=str(getattr(item,source,'') or '').strip()
    if value:result[target]=value
  return result
 except Exception:return {}

def powershell(script):
 if os.name!='nt': return {}
 p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=35,creationflags=0x08000000)
 if p.returncode: raise RuntimeError(p.stderr.strip()[:300])
 return json.loads(p.stdout.lstrip('\ufeff') or '{}')
def inventory():
 stats=psutil.net_if_stats()
 addresses=[a.address for name,values in psutil.net_if_addrs().items() if stats.get(name) and stats[name].isup for a in values if a.family==socket.AF_INET and not a.address.startswith(('127.','169.254.'))]
 result={'hostname':socket.gethostname(),'primary_ip':addresses[0] if addresses else '', 'ipv4':addresses,'os_name':platform.platform(),'architecture':platform.machine(),'agent_version':'0.1.0','cpu':platform.processor(),'physical_cores':psutil.cpu_count(logical=False),'logical_cores':psutil.cpu_count(),'last_boot':psutil.boot_time()}
 if os.name=='nt':
  # Some endpoint-security products allow interactive CIM but suppress stdout
  # when PowerShell is launched by a frozen EXE. Registry values keep inventory
  # available in that case; WMI COM also obtains BIOS serial without a child
  # PowerShell process. Non-empty CIM values remain the preferred result.
  result.update(registry_inventory())
  result.update(com_inventory())
  try:
   cim=powershell('$b=Get-CimInstance Win32_BIOS; $s=Get-CimInstance Win32_ComputerSystem; $c=Get-CimInstance Win32_Processor | Select-Object -First 1; ConvertTo-Json -Compress -InputObject @{bios_serial=$b.SerialNumber;manufacturer=$s.Manufacturer;model=$s.Model;cpu=$c.Name}')
   result.update({key:value for key,value in cim.items() if value is not None and str(value).strip()})
  except Exception:pass
 return result
def metrics():
 ram=psutil.virtual_memory(); volumes=[]
 for p in psutil.disk_partitions():
  try:
   u=psutil.disk_usage(p.mountpoint); volumes.append({'drive_letter':p.mountpoint,'total_bytes':u.total,'used_bytes':u.used,'free_bytes':u.free,'used_percent':u.percent,'free_percent':100-u.percent,'filesystem':p.fstype})
  except (OSError,PermissionError): pass
 return {'cpu_usage':psutil.cpu_percent(interval=0.2),'ram_total':ram.total,'ram_used':ram.used,'ram_available':ram.available,'ram_percent':ram.percent,'uptime_seconds':time.time()-psutil.boot_time(),'volumes':volumes}
def storage():
 if os.name!='nt': return {'disks':[]}
 disks=powershell('''$result=@(Get-PhysicalDisk | ForEach-Object {
 $d=$_; $r=$null; try {$r=$d | Get-StorageReliabilityCounter -ErrorAction Stop} catch {}
 [pscustomobject]@{disk_identity=[string]$d.UniqueId;model=$d.FriendlyName;serial_number=$d.SerialNumber;media_type=[string]$d.MediaType;bus_type=[string]$d.BusType;capacity_bytes=$d.Size;health_status=[string]$d.HealthStatus;temperature_c=$(if($r -and $r.Temperature -gt 0){$r.Temperature}else{$null});wear_percent=$(if($r){$r.Wear}else{$null});power_on_hours=$(if($r){$r.PowerOnHours}else{$null});read_errors_total=$(if($r){$r.ReadErrorsTotal}else{$null});write_errors_total=$(if($r){$r.WriteErrorsTotal}else{$null})}
 }); ConvertTo-Json -InputObject $result -Compress''')
 return {'disks':disks if isinstance(disks,list) else [disks]}
