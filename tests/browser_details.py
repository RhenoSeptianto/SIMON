"""Optional UI check: pip install playwright; uses installed Microsoft Edge."""
import os,tempfile,time,json,uuid,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['SIAMS_DATA']=tempfile.mkdtemp(prefix='siams-browser-')
from backend.main import DB,User,Device,Sample,password
from playwright.sync_api import sync_playwright,expect
import httpx
with DB() as s:
 s.add_all([User(name='QA Admin',username='qaadmin',password=password('1'),role='super_admin'),User(name='QA TS',username='qats',password=password('1'),role='ts')])
 d=Device(uuid=str(uuid.uuid4()),hostname='QA-PC',store_code='00115',ip='10.0.0.8',serial='QA-SERIAL',claim='unused',status='approved',last_seen=time.time(),inventory=json.dumps({'manufacturer':'QA','model':'Test PC','cpu':'Test CPU','os_name':'Windows test'}),metrics=json.dumps({'cpu_usage':24,'ram_percent':58,'ram_total':16*1073741824,'ram_used':9*1073741824,'metrics_at':time.time(),'storage_at':time.time(),'storage_source':'sentinel','sentinel_status':'fresh','sentinel_report_time':'11/6/2026 2:23:03 PM','sentinel_file_updated_at':time.time(),'volumes':[{'drive_letter':'C:','total_bytes':500*1073741824,'free_bytes':400*1073741824,'used_percent':20,'filesystem':'NTFS'},{'drive_letter':'D:','free_percent':15},{'drive_letter':'E:','free_percent':5}],'disks':[{'model':'QA SSD','capacity_bytes':500*1073741824,'health_status':'Reported','source':'sentinel','health_percent':95,'performance_percent':100,'temperature_c':44,'sentinel_tip':'No actions needed.','power_state':'Inactive (without monitoring) (since 11/6/2026 3:58:38 PM)','estimated_remaining_lifetime':'more than 414 days','sentinel_description':'The status of the solid state disk is PERFECT. Problematic or weak sectors were not found.'},{'model':'QA HDD','serial_number':'QA-HDD-2','source':'sentinel','health_percent':70,'performance_percent':100,'temperature_c':68}]}))
 s.add(d);s.flush();did=d.id
 for index in range(4):s.add(Sample(device_id=did,event_id=str(uuid.uuid4()),collected=time.time()-7200+index*300,payload=json.dumps({'cpu_usage':20+index,'ram_percent':50+index})))
 s.commit()
