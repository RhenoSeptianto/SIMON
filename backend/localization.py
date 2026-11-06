"""Offline Indonesian presentation of common Sentinel messages; raw source stays intact."""
import re
from datetime import datetime

MONTHS=('Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember')
UNKNOWN='Keterangan ini belum dikenali SIMON. Periksa laporan asli di Sentinel untuk rincian lengkap.'

def report_datetime(value):
    if not value:return None
    value=str(value).strip()
    for pattern in ('%m/%d/%Y %I:%M:%S %p','%m/%d/%Y %I:%M %p','%d/%m/%Y %H:%M:%S','%Y-%m-%d %H:%M:%S'):
        try:return datetime.strptime(value,pattern)
        except ValueError:pass
    return None

def report_time_id(value):
    dt=report_datetime(value)
    return f'{dt.day} {MONTHS[dt.month-1]} {dt.year}, {dt:%H.%M.%S}' if dt else 'Waktu laporan tidak tersedia'

def lifetime_id(value):
    if not value or str(value).strip().lower() in ('unknown','n/a','not available','-'):return 'Tidak tersedia'
    match=re.fullmatch(r'(more than|less than|approximately|about)?\s*([\d.,]+)\s*(days?|hours?|years?)',str(value).strip(),re.I)
    if not match:return 'Perkiraan belum tersedia dalam bahasa Indonesia'
    prefix={None:'','more than':'Lebih dari ','less than':'Kurang dari ','approximately':'Sekitar ','about':'Sekitar '}[match[1].lower() if match[1] else None]
    unit='hari' if match[3].lower().startswith('day') else 'jam' if match[3].lower().startswith('hour') else 'tahun'
    return prefix+match[2]+' '+unit

def power_state_id(value):
    if not value:return 'Tidak tersedia'
    text=' '.join(str(value).split())
    match=re.fullmatch(r'(Inactive \(without monitoring\)|Active|Inactive|Sleeping|Standby|Unknown)(?:\s*\(since (.+)\))?',text,re.I)
    if not match:return 'Status pemantauan belum dikenali; periksa Sentinel'
    state={'inactive (without monitoring)':'Tidak aktif (tanpa pemantauan)','active':'Aktif','inactive':'Tidak aktif','sleeping':'Dalam mode tidur','standby':'Siaga','unknown':'Tidak diketahui'}[match[1].lower()]
    return state+(' sejak '+report_time_id(match[2]) if match[2] else '')

ATTRIBUTES={
 'ssd life left':'Sisa umur SSD','ssd life remaining':'Sisa umur SSD',
 'available spare (percent)':'Cadangan tersedia (%)','percentage used':'Persentase pemakaian',
 'wear leveling count':'Jumlah pemerataan keausan','media wearout indicator':'Indikator keausan media',
 'remaining lifetime perc.':'Persentase sisa umur',
}

def attribute_id(value):
    parts=[]
    for item in value.split(','):
        item=item.strip().rstrip('.')
        match=re.fullmatch(r'(#\d+\s+)?(.+)',item)
        if not match:continue
        label=ATTRIBUTES.get(match[2].lower())
        # Attribute IDs/names are technical identifiers, preserved for matching Sentinel.
        parts.append((match[1] or '')+(label if label else match[2]))
    return ', '.join(parts)

