"""Modular ADO (Asset & Delivery Order) backend with isolated ado_* tables."""
import base64, io, json, secrets, hmac, time
from datetime import datetime, timedelta, timezone
from html import escape
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, inspect, text
from sqlalchemy.orm import Session
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from backend.main import Base, engine, DB, User, db, now, digest, password, limit

WIB = timezone(timedelta(hours=7))
ROMAN_MONTHS = ('I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII')
ADO_ROLES = {'super_admin', 'admin_it', 'ts'}

DEFAULT_CATALOG_TREE = [
 ('PERANGKAT', 'Back Office', ['PC OFFICE', 'MONITOR OFFICE', 'UPS', 'PRINTER OFFICE']),
 ('PERANGKAT', 'Pos 1', ['PC POS', 'MONITOR POS', 'BARCODE SCANNER', 'PRINTER THERMAL', 'CASH DRAWER', 'UPS POS']),
 ('PERANGKAT', 'Pos 2', ['PC POS', 'MONITOR POS', 'BARCODE SCANNER', 'PRINTER THERMAL', 'CASH DRAWER', 'UPS POS']),
 ('PERANGKAT', 'Pos 3', ['PC POS', 'MONITOR POS', 'BARCODE SCANNER', 'PRINTER THERMAL', 'CASH DRAWER', 'UPS POS']),
 ('PERANGKAT', 'Kitchen', ['PC KITCHEN', 'MONITOR KITCHEN', 'PRINTER KITCHEN', 'UPS KITCHEN']),
 ('PERANGKAT', 'Drive Thru', ['PC DRIVE THRU', 'MONITOR DRIVE THRU', 'BARCODE SCANNER', 'PRINTER THERMAL']),
 ('CCTV_NETWORK', 'CCTV & Network', ['SWITCH DLINK', 'SWITCH TPLINK', 'ROUTER MIKROTIK', 'MODEM', 'ACCESS POINT', 'DVR / NVR CCTV', 'CAMERA CCTV']),
]


class AdoUser(Base):
 __tablename__ = 'ado_users'
 id = Column(Integer, primary_key=True)
 name = Column(String(160), nullable=False)
 username = Column(String(120), unique=True, nullable=False)
 password = Column(String(255), nullable=False)
 role = Column(String(40), default='ts', nullable=False)
 active = Column(Integer, default=1, nullable=False)
 signature_data = Column(Text, default='', nullable=False)


class AdoSession(Base):
 __tablename__ = 'ado_sessions'
 token = Column(String(128), primary_key=True)
 user_id = Column(Integer, ForeignKey('ado_users.id'), index=True)
 expires = Column(Float, index=True)


class AdoStore(Base):
 __tablename__ = 'ado_stores'
 id = Column(Integer, primary_key=True)
 store_code = Column(String(40), unique=True, nullable=False)
 name = Column(String(200), nullable=False)
 region = Column(String(60), default='Jabodetabek', nullable=False)
 store_type = Column(String(40), default='Existing Store', nullable=False)
 ts_user_id = Column(Integer, ForeignKey('ado_users.id'), nullable=True, index=True)
 created_at = Column(Float, default=now)


class AdoCatalog(Base):
 __tablename__ = 'ado_catalog'
 id = Column(Integer, primary_key=True)
 kind = Column(String(40), nullable=False, index=True)  # 'category' or 'device'
 group_type = Column(String(40), default='PERANGKAT', nullable=False)  # 'PERANGKAT' or 'CCTV_NETWORK'
 parent_category = Column(String(160), default='', nullable=False, index=True)
 name = Column(String(160), nullable=False)


class AdoAsset(Base):
 __tablename__ = 'ado_assets'
 id = Column(Integer, primary_key=True)
 store_id = Column(Integer, ForeignKey('ado_stores.id'), nullable=False, index=True)
 group_type = Column(String(40), default='PERANGKAT', nullable=False, index=True)
 category = Column(String(100), nullable=False)
 device_name = Column(String(160), nullable=False)
 brand = Column(String(120), default='', nullable=False)
 serial_number = Column(String(160), default='', nullable=False, index=True)
 purchase_year = Column(Integer, default=lambda: datetime.now(WIB).year, nullable=False)
 purchase_date = Column(String(20), default='', nullable=False)
 status = Column(String(40), default='normal', nullable=False)  # 'normal', 'perbaikan', 'rusak'
 notes = Column(Text, default='', nullable=False)
 do_id = Column(Integer, nullable=True)
 updated_at = Column(Float, default=now)


class AdoDeliveryOrder(Base):
 __tablename__ = 'ado_delivery_orders'
 id = Column(Integer, primary_key=True)
 do_number = Column(String(80), unique=True, nullable=False, index=True)
 store_type = Column(String(40), default='Existing Store', nullable=False)
 store_id = Column(Integer, ForeignKey('ado_stores.id'), nullable=False, index=True)
 ts_user_id = Column(Integer, nullable=True, index=True)
 ts_name = Column(String(160), default='', nullable=False)
 request_date = Column(Float, default=now, index=True)
 delivery_date = Column(String(40), default='', nullable=False)
 status = Column(String(40), default='pending', nullable=False, index=True)  # 'pending' or 'confirmed'
 confirmed_at = Column(Float, nullable=True)
 confirmed_by = Column(String(160), default='', nullable=False)
 approved_signature = Column(Text, default='', nullable=False)
 notes = Column(Text, default='', nullable=False)


class AdoDoItem(Base):
 __tablename__ = 'ado_do_items'
 id = Column(Integer, primary_key=True)
 do_id = Column(Integer, ForeignKey('ado_delivery_orders.id'), nullable=False, index=True)
 group_type = Column(String(40), default='PERANGKAT', nullable=False)
 category = Column(String(100), nullable=False)
 device_name = Column(String(160), nullable=False)
 brand = Column(String(120), default='', nullable=False)
 serial_number = Column(String(160), default='', nullable=False)
 purchase_year = Column(Integer, default=lambda: datetime.now(WIB).year, nullable=False)
 notes = Column(Text, default='', nullable=False)


class AdoMutation(Base):
 __tablename__ = 'ado_mutations'
 id = Column(Integer, primary_key=True)
 asset_id = Column(Integer, ForeignKey('ado_assets.id'), nullable=False, index=True)
 from_store_id = Column(Integer, nullable=True)
 from_store_name = Column(String(200), default='', nullable=False)
 to_store_id = Column(Integer, nullable=False)
 to_store_name = Column(String(200), default='', nullable=False)
 device_name = Column(String(160), default='', nullable=False)
 serial_number = Column(String(160), default='', nullable=False)
 moved_by = Column(String(160), default='', nullable=False)
 notes = Column(Text, default='', nullable=False)
 moved_at = Column(Float, default=now, index=True)


class AdoAssetLog(Base):
 __tablename__ = 'ado_asset_logs'
 id = Column(Integer, primary_key=True)
 asset_id = Column(Integer, ForeignKey('ado_assets.id', ondelete='CASCADE'), nullable=False, index=True)
 event_type = Column(String(32), default='catatan', nullable=False)
 event_date = Column(String(20), default='', nullable=False)
 description = Column(Text, default='', nullable=False)
 actor_name = Column(String(160), default='', nullable=False)
 created_at = Column(Float, default=now, index=True)


Base.metadata.create_all(engine)
if 'parent_category' not in {col['name'] for col in inspect(engine).get_columns('ado_catalog')}:
 with engine.begin() as conn:
  conn.execute(text("ALTER TABLE ado_catalog ADD COLUMN parent_category VARCHAR(160) NOT NULL DEFAULT ''"))
if 'signature_data' not in {col['name'] for col in inspect(engine).get_columns('ado_users')}:
 with engine.begin() as conn:
  conn.execute(text("ALTER TABLE ado_users ADD COLUMN signature_data TEXT NOT NULL DEFAULT ''"))
do_cols = {col['name'] for col in inspect(engine).get_columns('ado_delivery_orders')}
if 'delivery_date' not in do_cols:
 with engine.begin() as conn:
  conn.execute(text("ALTER TABLE ado_delivery_orders ADD COLUMN delivery_date VARCHAR(40) NOT NULL DEFAULT ''"))
if 'approved_signature' not in do_cols:
 with engine.begin() as conn:
  conn.execute(text("ALTER TABLE ado_delivery_orders ADD COLUMN approved_signature TEXT NOT NULL DEFAULT ''"))
if 'purchase_date' not in {col['name'] for col in inspect(engine).get_columns('ado_assets')}:
 with engine.begin() as conn:
  conn.execute(text("ALTER TABLE ado_assets ADD COLUMN purchase_date VARCHAR(20) NOT NULL DEFAULT ''"))