server=subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--port','8769','--no-access-log'],cwd=ROOT,env=os.environ.copy(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
 for _ in range(80):
  try:
   if httpx.get('http://127.0.0.1:8769/').status_code==200:break
  except httpx.HTTPError:pass
  time.sleep(.1)
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='msedge',headless=True)
  page=browser.new_page(viewport={'width':1280,'height':900})
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8769/')
  expect(page.locator('link[rel="icon"]')).to_have_attribute('href','/static/favicon.svg?v=1')
  assert httpx.get('http://127.0.0.1:8769/static/favicon.svg').status_code==200
  page.locator('[name=username]').fill('qaadmin');page.locator('[name=password]').fill('1');page.get_by_role('button',name='Masuk ke dashboard').click()
  expect(page.locator('#sidebarVersion')).to_have_text('SIMON v'+(ROOT/'VERSION').read_text().strip())
  expect(page.get_by_role('button',name='UpdateSimon',exact=True)).to_be_visible()
  expect(page.get_by_role('columnheader',name='Health Disk',exact=True)).to_be_visible()
  pc_row=page.locator('[data-device="'+str(did)+'"]').locator('xpath=ancestor::tr')
  expect(pc_row.locator('.disk-health-item')).to_have_count(2)
  expect(pc_row.locator('.disk-health-item').nth(0)).to_contain_text('95%')
  expect(pc_row.locator('.disk-health-item').nth(0)).to_have_class('disk-health-item disk-health-good')
  expect(pc_row.locator('.disk-health-item').nth(1)).to_contain_text('70%')
  expect(pc_row).to_have_class('device-health-critical')
  expect(pc_row.locator('.disk-health-item').nth(1)).to_have_class('disk-health-item disk-health-critical')
  expect(pc_row.locator('.disk-temperature-high')).to_have_text('Suhu 68 °C')
  expect(page.locator('#overviewDevices tbody tr').first.locator('[data-device]')).to_have_attribute('data-device',str(did))
  assert 'Belum tersedia' in page.evaluate("diskHealthCell({disks:[{source:'sentinel',health_percent:null}]})")
  assert '0%' in page.evaluate("diskHealthCell({disks:[{source:'sentinel',health_percent:0}]})")
  assert 'disk-health-critical' in page.evaluate("diskHealthCell({disks:[{source:'sentinel',health_percent:79.9}]})")
  assert 'disk-health-critical' not in page.evaluate("diskHealthCell({disks:[{source:'sentinel',health_percent:80}]})")
  assert '100%' not in page.evaluate("diskHealthCell({disks:[{source:'windows',health_percent:100,wear_percent:0}]})")
  assert 'disk-health-warning' in page.evaluate("diskHealthCell({disks:[{source:'sentinel',health_percent:85}]})")
  assert 'Data Sentinel tidak diperbarui' in page.evaluate("diskHealthCell({storage_source:'sentinel',sentinel_status:'stale',disks:[{source:'sentinel',health_percent:95}]})")
  assert page.evaluate("deviceNeedsAttention({online:false,metrics:{}})")
  assert page.evaluate("deviceNeedsAttention({online:true,metrics:{storage_source:'sentinel',sentinel_status:'stale'}})")
  assert page.evaluate("deviceNeedsAttention({online:true,metrics:{disks:[{temperature_c:66}]}})")
  assert page.evaluate("deviceNeedsAttention({online:true,metrics:{volumes:[{free_percent:9}]}})")
  assert not page.evaluate("deviceNeedsAttention({online:true,metrics:{storage_source:'sentinel',sentinel_status:'fresh',disks:[{source:'sentinel',health_percent:90,temperature_c:40}],volumes:[{free_percent:20}]}})")
  # Newly enrolled PCs appear without navigation/reload, even while schedule keeps focus.
  with DB() as s:
   for index in range(9):s.add(Device(uuid=str(uuid.uuid4()),hostname='AUTO-OLD-'+str(index),store_code='AUTO-'+str(index),ip='10.9.0.'+str(index),serial='AUTO-'+str(index),claim='unused',status='approved',last_seen=time.time()))
   s.commit()
  summary=page.locator('.monitoring-schedule summary');summary.click();summary.focus()
  response=httpx.post('http://127.0.0.1:8769/api/agent/enroll',json={'uuid':str(uuid.uuid4()),'claim':'new-agent-claim-'+'x'*40,'inventory':{'hostname':'AUTO-NEW-PC','store_code':'AUTO-NEW','primary_ip':'10.9.1.1'}})
  response.raise_for_status()
  expect(page.locator('#overviewDevices').get_by_text('AUTO-NEW-PC',exact=True)).to_be_visible(timeout=15000)
  expect(page.locator('#overviewCount')).to_have_text('8 terbaru dari 11 perangkat')
  expect(summary).to_be_focused()
  expect(page.locator('.monitoring-schedule')).to_have_attribute('open','')
  page.get_by_role('button',name='Devices',exact=True).click()
  search=page.get_by_label('Cari hostname atau IP');search.fill('AUTO-LIVE');search.focus()
  response=httpx.post('http://127.0.0.1:8769/api/agent/enroll',json={'uuid':str(uuid.uuid4()),'claim':'new-agent-claim-'+'z'*40,'inventory':{'hostname':'AUTO-LIVE-PC','store_code':'AUTO-LIVE','primary_ip':'10.9.1.2'}})
  response.raise_for_status()
  expect(page.get_by_text('AUTO-LIVE-PC',exact=True)).to_be_visible(timeout=15000)
  expect(search).to_have_value('AUTO-LIVE');expect(search).to_be_focused()
  search.fill('');page.get_by_label('Filter kondisi perangkat').select_option('1')
  expect(page.get_by_text('QA-PC',exact=True)).to_be_visible()
  expect(page.get_by_text('AUTO-LIVE-PC',exact=True)).to_have_count(0)
  page.get_by_label('Filter kondisi perangkat').select_option('')
  with DB() as s:s.query(Device).filter(Device.id!=did).delete(synchronize_session=False);s.commit()
  print('PASS: newly enrolled agents appear automatically on Overview/Devices; newest PC shown beyond first 8; schedule/search focus retained.')
  page.get_by_role('button',name='Overview',exact=True).click()
  with DB() as s:
   live=s.get(Device,did);values=json.loads(live.metrics);values['disks'][1]['health_percent']=69;live.metrics=json.dumps(values);s.commit()
  expect(page.locator('[data-device="'+str(did)+'"]').locator('xpath=ancestor::tr').locator('.disk-health-item').nth(1)).to_contain_text('69%',timeout=15000)
  print('PASS: separate Sentinel disk health values, warning color/order and live update; missing/zero/legacy/stale data handled; sidebar uses server version.')
  target=ROOT/'data'/'qa';target.mkdir(parents=True,exist_ok=True)
  for theme in ('light','dark'):
   page.evaluate("dark => document.body.classList.toggle('dark', dark)",theme=='dark')
   for section in ('Overview','Devices','Users','Alerts','Reports','Audit','Database','Updates'):
    page.get_by_role('button',name='Laporan' if section=='Reports' else 'UpdateSimon' if section=='Updates' else section,exact=True).click()
    expect(page.locator('#content h2')).to_have_text('Laporan' if section=='Reports' else 'UpdateSimon' if section=='Updates' else section)
    if section=='Updates':
     expect(page.get_by_role('heading',name='Update aplikasi SIMON')).to_be_visible()
     expect(page.get_by_role('button',name='Cek update',exact=True)).to_be_disabled()
     expect(page.get_by_text('Pemasangan awal diperlukan satu kali')).to_be_visible()
    if section=='Reports':
     expect(page.get_by_role('link',name='Unduh Excel')).to_be_visible()
     expect(page.locator('a[href="/api/reports/csv"]')).to_have_count(0)
     if theme=='light':
      with page.expect_download() as download_info:page.get_by_role('link',name='Unduh Excel').click()
      download=download_info.value
      assert download.suggested_filename.startswith('SIMON-Inventaris-') and download.suggested_filename.endswith('.xlsx')
      download.save_as(str(target/'laporan-qa.xlsx'))
      from openpyxl import load_workbook
      assert load_workbook(target/'laporan-qa.xlsx').sheetnames==['Perangkat','SSD-HDD','Kapasitas Drive']
    if section=='Alerts':
     expect(page.get_by_text('Belum ada peringatan',exact=True)).to_be_visible()
     assert 'Jalankan agent' not in page.locator('#content').inner_text()
    assert page.locator('main').evaluate('(e)=>e.getBoundingClientRect().bottom>=window.innerHeight-1')
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    if section in ('Alerts','Overview','Users','Updates'):
     page.screenshot(path=str(target/f'{section.lower()}-{theme}.png'),full_page=True)
   page.set_viewport_size({'width':390,'height':844})
   for section in ('Overview','Devices','Users','Alerts','Reports','Audit','Database','Updates'):
    page.get_by_role('button',name='Laporan' if section=='Reports' else 'UpdateSimon' if section=='Updates' else section,exact=True).click()
    expect(page.locator('#content h2')).to_have_text('Laporan' if section=='Reports' else 'UpdateSimon' if section=='Updates' else section)
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'),section
   page.screenshot(path=str(target/f'dashboard-mobile-{theme}.png'),full_page=True)
   page.set_viewport_size({'width':1280,'height':900})
  # Exercise the updater UI with a simulated helper, including a restart/disconnect and rollback.
  update_state={'ready':True,'version':'0.2.0','current':'a'*40,'check':{},'job':{'state':'idle','message':'Siap diperiksa'},'busy':False,'maintenance':False}
  progress_markup=page.evaluate("updateCard({ready:true,version:'0.2.2',current:'a'.repeat(40),check:{},job:{state:'installing',message:'Memasang',started_at:Date.now()/1000-12,updated_at:Date.now()/1000},busy:true,maintenance:false})")
  assert 'Update sedang berjalan' in progress_markup and 'Berjalan' in progress_markup and 'Pemasangan' in progress_markup
  disconnect=[False];update_success=[False]
  def updater_status(route):
   if disconnect[0]:
    disconnect[0]=False;route.abort();return
   route.fulfill(json=update_state)
  def updater_check(route):
   update_state['check']={'available':True,'latest':'b'*40,'latest_version':'0.3.0','changes':['b123456 Update tampilan']}
   route.fulfill(json=update_state['check'])
  def updater_start(route):
   assert route.request.post_data_json['target']=='b'*40
   disconnect[0]=True
   if update_success[0]:update_state.update(current='b'*40,version='0.3.0',busy=False,maintenance=False,job={'state':'success','message':'Update berhasil. Server sudah siap digunakan.'})
   else:update_state.update(busy=False,maintenance=False,job={'state':'rolled_back','message':'Update gagal, versi sebelumnya berhasil dipulihkan.','error':'Uji health check gagal'})
   route.fulfill(json={'job_id':'test-job'})
  page.route('**/api/system/update/status',updater_status)
  page.route('**/api/system/update/check',updater_check)
  page.route('**/api/system/update/start',updater_start)
  page.get_by_role('button',name='UpdateSimon',exact=True).click()
  expect(page.locator('.nav-update-available')).to_be_hidden()
  expect(page.get_by_role('button',name='Cek update',exact=True)).to_be_enabled()
  page.get_by_role('button',name='Cek update',exact=True).click()
  expect(page.locator('.nav-update-available')).to_be_visible()
  expect(page.get_by_role('button',name='Update sekarang',exact=True)).to_be_enabled()
  page.get_by_role('button',name='Update sekarang',exact=True).click()
  expect(page.get_by_text('Update gagal, versi sebelumnya berhasil dipulihkan.',exact=True)).to_be_visible(timeout=12000)
  expect(page.get_by_text('Versi lama dipulihkan',exact=True)).to_be_visible()
  page.screenshot(path=str(target/'updater-rollback.png'),full_page=True)
  update_success[0]=True
  with page.expect_navigation(timeout=15000,wait_until='domcontentloaded'):
   page.get_by_role('button',name='Update sekarang',exact=True).click()
  expect(page.get_by_text('Update berhasil. Server sudah siap digunakan.',exact=True)).to_be_visible(timeout=10000)
  expect(page.get_by_role('button',name='Update sekarang',exact=True)).to_be_disabled()
  expect(page.locator('.nav-update-available')).to_be_hidden()
  page.screenshot(path=str(target/'updater-success.png'),full_page=True)

  page.unroute('**/api/system/update/status',updater_status)
  page.unroute('**/api/system/update/check',updater_check)
  page.unroute('**/api/system/update/start',updater_start)
  print('PASS: updater setup notice, check/update controls, disconnect recovery, rollback and automatic reload after success; no real deployment triggered.')
  with DB() as s:
   from backend.main import Alert
   s.add(Alert(device_id=did,category='disk_free',message='QA storage alert'));s.commit()
  page.evaluate("refreshNavIndicators()")
  expect(page.locator('.nav-alert-count')).to_have_text('1')
  page.get_by_role('button',name='Alerts',exact=True).click()
  expect(page.locator('.nav-alert-count')).to_be_hidden()
  expect(page.get_by_text('QA storage alert')).to_be_visible()
  page.get_by_role('button',name='Acknowledge',exact=True).click()
  expect(page.get_by_text('Ditinjau',exact=True)).to_be_visible()
  page.get_by_role('button',name='Ganti tema',exact=True).click()
  assert page.evaluate("localStorage.getItem('theme')===document.body.className")
  page.get_by_role('button',name='Devices',exact=True).click()
  page.get_by_label('Cari hostname atau IP').fill('no-match')
  expect(page.get_by_text('Tidak ada perangkat yang ditampilkan')).to_be_visible()
  expect(page.locator('#next')).to_be_disabled()
  page.get_by_label('Cari hostname atau IP').fill('00115')
  expect(page.get_by_text('QA-PC',exact=True)).to_be_visible()
  page.get_by_text('QA-PC',exact=True).click()
  dialog=page.locator('dialog');expect(dialog).to_be_visible();expect(dialog.get_by_text('24%',exact=True)).to_be_visible()
  expect(dialog.locator('.monitoring-schedule')).to_have_count(0)
  expect(page.locator('#panel-overview').get_by_text('Tersisa 80%',exact=True)).to_be_visible()
  page.get_by_role('tab',name='Storage',exact=True).click();expect(dialog.get_by_text('QA SSD',exact=True)).to_be_visible();expect(dialog.get_by_text('Kesehatan 95%',exact=True)).to_be_visible();expect(dialog.get_by_text('100%',exact=True).first).to_be_visible();expect(dialog.get_by_text('Store 00115',exact=True)).to_be_visible();expect(dialog.get_by_text('44 \u00b0C',exact=True)).to_be_visible()
  dialog.locator('#physicalDisks summary').first.click()
  expect(dialog.get_by_text('Tidak perlu tindakan.',exact=True)).to_be_visible()
  expect(dialog.get_by_text('Lebih dari 414 hari',exact=True)).to_be_visible()
  expect(dialog.get_by_text('Tidak aktif (tanpa pemantauan) sejak 6 November 2026, 15.58.38',exact=True)).to_be_visible()
  assert 'The status of' not in dialog.inner_text()
  with DB() as s:
   live=s.get(Device,did);values=json.loads(live.metrics);values['disks'][0]['health_percent']=94;values['cpu_usage']=42;live.metrics=json.dumps(values);s.commit()
  expect(dialog.get_by_text('Kesehatan 94%',exact=True)).to_be_visible(timeout=15000)
  page.get_by_role('tab',name='Histori',exact=True).click();expect(page.locator('#historySlider')).to_be_visible()
  expect(page.locator('#historyTooltip')).to_contain_text('CPU 23%')
  page.locator('#historySlider').focus();page.keyboard.press('Home');expect(page.locator('#historyTooltip')).to_contain_text('CPU 20%')
  page.get_by_label('Periode histori').select_option('1');expect(page.get_by_text('Belum ada sampel pada periode ini')).to_be_visible()
  page.get_by_label('Periode histori').select_option('168');expect(page.locator('#historySVG')).to_be_visible()
  page.get_by_role('tab',name='Akses User',exact=True).click();expect(page.get_by_role('button',name='Revoke credential',exact=True)).to_have_count(0);page.get_by_label('Pilih user TS').select_option(label='QA TS (qats)');page.get_by_role('button',name='Assign',exact=True).click();expect(page.get_by_text('User berhasil diassign.')).to_be_visible()
  page.get_by_role('tab',name='Ringkasan',exact=True).click();expect(dialog.get_by_text('42%',exact=True)).to_be_visible();page.get_by_role('button',name='Refresh data',exact=True).click();expect(page.get_by_role('tab',name='Ringkasan')).to_have_attribute('aria-selected','true')
  page.evaluate("document.body.classList.add('dark')")
  target=ROOT/'data'/'qa';target.mkdir(parents=True,exist_ok=True)
  page.screenshot(path=str(target/'device-desktop.png'))
  page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(target/'device-mobile.png'))
  assert page.locator('dialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
  page.get_by_role('button',name='Tutup detail perangkat',exact=True).click();expect(dialog).not_to_be_visible()
  with DB() as s:
   s.add(Device(uuid=str(uuid.uuid4()),hostname='QA-OTHER-TS-PC',store_code='OTHER',ip='10.0.0.99',claim='unused',status='approved',last_seen=time.time()));s.commit()
  page.get_by_role('button',name='Overview',exact=True).click()
  expect(page.get_by_role('note',name='Cakupan perangkat')).to_contain_text('Semua perangkat')
  expect(page.get_by_text('QA-PC',exact=True)).to_be_visible()
  expect(page.get_by_text('QA-OTHER-TS-PC',exact=True)).to_be_visible()
  expect(page.locator('#overviewCount')).to_have_text('2 perangkat')
  page.get_by_role('button',name='Keluar',exact=True).click()
  page.locator('[name=username]').fill('qats');page.locator('[name=password]').fill('1');page.get_by_role('button',name='Masuk ke dashboard').click()
  expect(page.get_by_role('button',name='UpdateSimon',exact=True)).to_have_count(0)
  expect(page.get_by_role('note',name='Cakupan perangkat')).to_contain_text('Perangkat yang diassign ke QA TS')
  expect(page.locator('#overviewCount')).to_have_text('1 perangkat')
  expect(page.get_by_text('QA-OTHER-TS-PC',exact=True)).to_have_count(0)
  expect(page.get_by_text('Belum diassign',exact=True)).to_have_count(0)
  page.get_by_text('QA-PC',exact=True).click()
  expect(page.get_by_role('tab',name='Akses User',exact=True)).to_have_count(0)
  assert not errors,errors
  print('PASS: desktop/mobile, tabs, percentages, history tooltip/slider/period, refresh, assignment, TS authorization; no JavaScript errors.')
  browser.close()
finally:
 server.terminate();server.wait(timeout=15)
