from datetime import date
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Settings
from app.db.dal import Database
from app.models.expense import ExpenseIn
from app.services.rate_service import RateService
import os, tempfile, sqlite3
from app.db.schema import init_db

# Use temp DB to isolate
fd, temp_path = tempfile.mkstemp(suffix='.db'); os.close(fd)
settings = Settings(db_filename=temp_path.split(os.sep)[-1], data_dir=os.path.dirname(temp_path))
# Initialize schema
init_db(settings.db_path)

db = Database(settings.db_path)
rs = RateService()

# Set trip dates
start = date(2025,10,1); end = date(2025,10,20)
db.set_trip_dates(start, end)

# Insert 2 pre-trip and 2 trip expenses
pre_dates = [date(2025,9,29), date(2025,9,30)]
trip_dates = [date(2025,10,1), date(2025,10,2)]

for idx,d in enumerate(pre_dates+trip_dates, start=1):
    e = ExpenseIn(amount=100*idx, currency='INR', category='other', description=None, date=d, payment_method='cash')
    db.insert_expense_with_budget(e, e.amount, 1.0)

# Build app with custom settings injection by temporarily overriding env var
os.environ['DB_FILENAME'] = settings.db_filename
app = create_app()
client = TestClient(app)

all_resp = client.get('/expenses').json()
pre_resp = client.get('/expenses?phase=pre-trip').json()
trip_resp = client.get('/expenses?phase=trip').json()
print('ALL total', len(all_resp))
print('PRE total', len(pre_resp), 'dates', sorted({e['date'] for e in pre_resp}))
print('TRIP total', len(trip_resp), 'dates', sorted({e['date'] for e in trip_resp}))

# Remove trip dates & test semantics
conn = sqlite3.connect(settings.db_path)
cur = conn.cursor(); cur.execute( DELETE FROM metadata WHERE key in trip_start_date trip_end_date ); conn.commit(); conn.close()
pre_no = client.get('/expenses?phase=pre-trip').json()
trip_no = client.get('/expenses?phase=trip').json()
print('NO DATES pre-trip count (expect 0):', len(pre_no))
print('NO DATES trip count (expect ALL):', len(trip_no))