def ensure_ado_defaults(s: Session):
 has_cats = s.query(AdoCatalog).filter_by(kind='category').count() > 0
 has_parented_devs = s.query(AdoCatalog).filter(AdoCatalog.kind == 'device', AdoCatalog.parent_category != '').count() > 0
 if not has_cats or not has_parented_devs:
  s.query(AdoCatalog).filter(AdoCatalog.kind == 'device', AdoCatalog.parent_category == '').delete(synchronize_session=False)
  existing_cats = {r.name.casefold() for r in s.query(AdoCatalog).filter_by(kind='category').all()}
  for grp, cat_name, devices in DEFAULT_CATALOG_TREE:
   if cat_name.casefold() not in existing_cats:
    s.add(AdoCatalog(kind='category', group_type=grp, parent_category='', name=cat_name))
    existing_cats.add(cat_name.casefold())
   for dev_name in devices:
    s.add(AdoCatalog(kind='device', group_type=grp, parent_category=cat_name, name=dev_name))
  s.commit()


def sync_all_simon_users(s: Session):
 ensure_ado_defaults(s)
 existing = {u.username.casefold() for u in s.query(AdoUser).all()}
 added = False
 for su in s.query(User).all():
  if su.username.casefold() not in existing:
   role = su.role if su.role in ADO_ROLES else 'ts'
   s.add(AdoUser(
    name=su.name,
    username=su.username,
    password=su.password,
    role=role,
    active=int(bool(su.active)),
   ))
   existing.add(su.username.casefold())
   added = True
 if added:
  s.commit()


def sync_simon_user_if_needed(s: Session, username: str):
 sync_all_simon_users(s)
 return s.query(AdoUser).filter_by(username=username).first()


router = APIRouter(prefix='/api/ado', tags=['ado'])


def ado_user(request: Request, s: Session = Depends(db)) -> AdoUser:
 token = request.cookies.get('ado_session', '')
 if not token:
  raise HTTPException(401, 'Silakan login ke ADO')
 sess = s.get(AdoSession, digest(token))
 if not sess or sess.expires < now():
  raise HTTPException(401, 'Sesi ADO berakhir, silakan login kembali')
 u = s.get(AdoUser, sess.user_id)
 if not u or not u.active:
  raise HTTPException(401, 'Akun ADO nonaktif')
 if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('x-siams-request') != '1':
  raise HTTPException(403, 'Header CSRF diperlukan')
 return u


def ado_admin_or_it(u: AdoUser = Depends(ado_user)) -> AdoUser:
 if u.role not in ('super_admin', 'admin_it'):
  raise HTTPException(403, 'Akses Admin IT atau Super Admin diperlukan')
 return u


def ado_super_admin(u: AdoUser = Depends(ado_user)) -> AdoUser:
 if u.role != 'super_admin':
  raise HTTPException(403, 'Hanya Super Admin yang diizinkan')
 return u


def visible_stores_query(s: Session, u: AdoUser):
 q = s.query(AdoStore).order_by(AdoStore.store_code, AdoStore.name)
 if u.role == 'ts':
  q = q.filter(AdoStore.ts_user_id == u.id)
 return q


def can_access_store(u: AdoUser, store: AdoStore) -> bool:
 return u.role in ('super_admin', 'admin_it') or store.ts_user_id == u.id


class AdoLoginInput(BaseModel):
 username: str
 password: str


@router.post('/login')
def ado_login(v: AdoLoginInput, request: Request, response: Response, s: Session = Depends(db)):
 limit(('ado_login', request.client.host))
 u = sync_simon_user_if_needed(s, v.username.strip())
 if not u or not u.active or not hmac.compare_digest(u.password, password(v.password, u.password.split(':')[0])):
  raise HTTPException(401, 'Username atau password ADO tidak valid')
 token = secrets.token_urlsafe(32)
 s.add(AdoSession(token=digest(token), user_id=u.id, expires=now() + 28800))
 s.commit()
 response.set_cookie(
  'ado_session',
  token,
  httponly=True,
  samesite='strict',
  secure=False,
  max_age=28800,
 )
 from backend.main import APP_VERSION
 return {'id': u.id, 'name': u.name, 'username': u.username, 'role': u.role, 'version': APP_VERSION, 'portal': 'ado', 'signature_data': u.signature_data or ''}


def sanitize_signature(sig: str | None) -> str:
 raw = (sig or '').strip()
 if not raw:
  return ''
 allowed_prefixes = (
  'data:image/png;base64,',
  'data:image/jpeg;base64,',
  'data:image/jpg;base64,',
  'data:image/webp;base64,',
 )
 if not raw.startswith(allowed_prefixes):
  raise HTTPException(422, 'Format tanda tangan harus gambar PNG/JPG/WEBP')
 if len(raw) > 400_000:
  raise HTTPException(422, 'Ukuran gambar tanda tangan terlalu besar (maks 300 KB)')
 return raw


class SignatureInput(BaseModel):
 signature_data: str = ''


@router.post('/logout')
def ado_logout(request: Request, response: Response, s: Session = Depends(db)):
 if request.headers.get('x-siams-request') != '1':
  raise HTTPException(403, 'Header CSRF diperlukan')
 token = request.cookies.get('ado_session', '')
 if token:
  s.query(AdoSession).filter_by(token=digest(token)).delete()
  s.commit()
 response.delete_cookie('ado_session')
 return {'ok': True}


