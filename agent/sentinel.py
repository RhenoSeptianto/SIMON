"""Read-only, bounded Hard Disk Sentinel XML reader. No drive scans or commands."""
import hashlib,os,re,time
from pathlib import Path
import xml.etree.ElementTree as ET

DEFAULT_XML=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'SIMON'/'HDSentinel.xml'
MAX_XML_BYTES=5*1024*1024

def number(text):
    if text is None:return None
    match=re.search(r'-?\d+(?:[.,]\d+)?',str(text))
    return float(match.group().replace(',','.')) if match else None

def parse_report(data):
    if len(data)>MAX_XML_BYTES:raise ValueError('XML terlalu besar (maksimal 5 MiB)')
    normalized=data.replace(b'\x00',b'').upper()
    if b'<!DOCTYPE' in normalized or b'<!ENTITY' in normalized:raise ValueError('DTD/entity XML tidak diizinkan')
    root=ET.fromstring(data)
    if root.tag!='Hard_Disk_Sentinel':raise ValueError('Bukan laporan Hard Disk Sentinel')
    disks=[];identities=set()
    for disk in root:
        if not disk.tag.startswith('Physical_Disk_Information_Disk_'):continue
        summary=disk.find('Hard_Disk_Summary')
        if summary is None:continue
        text=lambda key:summary.findtext(key,default='').strip()
        serial=text('Hard_Disk_Serial_Number') or None
        model=text('Hard_Disk_Model_ID') or None
        location=text('Disk_Location')
        if not serial and not (model and location):raise ValueError('Disk tidak memiliki serial atau identitas lokasi yang jelas')
        identity='sentinel:'+serial.upper() if serial else 'sentinel-location:'+hashlib.sha256((model+'|'+location).encode()).hexdigest()
        if identity in identities:raise ValueError('Identitas disk duplikat pada laporan')
        identities.add(identity)
        health=number(text('Health'));performance=number(text('Performance'))
        health=health if health is not None and 0<=health<=100 else None
        performance=performance if performance is not None and 0<=performance<=100 else None
        sectors=number(disk.findtext('.//Total_Sectors'));sector_size=number(disk.findtext('.//Bytes_Per_Sector'))
        capacity=int(sectors*sector_size) if sectors and sector_size else None
        power=text('Power_on_time');days=re.search(r'(\d+)\s*days?',power,re.I);hours=re.search(r'(\d+)\s*hours?',power,re.I)
        power_hours=(int(days.group(1))*24 if days else 0)+(int(hours.group(1)) if hours else 0) if days or hours else None
        description=text('Description')
        media='SSD' if text('SSD_Controller') or 'solid state' in description.lower() else ('HDD' if 'hard disk' in description.lower() else None)
        disks.append({'disk_identity':identity,'model':model,'serial_number':serial,'media_type':media,'bus_type':text('Interface') or None,'capacity_bytes':capacity,'temperature_c':number(text('Current_Temperature')),'health_percent':health,'performance_percent':performance,'health_status':'Reported' if health is not None else 'Unknown','wear_percent':None,'power_on_hours':power_hours,'sentinel_description':description[:1500],'sentinel_tip':text('Tip')[:500],'power_state':text('Power_State') or None,'estimated_remaining_lifetime':text('Estimated_remaining_lifetime') or None,'source':'sentinel'})
    if not disks:raise ValueError('Laporan tidak memiliki physical disk yang dapat diidentifikasi')
    return {'disks':disks,'storage_source':'sentinel','sentinel_report_time':root.findtext('./General_Information/Application_Information/Current_Date_And_Time') or None}

class SentinelWatcher:
    def __init__(self,path=DEFAULT_XML,stale_seconds=120):
        self.path=Path(path);self.stale_seconds=stale_seconds;self.signature=None;self.digest=None;self.last_status=None
    def _status(self,status,message):
        key=(status,message)
        if key==self.last_status:return None
        self.last_status=key
        return {'storage_source':'sentinel','sentinel_status':status,'sentinel_message':message}
    def read_update(self,now=None):
        now=time.time() if now is None else now
        try:
            before=self.path.stat();signature=(before.st_mtime_ns,before.st_size)
            if before.st_size>MAX_XML_BYTES:raise ValueError('XML terlalu besar (maksimal 5 MiB)')
            stale=now-before.st_mtime>self.stale_seconds
            if signature==self.signature and self.last_status and self.last_status[0] in ('fresh','stale'):
                if stale:return self._status('stale','XML Sentinel belum diperbarui lebih dari 2 menit')
                if self.last_status[0]=='fresh':return None
            data=self.path.read_bytes()
            after=self.path.stat()
            if (after.st_mtime_ns,after.st_size)!=signature:return self._status('waiting','XML sedang diperbarui; menunggu file lengkap')
            payload=parse_report(data)
            digest=hashlib.sha256(data).hexdigest()
            self.signature=signature
            status='stale' if stale else 'fresh'
            if digest==self.digest and self.last_status and self.last_status[0]==status:return None
            self.digest=digest;self.last_status=(status,'')
            payload.update({'sentinel_status':status,'sentinel_message':'XML Sentinel belum diperbarui lebih dari 2 menit' if stale else '', 'sentinel_file_updated_at':after.st_mtime})
            return payload
        except FileNotFoundError:return self._status('missing','HDSentinel.xml belum ditemukan')
        except (OSError,ET.ParseError,ValueError,LookupError) as error:return self._status('error',f'XML belum bisa dibaca: {error}')
