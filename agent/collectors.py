import json, socket, platform, subprocess, time, os
import psutil

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
  result.update(powershell('$b=Get-CimInstance Win32_BIOS; $s=Get-CimInstance Win32_ComputerSystem; $c=Get-CimInstance Win32_Processor | Select-Object -First 1; @{bios_serial=$b.SerialNumber;manufacturer=$s.Manufacturer;model=$s.Model;cpu=$c.Name} | ConvertTo-Json -Compress'))
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
