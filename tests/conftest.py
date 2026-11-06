"""Every pytest run uses a disposable DB; integration cases do not share records."""
import os,tempfile
from pathlib import Path
import pytest
os.environ['SIAMS_DATA']=tempfile.mkdtemp(prefix='simon-tests-')
os.environ.pop('DATABASE_URL',None)

@pytest.fixture(autouse=True)
def isolated_database():
 from backend.main import engine,Base,DATA,attempts
 assert DATA.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()), 'Refusing to clear a non-test database'
 with engine.begin() as connection:
  for table in reversed(Base.metadata.sorted_tables):connection.execute(table.delete())
 attempts.clear()
 yield
