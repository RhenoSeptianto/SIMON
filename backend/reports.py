"""Excel-only inventory export, one physical disk/volume per row, localized labels."""
import io,math
from datetime import datetime,timedelta,timezone
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from backend.localization import localize_disk,report_datetime

WIB=timezone(timedelta(hours=7))
MISSING='Tidak tersedia'

def numeric(value):
    if value is None or isinstance(value,bool):return None
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):return None

def gibibytes(value):
    value=numeric(value)
    return value/1073741824 if value is not None else None

def local_time(value):
    value=numeric(value)
    if value is None or value<=0:return None
    try:return datetime.fromtimestamp(value,WIB).replace(tzinfo=None)
    except (ValueError,OverflowError,OSError):return None

def xml_status(value):
    return {'fresh':'Terbaru','stale':'Belum diperbarui','missing':'XML belum ditemukan','error':'XML belum bisa dibaca','waiting':'Menunggu penulisan XML'}.get(value,MISSING)

def write_sheet(workbook,name,headers,rows,widths,table_name):
    sheet=workbook.create_sheet(name)
    sheet.append(headers);sheet.freeze_panes='A2';sheet.sheet_view.showGridLines=False
    sheet.row_dimensions[1].height=34
    for cell in sheet[1]:
        cell.fill=PatternFill('solid',fgColor='145D59');cell.font=Font(name='Calibri',size=11,color='FFFFFF',bold=True)
        cell.alignment=Alignment(vertical='center',wrap_text=True)
    for row in rows:
        sheet.append([MISSING if value is None or value=='' else ILLEGAL_CHARACTERS_RE.sub('',value)[:32767] if isinstance(value,str) else value for value in row])
        line_count=1
        for index,cell in enumerate(sheet[sheet.max_row]):
            cell.font=Font(name='Calibri',size=11,color='243447')
            cell.alignment=Alignment(vertical='top',wrap_text=True)
            if isinstance(cell.value,str):
                cell.value=ILLEGAL_CHARACTERS_RE.sub('',cell.value)[:32767]
                cell.data_type='s'  # Preserve leading zeros and never execute untrusted formulas.
                line_count=max(line_count,math.ceil(len(cell.value)/widths[index]))
            elif isinstance(cell.value,datetime):cell.number_format='dd/mm/yyyy hh:mm:ss'
            elif isinstance(cell.value,(int,float)):cell.number_format='0.00'
        sheet.row_dimensions[sheet.max_row].height=max(25,min(180,15*line_count+10))
    for index,width in enumerate(widths,1):sheet.column_dimensions[sheet.cell(1,index).column_letter].width=width
    sheet.auto_filter.ref=sheet.dimensions
    if sheet.max_row>1:
        table=Table(displayName=table_name,ref=sheet.dimensions)
        table.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False)
        sheet.add_table(table)
    sheet.print_title_rows='1:1';sheet.sheet_properties.pageSetUpPr.fitToPage=True
    sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A4;sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0
    return sheet

def inventory_workbook(devices,serialize):
    devices=sorted(devices,key=lambda d:((d.store_code or '').casefold(),(d.hostname or '').casefold()))
    pc_rows=[];disk_rows=[];volume_rows=[]
    for device in devices:
        data=serialize(device);metrics=data['metrics'];inventory=data['inventory']
        prefix=[data.get('store_code'),data['hostname'],data['ip']]
        pc_rows.append(prefix+[data['serial'],inventory.get('os_name'),inventory.get('cpu'),numeric(metrics.get('cpu_usage')),gibibytes(metrics.get('ram_total')),numeric(metrics.get('ram_percent')),'Online' if data['online'] else 'Offline',local_time(data['last_seen'])])
        for raw_disk in metrics.get('disks',[]):
            disk=localize_disk(raw_disk)
            disk_rows.append(prefix+[disk.get('model'),disk.get('serial_number'),disk.get('media_type'),disk.get('bus_type'),gibibytes(disk.get('capacity_bytes')),numeric(disk.get('health_percent')),numeric(disk.get('performance_percent')),numeric(disk.get('temperature_c')),numeric(disk.get('power_on_hours')),disk.get('estimated_remaining_lifetime_id'),disk.get('power_state_id'),disk.get('sentinel_description_id'),disk.get('sentinel_tip_id'),report_datetime(metrics.get('sentinel_report_time')),xml_status(metrics.get('sentinel_status'))])
        for volume in metrics.get('volumes',[]):
            total=numeric(volume.get('total_bytes'));used=numeric(volume.get('used_bytes'));free=numeric(volume.get('free_bytes'))
            if used is None and total is not None and free is not None:used=total-free
            used_percent=used/total*100 if total and used is not None else numeric(volume.get('used_percent'))
            free_percent=free/total*100 if total and free is not None else numeric(volume.get('free_percent'))
            volume_rows.append(prefix+[volume.get('drive_letter'),volume.get('filesystem'),gibibytes(total),gibibytes(used),gibibytes(free),used_percent,free_percent])
    workbook=Workbook();workbook.remove(workbook.active)
    workbook.properties.creator='SIMON';workbook.properties.title='Laporan Inventaris Perangkat'
    write_sheet(workbook,'Perangkat',['Kode Store','Nama PC','Alamat IP','Nomor Seri PC','Sistem Operasi','Prosesor','Penggunaan CPU (%)','Total RAM (GiB)','Penggunaan RAM (%)','Status Koneksi','Terakhir Terhubung (WIB)'],pc_rows,[16,24,20,24,38,46,22,20,22,18,28],'TabelPerangkat')
    write_sheet(workbook,'SSD-HDD',['Kode Store','Nama PC','Alamat IP','Model Disk','Nomor Seri Disk','Jenis Disk','Interface','Kapasitas (GiB)','Kesehatan (%)','Performa (%)','Suhu ('+chr(176)+'C)','Total Jam Pemakaian','Perkiraan Sisa Umur','Status Pemantauan','Keterangan Sentinel','Saran Sentinel','Waktu Laporan Sentinel','Status XML'],disk_rows,[16,24,20,38,30,16,28,20,18,18,16,24,28,48,70,52,28,24],'TabelDisk')
    write_sheet(workbook,'Kapasitas Drive',['Kode Store','Nama PC','Alamat IP','Drive','File System','Total (GiB)','Terpakai (GiB)','Tersisa (GiB)','Terpakai (%)','Tersisa (%)'],volume_rows,[16,24,20,14,18,20,20,20,20,20],'TabelDrive')
    output=io.BytesIO();workbook.save(output);workbook.close();output.seek(0)
    filename='SIMON-Inventaris-'+datetime.now(WIB).strftime('%Y-%m-%d')+'.xlsx'
    return output,filename
