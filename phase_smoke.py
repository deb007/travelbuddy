from datetime import date
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import get_settings
from app.db.dal import Database
from app.models.expense import ExpenseIn
from app.services.rate_service import RateService
import sqlite3

settings = get_settings()
db = Database(settings.db_path)
if not db.get_trip_dates():
    db.set_trip_dates(date(2025,10,1), date(2025,10,20))

rs = RateService()

def add(amount, currency, d):
    e = ExpenseIn(amount=amount, currency=currency, category='other', description=None, date=d, payment_method='cash')
    if currency=='INR':
        inr = amount; rate = 1.0
    else:
        rate = rs.get_rate(currency); inr = rs.compute_inr(amount,currency)
    db.insert_expense_with_budget(e, inr, rate)

if len(db.list_expenses()) < 5:
    add(100,'INR',date(2025,9,29))
    add(200,'INR',date(2025,9,30))
    add(300,'INR',date(2025,10,1))
    add(400,'INR',date(2025,10,2))

app = create_app()
client = TestClient(app)
all_resp = client.get('/expenses').json()
pre_resp = client.get('/expenses?phase=pre-trip').json()
trip_resp = client.get('/expenses?phase=trip').json()
print('ALL', len(all_resp))
print('PRE', len(pre_resp), 'DATES', sorted({e['date'] for e in pre_resp}))
print('TRIP', len(trip_resp), 'DATES SAMPLE', sorted({e['date'] for e in trip_resp})[:5])

conn = sqlite3.connect(settings.db_path)
cur = conn.cursor(); cur.execute(" DELETE FROM metadata WHERE key in trip_start_date trip_end_date "); conn.commit(); conn.close()
pre_no = client.get('/expenses?phase=pre-trip').json()
trip_no = client.get('/expenses?phase=trip').json()
print('NO DATES PRE (expect 0):', len(pre_no))
print('NO DATES TRIP (expect ALL count):', len(trip_no))