@router.get('/me')
def ado_me(u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 ensure_ado_defaults(s)
 from backend.main import APP_VERSION
 pending_do = s.query(AdoDeliveryOrder).filter_by(status='pending')
 if u.role == 'ts':
  store_ids = [st.id for st in visible_stores_query(s, u).all()]
  pending_count = pending_do.filter(AdoDeliveryOrder.store_id.in_(store_ids)).count() if store_ids else 0
 else:
  pending_count = pending_do.count()
 return {
  'id': u.id,
  'name': u.name,
  'username': u.username,
  'role': u.role,
  'version': APP_VERSION,
  'portal': 'ado',
  'pending_do_count': pending_count,
  'signature_data': u.signature_data or '',
 }


@router.put('/me/signature')
def update_my_signature(v: SignatureInput, u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 u.signature_data = sanitize_signature(v.signature_data)
 s.commit()
 return {'ok': True, 'signature_data': u.signature_data}


@router.get('/catalog')
def get_catalog(u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 ensure_ado_defaults(s)
 rows = s.query(AdoCatalog).order_by(AdoCatalog.kind, AdoCatalog.id).all()
 return {
  'categories': [{'id': r.id, 'group_type': r.group_type, 'name': r.name} for r in rows if r.kind == 'category'],
  'devices': [{'id': r.id, 'group_type': r.group_type, 'parent_category': r.parent_category or '', 'name': r.name} for r in rows if r.kind == 'device'],
 }


class CatalogInput(BaseModel):
 kind: str = Field(pattern='^(category|device)$')
 group_type: str = 'PERANGKAT'
 parent_category: str = ''
 name: str = Field(min_length=1, max_length=160)


@router.post('/catalog')
def add_catalog(v: CatalogInput, u: AdoUser = Depends(ado_super_admin), s: Session = Depends(db)):
 clean = v.name.strip()
 parent = v.parent_category.strip() if v.kind == 'device' else ''
 grp = 'CCTV_NETWORK' if v.group_type == 'CCTV_NETWORK' else 'PERANGKAT'
 if v.kind == 'device' and parent:
  cat_row = s.query(AdoCatalog).filter(AdoCatalog.kind == 'category', AdoCatalog.name == parent).first()
  if cat_row:
   grp = cat_row.group_type
 q = s.query(AdoCatalog).filter(AdoCatalog.kind == v.kind, AdoCatalog.name.ilike(clean))
 if v.kind == 'device':
  q = q.filter(AdoCatalog.parent_category == parent)
 if q.first():
  raise HTTPException(409, f'{clean} sudah ada di area/kategori ini')
 item = AdoCatalog(kind=v.kind, group_type=grp, parent_category=parent, name=clean)
 s.add(item)
 s.commit()
 return {'id': item.id, 'kind': item.kind, 'group_type': item.group_type, 'parent_category': item.parent_category, 'name': item.name}


@router.delete('/catalog/{id}')
def delete_catalog(id: int, u: AdoUser = Depends(ado_super_admin), s: Session = Depends(db)):
 item = s.get(AdoCatalog, id)
 if not item:
  raise HTTPException(404, 'Item master tidak ditemukan')
 if item.kind == 'category':
  s.query(AdoCatalog).filter(AdoCatalog.kind == 'device', AdoCatalog.parent_category == item.name).delete(synchronize_session=False)
 s.delete(item)
 s.commit()
 return {'ok': True}


@router.get('/summary')
def ado_summary(u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 ensure_ado_defaults(s)
 stores = visible_stores_query(s, u).all()
 store_ids = [st.id for st in stores]
 jabodetabek = sum(1 for st in stores if st.region == 'Jabodetabek')
 luar = sum(1 for st in stores if st.region != 'Jabodetabek')
 if store_ids:
  total_assets = s.query(AdoAsset).filter(AdoAsset.store_id.in_(store_ids)).count()
  pending_do = s.query(AdoDeliveryOrder).filter(AdoDeliveryOrder.store_id.in_(store_ids), AdoDeliveryOrder.status == 'pending').count()
  confirmed_do = s.query(AdoDeliveryOrder).filter(AdoDeliveryOrder.store_id.in_(store_ids), AdoDeliveryOrder.status == 'confirmed').count()
 else:
  total_assets = pending_do = confirmed_do = 0
 return {
  'stores_total': len(stores),
  'stores_jabodetabek': jabodetabek,
  'stores_luar': luar,
  'total_assets': total_assets,
  'pending_do': pending_do,
  'confirmed_do': confirmed_do,
 }


def serialize_store(st: AdoStore, ts_map: dict[int, str], asset_counts: dict[int, int]):
 return {
  'id': st.id,
  'store_code': st.store_code,
  'name': st.name,
  'region': st.region,
  'store_type': st.store_type,
  'ts_user_id': st.ts_user_id,
  'ts_name': ts_map.get(st.ts_user_id, 'Belum diassign'),
  'asset_count': asset_counts.get(st.id, 0),
 }


@router.get('/stores')
def list_stores(u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 sync_all_simon_users(s)
 stores = visible_stores_query(s, u).all()
 ts_map = {x.id: x.name for x in s.query(AdoUser).all()}
 counts = {}
 for asset in s.query(AdoAsset.store_id).all():
  counts[asset[0]] = counts.get(asset[0], 0) + 1
 return [serialize_store(st, ts_map, counts) for st in stores]


class StoreInput(BaseModel):
 store_code: str = Field(min_length=1, max_length=40)
 name: str = Field(min_length=1, max_length=200)
 region: str = 'Jabodetabek'
 store_type: str = 'Existing Store'
 ts_user_id: int | None = None


@router.post('/stores')
def create_store(v: StoreInput, u: AdoUser = Depends(ado_admin_or_it), s: Session = Depends(db)):
 code = v.store_code.strip()
 name = v.name.strip()
 if s.query(AdoStore).filter(AdoStore.store_code.ilike(code)).first():
  raise HTTPException(409, f'Kode store {code} sudah terdaftar di ADO')
 region = 'Luar Jabodetabek' if v.region == 'Luar Jabodetabek' else 'Jabodetabek'
 st_type = 'New Store' if v.store_type == 'New Store' else 'Existing Store'
 st = AdoStore(store_code=code, name=name, region=region, store_type=st_type, ts_user_id=v.ts_user_id)
 s.add(st)
 s.commit()
 s.refresh(st)
 return {'id': st.id, 'store_code': st.store_code, 'name': st.name}


@router.put('/stores/{id}')
def update_store(id: int, v: StoreInput, u: AdoUser = Depends(ado_admin_or_it), s: Session = Depends(db)):
 st = s.get(AdoStore, id)
 if not st:
  raise HTTPException(404, 'Store tidak ditemukan')
 code = v.store_code.strip()
 dup = s.query(AdoStore).filter(AdoStore.id != id, AdoStore.store_code.ilike(code)).first()
 if dup:
  raise HTTPException(409, f'Kode store {code} sudah digunakan oleh {dup.name}')
 st.store_code = code
 st.name = v.name.strip()
 st.region = 'Luar Jabodetabek' if v.region == 'Luar Jabodetabek' else 'Jabodetabek'
 st.store_type = 'New Store' if v.store_type == 'New Store' else 'Existing Store'
 st.ts_user_id = v.ts_user_id
 s.commit()
 return {'ok': True}


@router.delete('/stores/{id}')
def delete_store(id: int, u: AdoUser = Depends(ado_super_admin), s: Session = Depends(db)):
 st = s.get(AdoStore, id)
 if not st:
  raise HTTPException(404, 'Store tidak ditemukan')
 s.query(AdoAsset).filter_by(store_id=id).delete(synchronize_session=False)
 s.delete(st)
 s.commit()
 return {'ok': True}


@router.get('/stores/template')
def download_store_template(u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 from openpyxl import load_workbook  # noqa: F401
 wb = Workbook()
 ws = wb.active
 ws.title = 'Data Store'
 headers = ['Kode Store', 'Nama Store', 'Wilayah', 'Kategori Store', 'Technical Support']
 ws.append(headers)
 ws.freeze_panes = 'A2'
 for cell in ws[1]:
  cell.fill = PatternFill('solid', fgColor='145D59')
  cell.font = Font(name='Calibri', size=11, color='FFFFFF', bold=True)
  cell.alignment = Alignment(vertical='center', wrap_text=True)
 widths = [16, 34, 20, 18, 24]
 for idx, w in enumerate(widths, 1):
  ws.column_dimensions[ws.cell(1, idx).column_letter].width = w
 ts_example = u.username if u.role == 'ts' else 'dovi'
 ws.append(['00115', 'HokBen Mall Grand Indonesia', 'Jabodetabek', 'Existing Store', ts_example])
 ws.append(['00201', 'HokBen Bandung', 'Luar Jabodetabek', 'New Store', ts_example])
 for row_idx in range(2, 200):
  ws.cell(row=row_idx, column=1).number_format = '@'

 ws_guide = wb.create_sheet('Panduan & Daftar TS')
 ws_guide.append(['Kolom', 'Wajib?', 'Keterangan / Pilihan Valid'])
 for cell in ws_guide[1]:
  cell.fill = PatternFill('solid', fgColor='145D59')
  cell.font = Font(name='Calibri', size=11, color='FFFFFF', bold=True)
 ws_guide.append(['Kode Store', 'Wajib', 'Kode unik store (format teks agar angka 0 di depan tidak hilang, contoh: 00115)'])
 ws_guide.append(['Nama Store', 'Wajib', 'Nama lengkap store, contoh: HokBen Mall Grand Indonesia'])
 ws_guide.append(['Wilayah', 'Opsional', 'Isi: Jabodetabek atau Luar Jabodetabek (default: Jabodetabek)'])
 ws_guide.append(['Kategori Store', 'Opsional', 'Isi: Existing Store atau New Store (default: Existing Store)'])
 ws_guide.append(['Technical Support', 'Opsional', 'Isi username atau nama TS. Jika yang import akun TS, otomatis di-assign ke akun TS tersebut.'])
 ws_guide.append([])
 ws_guide.append(['Daftar Akun TS Aktif', 'Username', 'Nama'])
 for ts_u in s.query(AdoUser).filter_by(role='ts', active=1).order_by(AdoUser.name).all():
  ws_guide.append(['TS', ts_u.username, ts_u.name])
 ws_guide.column_dimensions['A'].width = 22
 ws_guide.column_dimensions['B'].width = 18
 ws_guide.column_dimensions['C'].width = 72

 out = io.BytesIO()
 wb.save(out)
 wb.close()
 out.seek(0)
 return StreamingResponse(
  out,
  media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  headers={'Content-Disposition': 'attachment; filename="Template-Import-Store-ADO.xlsx"'},
 )


class StoreImportInput(BaseModel):
 content_base64: str = Field(min_length=10, max_length=7_000_000)
 update_existing: bool = True


def _clean_excel_code(val) -> str:
 if val is None:
  return ''
 if isinstance(val, float) and val.is_integer():
  return str(int(val))
 return str(val).strip()


@router.post('/stores/import')
def import_stores_excel(v: StoreImportInput, u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 from openpyxl import load_workbook
 raw_b64 = v.content_base64.split(',', 1)[-1].strip()
 try:
  raw_bytes = base64.b64decode(raw_b64, validate=True)
  wb = load_workbook(io.BytesIO(raw_bytes), data_only=True)
 except Exception as exc:
  raise HTTPException(422, f'File Excel (.xlsx) tidak valid: {exc}')
 ws = wb.active
 ts_users = s.query(AdoUser).filter_by(role='ts').all()
 ts_by_key = {}
 for tu in ts_users:
  ts_by_key[tu.username.strip().casefold()] = tu.id
  ts_by_key[tu.name.strip().casefold()] = tu.id
 existing_by_code = {st.store_code.strip().casefold(): st for st in s.query(AdoStore).all()}

 created = 0
 updated = 0
 skipped = 0
 errors = []

 for row_num, row in enumerate(ws.iter_rows(values_only=True), 1):
  if not row or all(cell is None or str(cell).strip() == '' for cell in row):
   continue
  code = _clean_excel_code(row[0] if len(row) > 0 else '')
  name = str(row[1] if len(row) > 1 and row[1] is not None else '').strip()
  if row_num == 1 and code.casefold() in ('kode store', 'store_code', 'kode'):
   continue
  if not code or not name:
   errors.append(f'Baris {row_num}: Kode Store dan Nama Store wajib diisi')
   continue
  raw_region = str(row[2] if len(row) > 2 and row[2] is not None else '').strip()
  raw_type = str(row[3] if len(row) > 3 and row[3] is not None else '').strip()
  raw_ts = str(row[4] if len(row) > 4 and row[4] is not None else '').strip()
  region = 'Luar Jabodetabek' if 'luar' in raw_region.casefold() else 'Jabodetabek'
  st_type = 'New Store' if 'new' in raw_type.casefold() else 'Existing Store'
  ts_id = u.id if u.role == 'ts' else ts_by_key.get(raw_ts.casefold())

  key = code.casefold()
  existing = existing_by_code.get(key)
  if existing:
   if u.role == 'ts' and existing.ts_user_id not in (None, u.id):
    skipped += 1
    errors.append(f'Baris {row_num}: Kode {code} sudah terdaftar pada TS lain')
    continue
   if v.update_existing:
    existing.name = name[:200]
    existing.region = region
    existing.store_type = st_type
    if u.role == 'ts':
     existing.ts_user_id = u.id
    elif ts_id is not None:
     existing.ts_user_id = ts_id
    updated += 1
   else:
    skipped += 1
  else:
   st = AdoStore(
    store_code=code[:40],
    name=name[:200],
    region=region,
    store_type=st_type,
    ts_user_id=ts_id,
   )
   s.add(st)
   existing_by_code[key] = st
   created += 1

 wb.close()
 s.commit()
 return {'ok': True, 'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors[:20]}


def add_asset_log(
 s: Session,
 asset_id: int,
 event_type: str,
 description: str,
 actor_name: str,
 event_date: str = '',
):
 ev_date = (event_date or '').strip() or datetime.now(WIB).strftime('%Y-%m-%d')
 s.add(AdoAssetLog(
  asset_id=asset_id,
  event_type=event_type,
  event_date=ev_date[:20],
  description=(description or '').strip(),
  actor_name=(actor_name or '').strip()[:160],
  created_at=now(),
 ))


def serialize_asset(
 a: AdoAsset,
 store_map: dict[int, AdoStore],
 current_year: int,
 do_map: dict[int, str] | None = None,
 log_counts: dict[int, dict[str, int]] | None = None,
):
 st = store_map.get(a.store_id)
 age = max(0, current_year - (a.purchase_year or current_year))
 date_label = format_delivery_date_str(a.purchase_date, a.updated_at)
 do_num = (do_map or {}).get(a.do_id, '') if a.do_id else ''
 counts = (log_counts or {}).get(a.id, {})
 return {
  'id': a.id,
  'store_id': a.store_id,
  'store_code': st.store_code if st else '',
  'store_name': st.name if st else '-',
  'group_type': a.group_type,
  'category': a.category,
  'device_name': a.device_name,
  'brand': a.brand,
  'serial_number': a.serial_number,
  'purchase_year': a.purchase_year,
  'purchase_date': a.purchase_date or '',
  'purchase_date_label': date_label,
  'age_years': age,
  'age_label': f'{age} Tahun',
  'status': a.status,
  'notes': a.notes,
  'do_id': a.do_id,
  'do_number': do_num,
  'repair_count': counts.get('repair', 0),
  'issue_count': counts.get('issue', 0),
  'log_count': counts.get('total', 0),
  'updated_at': a.updated_at,
 }


@router.get('/assets')
def list_assets(
 group_type: str = '',
 store_id: int | None = None,
 status: str = '',
 q: str = '',
 u: AdoUser = Depends(ado_user),
 s: Session = Depends(db),
):
 stores = visible_stores_query(s, u).all()
 store_map = {st.id: st for st in stores}
 if not store_map:
  return []
 query = s.query(AdoAsset).filter(AdoAsset.store_id.in_(store_map.keys()))
 if group_type:
  query = query.filter(AdoAsset.group_type == group_type)
 if store_id is not None:
  query = query.filter(AdoAsset.store_id == store_id)
 if status:
  query = query.filter(AdoAsset.status == status)
 rows = query.order_by(AdoAsset.id.desc()).all()
 do_ids = {a.do_id for a in rows if a.do_id}
 do_map = {
  o.id: o.do_number
  for o in s.query(AdoDeliveryOrder).filter(AdoDeliveryOrder.id.in_(do_ids)).all()
 } if do_ids else {}
 asset_ids = [a.id for a in rows]
 log_counts: dict[int, dict[str, int]] = {}
 if asset_ids:
  for aid, ev_type in s.query(AdoAssetLog.asset_id, AdoAssetLog.event_type).filter(AdoAssetLog.asset_id.in_(asset_ids)).all():
   bucket = log_counts.setdefault(aid, {'repair': 0, 'issue': 0, 'total': 0})
   bucket['total'] += 1
   if ev_type == 'perbaikan':
    bucket['repair'] += 1
   elif ev_type == 'rusak':
    bucket['issue'] += 1
 current_year = datetime.now(WIB).year
 items = [serialize_asset(a, store_map, current_year, do_map, log_counts) for a in rows]
 if q.strip():
  needle = q.strip().casefold()
  items = [
   x for x in items
   if needle in ' '.join((x['store_code'], x['store_name'], x['category'], x['device_name'], x['brand'], x['serial_number'], x['notes'])).casefold()
  ]
 return items


class AssetInput(BaseModel):
 store_id: int
 group_type: str = 'PERANGKAT'
 category: str = Field(min_length=1, max_length=100)
 device_name: str = Field(min_length=1, max_length=160)
 brand: str = Field(default='', max_length=120)
 serial_number: str = Field(default='', max_length=160)
 purchase_year: int = Field(default_factory=lambda: datetime.now(WIB).year, ge=1990, le=2100)
 purchase_date: str = Field(default='', max_length=20)
 status: str = 'normal'
 notes: str = ''


@router.post('/assets')
def create_asset(v: AssetInput, u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 st = s.get(AdoStore, v.store_id)
 if not st or not can_access_store(u, st):
  raise HTTPException(404, 'Store tidak ditemukan atau tidak memiliki akses')
 grp = 'CCTV_NETWORK' if v.group_type == 'CCTV_NETWORK' or 'CCTV' in v.category.upper() or 'NETWORK' in v.category.upper() else 'PERANGKAT'
 st_val = v.status if v.status in ('normal', 'perbaikan', 'rusak') else 'normal'
 a = AdoAsset(
  store_id=v.store_id,
  group_type=grp,
  category=v.category.strip(),
  device_name=v.device_name.strip(),
  brand=v.brand.strip(),
  serial_number=v.serial_number.strip(),
  purchase_year=v.purchase_year,
  purchase_date=v.purchase_date.strip() or datetime.now(WIB).strftime('%Y-%m-%d'),
  status=st_val,
  notes=v.notes.strip(),
  updated_at=now(),
 )
 s.add(a)
 s.flush()
 init_ev = st_val if st_val in ('perbaikan', 'rusak') else 'catatan'
 init_desc = f'Asset ditambahkan ({st_val})' + (f' — {a.notes}' if a.notes else '')
 add_asset_log(s, a.id, init_ev, init_desc, u.name, a.purchase_date)
 s.commit()
 s.refresh(a)
 return {'id': a.id}


@router.put('/assets/{id}')
def update_asset(id: int, v: AssetInput, u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 a = s.get(AdoAsset, id)
 if not a:
  raise HTTPException(404, 'Perangkat tidak ditemukan')
 st = s.get(AdoStore, a.store_id)
 if not st or not can_access_store(u, st):
  raise HTTPException(403, 'Tidak memiliki akses ke perangkat store ini')
 prev_status = a.status
 prev_notes = a.notes
 a.store_id = v.store_id
 a.group_type = 'CCTV_NETWORK' if v.group_type == 'CCTV_NETWORK' or 'CCTV' in v.category.upper() or 'NETWORK' in v.category.upper() else 'PERANGKAT'
 a.category = v.category.strip()
 a.device_name = v.device_name.strip()
 a.brand = v.brand.strip()
 a.serial_number = v.serial_number.strip()
 a.purchase_year = v.purchase_year
 if v.purchase_date.strip():
  a.purchase_date = v.purchase_date.strip()
 a.status = v.status if v.status in ('normal', 'perbaikan', 'rusak') else 'normal'
 a.notes = v.notes.strip()
 a.updated_at = now()
 if a.status != prev_status:
  ev = a.status if a.status in ('perbaikan', 'rusak', 'normal') else 'catatan'
  desc = f'Status diubah: {prev_status} -> {a.status}' + (f' ({a.notes})' if a.notes and a.notes != prev_notes else '')
  add_asset_log(s, a.id, ev, desc, u.name)
 elif a.notes and a.notes != prev_notes:
  add_asset_log(s, a.id, 'catatan', f'Catatan diperbarui: {a.notes}', u.name)
 s.commit()
 return {'ok': True}


@router.delete('/assets/{id}')
def delete_asset(id: int, u: AdoUser = Depends(ado_admin_or_it), s: Session = Depends(db)):
 a = s.get(AdoAsset, id)
 if not a:
  raise HTTPException(404, 'Perangkat tidak ditemukan')
 s.query(AdoAssetLog).filter(AdoAssetLog.asset_id == id).delete(synchronize_session=False)
 s.delete(a)
 s.commit()
 return {'ok': True}


class AssetLogInput(BaseModel):
 event_type: str = 'perbaikan'
 event_date: str = Field(default='', max_length=20)
 description: str = Field(min_length=1, max_length=1000)
 update_status: bool = True


@router.get('/assets/{id}/logs')
def list_asset_logs(id: int, u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 a = s.get(AdoAsset, id)
 if not a:
  raise HTTPException(404, 'Perangkat tidak ditemukan')
 st = s.get(AdoStore, a.store_id)
 if not st or not can_access_store(u, st):
  raise HTTPException(403, 'Tidak memiliki akses ke riwayat perangkat ini')
 rows = s.query(AdoAssetLog).filter(AdoAssetLog.asset_id == id).order_by(AdoAssetLog.event_date.desc(), AdoAssetLog.id.desc()).all()
 do_map = {}
 if a.do_id:
  order = s.get(AdoDeliveryOrder, a.do_id)
  if order:
   do_map[order.id] = order.do_number
 repair_cnt = sum(1 for r in rows if r.event_type == 'perbaikan')
 issue_cnt = sum(1 for r in rows if r.event_type == 'rusak')
 mut_cnt = sum(1 for r in rows if r.event_type == 'mutasi')
 log_counts = {a.id: {'repair': repair_cnt, 'issue': issue_cnt, 'total': len(rows)}}
 return {
  'asset': serialize_asset(a, {st.id: st}, datetime.now(WIB).year, do_map, log_counts),
  'counts': {
   'perbaikan': repair_cnt,
   'rusak': issue_cnt,
   'mutasi': mut_cnt,
   'total': len(rows),
  },
  'logs': [{
   'id': r.id,
   'asset_id': r.asset_id,
   'event_type': r.event_type,
   'event_date': r.event_date,
   'description': r.description,
   'actor_name': r.actor_name,
   'created_at': r.created_at,
  } for r in rows],
 }


@router.post('/assets/{id}/logs')
def create_asset_log(id: int, v: AssetLogInput, u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 a = s.get(AdoAsset, id)
 if not a:
  raise HTTPException(404, 'Perangkat tidak ditemukan')
 st = s.get(AdoStore, a.store_id)
 if not st or not can_access_store(u, st):
  raise HTTPException(403, 'Tidak memiliki akses ke perangkat store ini')
 ev = v.event_type if v.event_type in ('perbaikan', 'rusak', 'normal', 'catatan') else 'catatan'
 ev_date = v.event_date.strip() or datetime.now(WIB).strftime('%Y-%m-%d')
 log = AdoAssetLog(
  asset_id=a.id,
  event_type=ev,
  event_date=ev_date[:20],
  description=v.description.strip(),
  actor_name=u.name,
  created_at=now(),
 )
 s.add(log)
 if v.update_status and ev in ('perbaikan', 'rusak', 'normal'):
  a.status = ev
 a.updated_at = now()
 s.commit()
 s.refresh(log)
 return {'ok': True, 'id': log.id, 'status': a.status}


def next_do_number(s: Session) -> str:
 dt = datetime.now(WIB)
 roman = ROMAN_MONTHS[dt.month - 1]
 year_suffix = f'/{dt.year}'
 existing = s.query(AdoDeliveryOrder.do_number).filter(AdoDeliveryOrder.do_number.like(f'%{year_suffix}')).all()
 max_seq = 0
 for (code,) in existing:
  parts = str(code).split('/')
  if len(parts) >= 4 and parts[3].isdigit():
   max_seq = max(max_seq, int(parts[3]))
 return f'{roman}/DO/IT/{max_seq + 1:03d}/{dt.year}'


class DoItemInput(BaseModel):
 category: str = Field(min_length=1, max_length=100)
 device_name: str = Field(min_length=1, max_length=160)
 brand: str = Field(default='', max_length=120)
 serial_number: str = Field(default='', max_length=160)
 purchase_year: int = Field(default_factory=lambda: datetime.now(WIB).year, ge=1990, le=2100)
 notes: str = ''


class DeliveryOrderInput(BaseModel):
 store_id: int
 store_type: str = 'Existing Store'
 notes: str = ''
 items: list[DoItemInput] = Field(min_length=1, max_length=100)


@router.get('/do')
def list_delivery_orders(
 status: str = '',
 store_type: str = '',
 q: str = '',
 u: AdoUser = Depends(ado_user),
 s: Session = Depends(db),
):
 stores = visible_stores_query(s, u).all()
 store_map = {st.id: st for st in s.query(AdoStore).all()}
 visible_ids = {st.id for st in stores}
 query = s.query(AdoDeliveryOrder).order_by(AdoDeliveryOrder.id.desc())
 if u.role == 'ts':
  if not visible_ids:
   return []
  query = query.filter(AdoDeliveryOrder.store_id.in_(visible_ids))
 if status:
  query = query.filter(AdoDeliveryOrder.status == status)
 if store_type:
  query = query.filter(AdoDeliveryOrder.store_type == store_type)
 orders = query.all()
 do_ids = [o.id for o in orders]
 items_by_do = {did: [] for did in do_ids}
 if do_ids:
  for item in s.query(AdoDoItem).filter(AdoDoItem.do_id.in_(do_ids)).order_by(AdoDoItem.id).all():
   items_by_do[item.do_id].append({
    'id': item.id,
    'category': item.category,
    'device_name': item.device_name,
    'brand': item.brand,
    'serial_number': item.serial_number,
    'purchase_year': item.purchase_year,
    'notes': item.notes,
   })
 result = []
 needle = q.strip().casefold()
 for o in orders:
  st = store_map.get(o.store_id)
  row = {
   'id': o.id,
   'do_number': o.do_number,
   'store_id': o.store_id,
   'store_code': st.store_code if st else '',
   'store_name': st.name if st else '-',
   'store_type': o.store_type,
   'ts_user_id': o.ts_user_id,
   'ts_name': o.ts_name,
   'request_date': o.request_date,
   'delivery_date': o.delivery_date or '',
   'status': o.status,
   'confirmed_at': o.confirmed_at,
   'confirmed_by': o.confirmed_by,
   'has_signature': bool(o.approved_signature),
   'notes': o.notes,
   'items': items_by_do.get(o.id, []),
  }
  if needle and needle not in ' '.join((row['do_number'], row['store_code'], row['store_name'], row['ts_name'])).casefold():
   continue
  result.append(row)
 return result


@router.post('/do')
def create_delivery_order(v: DeliveryOrderInput, u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 st = s.get(AdoStore, v.store_id)
 if not st or not can_access_store(u, st):
  raise HTTPException(404, 'Store tidak ditemukan atau tidak memiliki akses')
 st_type = 'New Store' if v.store_type == 'New Store' else 'Existing Store'
 ts_owner = s.get(AdoUser, st.ts_user_id) if st.ts_user_id else None
 ts_label = u.name if u.role == 'ts' else (ts_owner.name if ts_owner else u.name)
 order = AdoDeliveryOrder(
  do_number=next_do_number(s),
  store_type=st_type,
  store_id=st.id,
  ts_user_id=u.id if u.role == 'ts' else st.ts_user_id,
  ts_name=ts_label,
  request_date=now(),
  status='pending',
  notes=v.notes.strip(),
 )
 s.add(order)
 s.flush()
 for item in v.items:
  cat = item.category.strip()
  grp = 'CCTV_NETWORK' if ('CCTV' in cat.upper() or 'NETWORK' in cat.upper()) else 'PERANGKAT'
  s.add(AdoDoItem(
   do_id=order.id,
   group_type=grp,
   category=cat,
   device_name=item.device_name.strip(),
   brand=item.brand.strip(),
   serial_number=item.serial_number.strip(),
   purchase_year=item.purchase_year,
   notes=item.notes.strip(),
  ))
 s.commit()
 return {'id': order.id, 'do_number': order.do_number, 'status': order.status}


class DoEditInput(BaseModel):
 do_number: str | None = Field(default=None, min_length=1, max_length=80)
 store_id: int | None = None
 store_type: str | None = None
 ts_name: str | None = Field(default=None, max_length=160)
 delivery_date: str | None = Field(default=None, max_length=40)
 notes: str | None = None
 items: list[DoItemInput] | None = Field(default=None, min_length=1, max_length=100)


class ConfirmDoInput(DoEditInput):
 confirmed_by: str | None = Field(default=None, max_length=160)
 approved_signature: str | None = None
 save_user_signature: bool = False


def apply_do_edits(s: Session, order: AdoDeliveryOrder, v: DoEditInput):
 if v.do_number is not None:
  new_num = v.do_number.strip()
  if not new_num:
   raise HTTPException(422, 'Nomor DO tidak boleh kosong')
  if s.query(AdoDeliveryOrder).filter(AdoDeliveryOrder.id != order.id, AdoDeliveryOrder.do_number == new_num).first():
   raise HTTPException(409, f'Nomor DO {new_num} sudah digunakan')
  order.do_number = new_num
 if v.store_id is not None:
  st = s.get(AdoStore, v.store_id)
  if not st:
   raise HTTPException(404, 'Store tujuan tidak ditemukan')
  order.store_id = st.id
 if v.store_type is not None:
  order.store_type = 'New Store' if v.store_type == 'New Store' else 'Existing Store'
 if v.ts_name is not None:
  order.ts_name = v.ts_name.strip()
 if v.delivery_date is not None:
  order.delivery_date = v.delivery_date.strip()
 if v.notes is not None:
  order.notes = v.notes.strip()
 if v.items is not None:
  s.query(AdoDoItem).filter_by(do_id=order.id).delete(synchronize_session=False)
  for item in v.items:
   cat = item.category.strip()
   grp = 'CCTV_NETWORK' if ('CCTV' in cat.upper() or 'NETWORK' in cat.upper()) else 'PERANGKAT'
   s.add(AdoDoItem(
    do_id=order.id,
    group_type=grp,
    category=cat,
    device_name=item.device_name.strip(),
    brand=item.brand.strip(),
    serial_number=item.serial_number.strip(),
    purchase_year=item.purchase_year,
    notes=item.notes.strip(),
   ))


@router.put('/do/{id}')
def update_delivery_order(id: int, v: DoEditInput, u: AdoUser = Depends(ado_admin_or_it), s: Session = Depends(db)):
 order = s.get(AdoDeliveryOrder, id)
 if not order:
  raise HTTPException(404, 'Delivery Order tidak ditemukan')
 if order.status == 'confirmed':
  raise HTTPException(409, 'DO yang sudah dikonfirmasi tidak dapat diubah')
 apply_do_edits(s, order, v)
 s.commit()
 return {'ok': True, 'id': order.id, 'do_number': order.do_number}


@router.post('/do/{id}/confirm')
def confirm_delivery_order(
 id: int,
 v: ConfirmDoInput | None = None,
 u: AdoUser = Depends(ado_admin_or_it),
 s: Session = Depends(db),
):
 order = s.get(AdoDeliveryOrder, id)
 if not order:
  raise HTTPException(404, 'Delivery Order tidak ditemukan')
 if order.status == 'confirmed':
  return {'ok': True, 'do_number': order.do_number, 'already_confirmed': True}
 if v is not None:
  apply_do_edits(s, order, v)
  s.flush()
 sig_data = sanitize_signature(v.approved_signature) if (v and v.approved_signature is not None) else (u.signature_data or '')
 if v and v.save_user_signature and sig_data:
  u.signature_data = sig_data
 approver_name = (v.confirmed_by.strip() if v and v.confirmed_by else '') or u.name
 items = s.query(AdoDoItem).filter_by(do_id=order.id).order_by(AdoDoItem.id).all()
 for item in items:
  new_asset = AdoAsset(
   store_id=order.store_id,
   group_type=item.group_type,
   category=item.category,
   device_name=item.device_name,
   brand=item.brand,
   serial_number=item.serial_number,
   purchase_year=item.purchase_year,
   purchase_date=order.delivery_date or datetime.fromtimestamp(order.request_date or now(), WIB).strftime('%Y-%m-%d'),
   status='normal',
   notes=item.notes,
   do_id=order.id,
   updated_at=now(),
  )
  s.add(new_asset)
  s.flush()
  do_desc = f'Masuk dari DO {order.do_number}' + (f' — {item.notes}' if item.notes else '')
  add_asset_log(s, new_asset.id, 'do_masuk', do_desc, approver_name, new_asset.purchase_date)
 order.status = 'confirmed'
 order.confirmed_at = now()
 order.confirmed_by = approver_name
 order.approved_signature = sig_data
 s.commit()
 return {'ok': True, 'do_number': order.do_number, 'confirmed_by': order.confirmed_by, 'added_assets': len(items)}


@router.delete('/do/{id}')
def delete_delivery_order(id: int, u: AdoUser = Depends(ado_super_admin), s: Session = Depends(db)):
 order = s.get(AdoDeliveryOrder, id)
 if not order:
  raise HTTPException(404, 'Delivery Order tidak ditemukan')
 s.query(AdoDoItem).filter_by(do_id=id).delete(synchronize_session=False)
 s.delete(order)
 s.commit()
 return {'ok': True}


ID_MONTHS = (
 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
)


def format_date_id_long(ts: float | None) -> str:
 dt = datetime.fromtimestamp(ts or now(), WIB)
 return f'{dt.day} {ID_MONTHS[dt.month - 1]} {dt.year}'


def format_delivery_date_str(raw: str | None, fallback_ts: float | None) -> str:
 val = (raw or '').strip()
 if not val:
  return format_date_id_long(fallback_ts)
 try:
  dt = datetime.strptime(val, '%Y-%m-%d')
  return f'{dt.day} {ID_MONTHS[dt.month - 1]} {dt.year}'
 except ValueError:
  return val


@router.get('/do/{id}/print', response_class=HTMLResponse)
def print_delivery_order(id: int, autoprint: int = 0, u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 order = s.get(AdoDeliveryOrder, id)
 if not order:
  raise HTTPException(404, 'Delivery Order tidak ditemukan')
 st = s.get(AdoStore, order.store_id)
 if st and not can_access_store(u, st):
  raise HTTPException(403, 'Tidak memiliki akses ke Delivery Order store ini')
 items = s.query(AdoDoItem).filter_by(do_id=order.id).order_by(AdoDoItem.id).all()
 do_date_str = format_date_id_long(order.request_date)
 delivery_date_str = format_delivery_date_str(order.delivery_date, order.confirmed_at or order.request_date)
 store_title = escape((st.name if st else '-').upper())
 default_desc = 'New Store' if order.store_type == 'New Store' else 'Replace'

 item_rows_html = []
 for idx, it in enumerate(items, 1):
  brand_part = (it.brand or '').strip().upper()
  dev_part = (it.device_name or '').strip().upper()
  brand_type = f'{brand_part} / {dev_part}' if brand_part and dev_part else (brand_part or dev_part or '-')
  desc = (it.notes or '').strip() or default_desc
  item_rows_html.append(
   f'<tr class="item-row">'
   f'<td class="c-no">{idx}</td>'
   f'<td class="c-brand">{escape(brand_type)}</td>'
   f'<td class="c-sn">{escape(it.serial_number or "-")}</td>'
   f'<td class="c-qty">1</td>'
   f'<td class="c-desc">{escape(desc)}</td>'
   f'</tr>'
  )
 item_rows_html.append(
  '<tr class="spacer-row"><td class="c-no">&nbsp;</td><td class="c-brand">&nbsp;</td>'
  '<td class="c-sn">&nbsp;</td><td class="c-qty">&nbsp;</td><td class="c-desc">&nbsp;</td></tr>'
 )

 ts_signer = escape(order.ts_name or '...........................')
 if order.status == 'confirmed' and order.confirmed_by:
  if order.approved_signature:
   admin_sig_svg = f'<div class="sig-mark"><img class="sig-img" src="{escape(order.approved_signature)}" alt="TTD Admin IT"></div>'
  else:
   admin_sig_svg = '<div class="sig-space"></div>'
  admin_signer = f'( {escape(order.confirmed_by)} )'
 else:
  admin_sig_svg = '<div class="sig-space"></div>'
  admin_signer = '( ............................................... )'

 auto_js = '<script>window.addEventListener("load",()=>setTimeout(()=>window.print(),250));</script>' if autoprint else ''

 html = f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Delivery Order - {escape(order.do_number)}</title>
<style>
  @page {{ size: A4 portrait; margin: 12mm; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 20px;
    font-family: Calibri, "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #111;
    background: #eef2f5;
  }}
  .print-toolbar {{
    max-width: 794px;
    margin: 0 auto 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #132226;
    color: #fff;
    padding: 10px 16px;
    border-radius: 8px;
  }}
  .print-toolbar button {{
    background: #0d9488;
    color: #fff;
    border: 0;
    padding: 8px 14px;
    border-radius: 6px;
    font-weight: 700;
    cursor: pointer;
    font-size: 13px;
  }}
  .print-toolbar button.close-btn {{
    background: #334155;
    margin-left: 8px;
  }}
  .do-sheet {{
    max-width: 794px;
    min-height: 1060px;
    margin: 0 auto;
    background: #fff;
    padding: 26px 30px 22px;
    box-shadow: 0 6px 24px rgba(0,0,0,.08);
    display: flex;
    flex-direction: column;
  }}
  table.doc-header {{
    width: 100%;
    border-collapse: collapse;
    border: 1.5px solid #111;
    margin-bottom: 18px;
  }}
  table.doc-header td {{
    border: 1.2px solid #111;
    padding: 5px 10px;
    font-weight: 700;
    font-size: 13px;
  }}
  .doc-logo {{
    width: 11%;
    text-align: center;
    vertical-align: middle;
    font-size: 14px;
  }}
  .doc-title-top {{
    width: 44%;
    text-align: center;
  }}
  .doc-title-main {{
    text-align: center;
    vertical-align: middle;
    font-size: 14px;
  }}
  .doc-meta-lbl {{ width: 17%; }}
  .doc-meta-val {{ width: 28%; }}

  .company-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 16px;
    line-height: 1.45;
    font-size: 12.5px;
  }}
  .company-row b {{ font-size: 13px; }}

  .meta-boxes {{
    display: grid;
    grid-template-columns: 1fr 1.05fr 1fr;
    gap: 14px;
    margin-bottom: 14px;
  }}
  .meta-box {{
    border: 1.5px solid #111;
    text-align: center;
  }}
  .meta-box .hd {{
    border-bottom: 1.2px solid #111;
    padding: 5px 8px;
    font-weight: 700;
    font-size: 13px;
  }}
  .meta-box .val {{
    padding: 16px 8px;
    font-weight: 700;
    font-size: 13.5px;
  }}

  .deliver-boxes {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 14px;
  }}
  .deliver-box {{
    border: 1.5px solid #111;
    padding: 7px 10px 14px;
    min-height: 76px;
  }}
  .deliver-box .lbl {{
    font-weight: 700;
    font-size: 13px;
    margin-bottom: 4px;
  }}
  .deliver-box .from-lines {{
    font-weight: 700;
    line-height: 1.45;
  }}
  .deliver-box .to-store {{
    font-size: 19px;
    font-weight: 400;
    letter-spacing: 0.2px;
    margin-top: 2px;
  }}

  table.items-table {{
    width: 100%;
    border-collapse: collapse;
    border: 1.5px solid #111;
    margin-bottom: 16px;
  }}
  table.items-table th {{
    border: 1.2px solid #111;
    padding: 6px 8px;
    text-align: center;
    font-weight: 700;
    font-size: 13px;
  }}
  table.items-table td {{
    border-left: 1.2px solid #111;
    border-right: 1.2px solid #111;
    padding: 6px 8px;
    vertical-align: top;
    font-size: 13px;
  }}
  table.items-table tr.spacer-row td {{
    height: {max(60, 210 - len(items) * 28)}px;
  }}
  .c-no {{ width: 7%; text-align: center; }}
  .c-brand {{ width: 34%; }}
  .c-sn {{ width: 29%; }}
  .c-qty {{ width: 8%; text-align: center; }}
  .c-desc {{ width: 22%; }}

  .check-notice {{
    text-align: center;
    font-weight: 700;
    font-size: 13.5px;
    margin: 4px 0 8px;
  }}

  .sig-grid-4 {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 14px;
  }}
  .sig-box {{
    border: 1.5px solid #111;
    padding: 6px 8px;
    min-height: 124px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    font-size: 12.5px;
  }}
  .sig-top {{ line-height: 1.4; }}
  .sig-space {{ height: 64px; }}
  .sig-mark {{
    height: 66px;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    padding: 2px 4px;
  }}
  .sig-name {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

  .sig-pic-box {{
    width: 49%;
    border: 1.5px solid #111;
    padding: 6px 10px;
    min-height: 112px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    font-size: 12.5px;
  }}
  .sig-pic-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .footer-note {{
    margin-top: auto;
    padding-top: 32px;
    font-size: 12.5px;
  }}
  .sig-img {{
    max-height: 64px;
    max-width: 165px;
    width: auto;
    height: auto;
    object-fit: contain;
    display: block;
    mix-blend-mode: multiply;
  }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .print-toolbar {{ display: none !important; }}
    .do-sheet {{ box-shadow: none; max-width: 100%; min-height: 96vh; padding: 8px 6px; }}
  }}
</style>
</head>
<body>
  <div class="print-toolbar">
    <div><b>DELIVERY ORDER FORM</b> &middot; {escape(order.do_number)} ({escape(order.store_type)})</div>
    <div>
      <button onclick="window.print()">&#128424; Print / Simpan PDF</button>
      <button class="close-btn" onclick="window.close()">Tutup</button>
    </div>
  </div>

  <div class="do-sheet">
    <table class="doc-header">
      <tr>
        <td class="doc-logo" rowspan="3">HHBG</td>
        <td class="doc-title-top">FORM</td>
        <td class="doc-meta-lbl">No. Dokumen</td>
        <td class="doc-meta-val">HBG/SUP/FRM/B.04/1</td>
      </tr>
      <tr>
        <td class="doc-title-main" rowspan="2">DELIVERY ORDER FORM</td>
        <td class="doc-meta-lbl">Revisi Ke</td>
        <td class="doc-meta-val">0</td>
      </tr>
      <tr>
        <td class="doc-meta-lbl">Tgl. Berlaku</td>
        <td class="doc-meta-val">11 Februari 2019</td>
      </tr>
    </table>

    <div class="company-row">
      <div>
        <b>PT. EKA BOGAINTI</b><br>
        Head Office<br>
        Jl. Raya Poncol No.2 Ciracas, Jakarta 13740 Indonesia.<br>
        Ph. +62 21 29981234 &nbsp; fax. +62 21 8700444-5<br>
        www.hokben.co.id
      </div>
      <div>
        &nbsp;<br>
        Repesentative Office<br>
        Gandaria 8 Office Tower 18<sup>th</sup><br>
        Jl. Sultan Iskandar Muda, Jakarta 12240<br>
        ph. +62 21 29304123 &nbsp; fax. +62 21 29304122
      </div>
    </div>

    <div class="meta-boxes">
      <div class="meta-box">
        <div class="hd">Delivery Date</div>
        <div class="val">{escape(delivery_date_str)}</div>
      </div>
      <div class="meta-box">
        <div class="hd">DO Number</div>
        <div class="val">{escape(order.do_number)}</div>
      </div>
      <div class="meta-box">
        <div class="hd">DO Date</div>
        <div class="val">{escape(do_date_str)}</div>
      </div>
    </div>

    <div class="deliver-boxes">
      <div class="deliver-box">
        <div class="lbl">DELIVER FROM</div>
        <div class="from-lines">Div. IT<br>Head Office - Ciracas</div>
      </div>
      <div class="deliver-box">
        <div class="lbl">DELIVER TO</div>
        <div class="to-store">{store_title}</div>
      </div>
    </div>

    <table class="items-table">
      <thead>
        <tr>
          <th class="c-no">No</th>
          <th class="c-brand">Brand / Type</th>
          <th class="c-sn">Serial Number</th>
          <th class="c-qty">Qty</th>
          <th class="c-desc">Description</th>
        </tr>
      </thead>
      <tbody>
        {''.join(item_rows_html)}
      </tbody>
    </table>

    <div class="check-notice">PLEASE CHECK EVERY ITEM RECEIVED IS COMPLETE</div>

    <div class="sig-grid-4">
      <div class="sig-box">
        <div class="sig-top">Checked by :<br>(Team IT)</div>
        <div class="sig-space"></div>
        <div class="sig-name">( {ts_signer} )</div>
      </div>
      <div class="sig-box">
        <div class="sig-top">Approved by :<br>(Admin IT)</div>
        {admin_sig_svg}
        <div class="sig-name">{admin_signer}</div>
      </div>
      <div class="sig-box">
        <div class="sig-top">Delivered :<br>(Driver/Distribusi)</div>
        <div class="sig-space"></div>
        <div class="sig-name">( ............................................... )</div>
      </div>
      <div class="sig-box">
        <div class="sig-top">Approved by :<br>(Staff Maintenance)</div>
        <div class="sig-space"></div>
        <div class="sig-name">( ............................................... )</div>
      </div>
    </div>

    <div class="sig-pic-box">
      <div>
        <div class="sig-pic-head">
          <b>Approved by</b>
          <span>Date Received : ............................</span>
        </div>
        <div>(PIC Store/User)</div>
      </div>
      <div class="sig-space"></div>
      <div>
        <div>( ............................................... )</div>
        <div>Authorized Signature</div>
      </div>
    </div>

    <div class="footer-note">
      <b>Note :</b> Mohon setelah barang diterima, tanda tangan tangan dibagian <i>Received By</i>, kemudian kirim kembali ke Divisi IT.
    </div>
  </div>
  {auto_js}
</body>
</html>"""
 return HTMLResponse(html, headers={'X-Frame-Options': 'SAMEORIGIN'})


class MutationInput(BaseModel):
 asset_id: int
 to_store_id: int
 notes: str = ''


@router.get('/mutations')
def list_mutations(u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 rows = s.query(AdoMutation).order_by(AdoMutation.id.desc()).limit(300).all()
 if u.role == 'ts':
  visible_ids = {st.id for st in visible_stores_query(s, u).all()}
  rows = [r for r in rows if r.from_store_id in visible_ids or r.to_store_id in visible_ids]
 return [{
  'id': r.id,
  'asset_id': r.asset_id,
  'from_store_id': r.from_store_id,
  'from_store_name': r.from_store_name,
  'to_store_id': r.to_store_id,
  'to_store_name': r.to_store_name,
  'device_name': r.device_name,
  'serial_number': r.serial_number,
  'moved_by': r.moved_by,
  'notes': r.notes,
  'moved_at': r.moved_at,
 } for r in rows]


@router.post('/mutations')
def create_mutation(v: MutationInput, u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 asset = s.get(AdoAsset, v.asset_id)
 if not asset:
  raise HTTPException(404, 'Perangkat tidak ditemukan')
 from_store = s.get(AdoStore, asset.store_id)
 to_store = s.get(AdoStore, v.to_store_id)
 if not to_store:
  raise HTTPException(404, 'Store tujuan tidak ditemukan')
 if not from_store or not can_access_store(u, from_store):
  raise HTTPException(403, 'Tidak memiliki akses mutasi dari store asal')
 if asset.store_id == v.to_store_id:
  raise HTTPException(422, 'Store tujuan harus berbeda dari store asal')
 mut = AdoMutation(
  asset_id=asset.id,
  from_store_id=from_store.id,
  from_store_name=f'{from_store.store_code} · {from_store.name}',
  to_store_id=to_store.id,
  to_store_name=f'{to_store.store_code} · {to_store.name}',
  device_name=asset.device_name,
  serial_number=asset.serial_number,
  moved_by=u.name,
  notes=v.notes.strip(),
  moved_at=now(),
 )
 asset.store_id = to_store.id
 asset.updated_at = now()
 s.add(mut)
 mut_desc = f'Mutasi dari {from_store.store_code} · {from_store.name} ke {to_store.store_code} · {to_store.name}' + (f' — {v.notes.strip()}' if v.notes.strip() else '')
 add_asset_log(s, asset.id, 'mutasi', mut_desc, u.name)
 s.commit()
 return {'ok': True, 'id': mut.id}


class AdoUserInput(BaseModel):
 name: str = Field(min_length=1, max_length=160)
 username: str = Field(min_length=1, max_length=120)
 password: str | None = None
 role: str
 active: bool = True
 store_ids: list[int] = []
 signature_data: str | None = None


@router.get('/users')
def list_ado_users(u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 sync_all_simon_users(s)
 users = s.query(AdoUser).order_by(AdoUser.name).all()
 if u.role != 'super_admin':
  return [{'id': x.id, 'name': x.name, 'username': x.username, 'role': x.role, 'active': bool(x.active), 'store_ids': [], 'has_signature': bool(x.signature_data)} for x in users if x.role == 'ts' and x.active]
 stores_by_ts = {}
 for st in s.query(AdoStore).all():
  if st.ts_user_id:
   stores_by_ts.setdefault(st.ts_user_id, []).append(st.id)
 return [{
  'id': x.id,
  'name': x.name,
  'username': x.username,
  'role': x.role,
  'active': bool(x.active),
  'store_ids': stores_by_ts.get(x.id, []),
  'has_signature': bool(x.signature_data),
  'signature_data': x.signature_data or '',
 } for x in users]


@router.post('/users')
def create_ado_user(v: AdoUserInput, u: AdoUser = Depends(ado_super_admin), s: Session = Depends(db)):
 if v.role not in ADO_ROLES:
  raise HTTPException(422, 'Role ADO tidak valid')
 if not v.password:
  raise HTTPException(422, 'Password wajib diisi')
 uname = v.username.strip()
 if s.query(AdoUser).filter_by(username=uname).first():
  raise HTTPException(409, 'Username sudah digunakan di ADO')
 x = AdoUser(
  name=v.name.strip(),
  username=uname,
  password=password(v.password),
  role=v.role,
  active=int(v.active),
  signature_data=sanitize_signature(v.signature_data),
 )
 s.add(x)
 s.flush()
 if v.role == 'ts' and v.store_ids:
  s.query(AdoStore).filter(AdoStore.id.in_(v.store_ids)).update({'ts_user_id': x.id}, synchronize_session=False)
 s.commit()
 return {'id': x.id}


@router.put('/users/{id}')
def update_ado_user(id: int, v: AdoUserInput, u: AdoUser = Depends(ado_super_admin), s: Session = Depends(db)):
 x = s.get(AdoUser, id)
 if not x:
  raise HTTPException(404, 'User tidak ditemukan')
 if v.role not in ADO_ROLES:
  raise HTTPException(422, 'Role ADO tidak valid')
 if x.id == u.id and (not v.active or v.role != 'super_admin'):
  raise HTTPException(409, 'Jangan nonaktifkan atau ubah role akun Super Admin sendiri')
 uname = v.username.strip()
 if s.query(AdoUser).filter(AdoUser.id != id, AdoUser.username == uname).first():
  raise HTTPException(409, 'Username sudah digunakan')
 x.name = v.name.strip()
 x.username = uname
 x.role = v.role
 x.active = int(v.active)
 if v.password:
  x.password = password(v.password)
 if v.signature_data is not None:
  x.signature_data = sanitize_signature(v.signature_data)
 if v.role == 'ts':
  s.query(AdoStore).filter_by(ts_user_id=x.id).update({'ts_user_id': None}, synchronize_session=False)
  if v.store_ids:
   s.query(AdoStore).filter(AdoStore.id.in_(v.store_ids)).update({'ts_user_id': x.id}, synchronize_session=False)
 s.commit()
 return {'ok': True}


@router.get('/reports/xlsx')
def export_ado_xlsx(u: AdoUser = Depends(ado_user), s: Session = Depends(db)):
 stores = visible_stores_query(s, u).all()
 store_map = {st.id: st for st in stores}
 ts_map = {x.id: x.name for x in s.query(AdoUser).all()}
 current_year = datetime.now(WIB).year

 wb = Workbook()
 wb.remove(wb.active)

 def style_header(ws, headers, widths):
  ws.append(headers)
  ws.freeze_panes = 'A2'
  for cell in ws[1]:
   cell.fill = PatternFill('solid', fgColor='145D59')
   cell.font = Font(name='Calibri', size=11, color='FFFFFF', bold=True)
   cell.alignment = Alignment(vertical='center', wrap_text=True)
  for idx, w in enumerate(widths, 1):
   ws.column_dimensions[ws.cell(1, idx).column_letter].width = w

 ws_assets = wb.create_sheet('Data Perangkat Store')
 style_header(ws_assets, ['Kode Store', 'Nama Store', 'Wilayah', 'TS', 'Grup', 'Kategori', 'Nama Perangkat', 'Merk', 'Serial Number', 'Tahun', 'Usia', 'Status', 'Keterangan'], [14, 30, 18, 22, 16, 18, 24, 18, 24, 10, 12, 14, 28])
 if store_map:
  for a in s.query(AdoAsset).filter(AdoAsset.store_id.in_(store_map.keys())).order_by(AdoAsset.store_id, AdoAsset.category).all():
   st = store_map.get(a.store_id)
   age = max(0, current_year - (a.purchase_year or current_year))
   ws_assets.append([
    st.store_code if st else '',
    st.name if st else '',
    st.region if st else '',
    ts_map.get(st.ts_user_id, 'Belum diassign') if st else '',
    a.group_type,
    a.category,
    a.device_name,
    a.brand,
    a.serial_number,
    a.purchase_year,
    f'{age} Tahun',
    a.status.upper(),
    a.notes,
   ])

 ws_do = wb.create_sheet('History DO')
 style_header(ws_do, ['Kode Permintaan (DO)', 'Tipe Store', 'Kode Store', 'Nama Store', 'Technical Support', 'Tanggal Permintaan', 'Status Konfirmasi', 'Dikonfirmasi Oleh', 'Kategori', 'Perangkat', 'Merk', 'Serial Number', 'Keterangan'], [22, 16, 14, 28, 22, 20, 18, 20, 16, 22, 18, 22, 26])
 if store_map:
  orders = s.query(AdoDeliveryOrder).filter(AdoDeliveryOrder.store_id.in_(store_map.keys())).order_by(AdoDeliveryOrder.id.desc()).all()
  for o in orders:
   st = store_map.get(o.store_id)
   req_dt = datetime.fromtimestamp(o.request_date, WIB).strftime('%d-%m-%Y %H:%M') if o.request_date else ''
   items = s.query(AdoDoItem).filter_by(do_id=o.id).all()
   for item in items:
    ws_do.append([
     o.do_number,
     o.store_type,
     st.store_code if st else '',
     st.name if st else '',
     o.ts_name,
     req_dt,
     'Terkonfirmasi' if o.status == 'confirmed' else 'Menunggu Konfirmasi',
     o.confirmed_by or '-',
     item.category,
     item.device_name,
     item.brand,
     item.serial_number,
     item.notes or o.notes,
    ])

 out = io.BytesIO()
 wb.save(out)
 wb.close()
 out.seek(0)
 filename = 'ADO-Asset-DO-' + datetime.now(WIB).strftime('%Y-%m-%d') + '.xlsx'
 return StreamingResponse(
  out,
  media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  headers={'Content-Disposition': f'attachment; filename="{filename}"'},
 )