def sentence_id(sentence):
    text=sentence.strip().rstrip('.!')
    normalized=text.lower()
    exact={
      'problematic or weak sectors were not found':'Tidak ditemukan sektor bermasalah atau lemah.',
      'the trim feature of the ssd is supported and enabled for optimal performance':'TRIM didukung dan aktif untuk mengoptimalkan performa SSD.',
      'the trim feature of the ssd is supported but disabled':'TRIM didukung, tetapi belum aktif.',
      'no actions needed':'Tidak perlu tindakan.',
      'no actions needed at this time':'Saat ini tidak perlu tindakan.',
      'the hard disk status is perfect':'Kondisi HDD sangat baik.',
      'problematic or weak sectors were not found and there are no spin up or data transfer errors':'Tidak ditemukan sektor bermasalah atau lemah, kesalahan putaran awal disk, maupun kesalahan transfer data.',
      'the drive found no problems during the self test':'Disk tidak menemukan masalah selama pengujian mandiri.',
      'it is recommended to backup immediately to prevent data loss':'Disarankan segera mencadangkan data untuk mencegah kehilangan data.',
      'backup immediately to prevent data loss':'Segera cadangkan data untuk mencegah kehilangan data.',
      'replace hard disk immediately':'Segera ganti disk.',
      'it is recommended to examine the log of the disk regularly':'Disarankan memeriksa log disk secara berkala.',
      'all new problems found will be logged there':'Semua masalah baru yang ditemukan akan dicatat di sana.',
      'the contents of these sectors were moved to the spare area':'Isi sektor tersebut sudah dipindahkan ke area cadangan.',
      'they may be remapped any time in the later use of the disk':'Sektor tersebut dapat dipetakan ulang saat disk digunakan selanjutnya.',
      'it is recommended to monitor the hard disk status continuously':'Disarankan memantau kondisi disk secara berkelanjutan.',
    }
    if normalized in exact:return exact[normalized],True
    match=re.fullmatch(r'The (?:status of the (solid state disk|hard disk)|hard disk status) is (PERFECT|EXCELLENT|GOOD|ACCEPTABLE|FAIR|POOR|WEAK|BAD|CRITICAL|FAILING|UNKNOWN)',text,re.I)
    if match:
        state={'perfect':'sangat baik','excellent':'sangat baik','good':'baik','acceptable':'cukup baik','fair':'cukup','poor':'buruk','weak':'lemah','bad':'buruk','critical':'kritis','failing':'mengalami kegagalan','unknown':'belum diketahui'}[match[2].lower()]
        return f"Kondisi {'SSD' if match[1] and match[1].lower()=='solid state disk' else 'HDD'} {state}.",True
    match=re.fullmatch(r'The health is determined by SSD specific S\.M\.A\.R\.T\. attribute\(s\):\s*(.+)',text,re.I)
    if match:return 'Nilai kesehatan dihitung berdasarkan atribut SMART khusus SSD: '+attribute_id(match[1])+'.',True
    rules=[
      (r'There (?:are|is) ([\d,]+) bad sectors? on the disk surface',lambda m:f'Terdapat {m[1]} sektor rusak pada permukaan disk.'),
      (r'There (?:are|is) ([\d,]+) weak sectors? found on the disk surface',lambda m:f'Ditemukan {m[1]} sektor lemah pada permukaan disk.'),
      (r'There (?:are|is) ([\d,]+) reallocated sectors?(?: on the disk surface)?',lambda m:f'Terdapat {m[1]} sektor yang sudah direalokasi.'),
      (r'Problems occurred between the communication of the disk and the host ([\d,]+) times?',lambda m:f'Terjadi masalah komunikasi antara disk dan komputer sebanyak {m[1]} kali.'),
      (r'There were ([\d,]+) errors? (?:occurred )?during data transfer',lambda m:f'Terjadi {m[1]} kesalahan saat transfer data.'),
    ]
    for pattern,translate in rules:
        match=re.fullmatch(pattern,text,re.I)
        if match:return translate(match),True
    return UNKNOWN,False

def message_id(value):
    if not value:return 'Tidak tersedia',True
    text=' '.join(str(value).split())
    if text.lower() in ('n/a','unknown','not available','-'):return 'Tidak tersedia',True
    # Keep punctuation in the SMART identifier from being mistaken for sentences.
    protected=re.sub(r'S\.M\.A\.R\.T\.','__SMART__',text,flags=re.I)
    sentences=re.split(r'(?<=[.!?])\s+',protected)
    results=[];complete=True
    for sentence in sentences:
        translated,known=sentence_id(sentence.replace('__SMART__','S.M.A.R.T.'))
        complete=complete and known
        if translated not in results:results.append(translated)
    return ' '.join(results),complete

def localize_disk(disk):
    result=dict(disk)
    if disk.get('source')!='sentinel':return result
    result['sentinel_description_id'],description_ok=message_id(disk.get('sentinel_description'))
    result['sentinel_tip_id'],tip_ok=message_id(disk.get('sentinel_tip'))
    result['power_state_id']=power_state_id(disk.get('power_state'))
    result['estimated_remaining_lifetime_id']=lifetime_id(disk.get('estimated_remaining_lifetime'))
    result['sentinel_translation_complete']=description_ok and tip_ok
    return result

def localize_metrics(metrics):
    result=dict(metrics)
    result['disks']=[localize_disk(disk) for disk in metrics.get('disks',[])]
    if metrics.get('storage_source')=='sentinel':result['sentinel_report_time_id']=report_time_id(metrics.get('sentinel_report_time'))
    return result
