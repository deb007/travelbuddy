from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import get_settings
from app.db.dal import Database
from datetime import date, timedelta

settings = get_settings()
app = create_app()
client = TestClient(app)

db = Database(settings.db_path)
start = date.today()
end = start + timedelta(days=4)
db.set_trip_dates(start, end)
# Normalize INR budget
row = db.get_budget('INR')
if not row:
    db.set_budget_max('INR', 1000)
    db.increment_budget_spent('INR', 200)
else:
    db.set_budget_max('INR', 1000)
    current = db.get_budget('INR')['spent_amount']
    # Reset spent_amount via delta logic
    if abs(current - 200) > 1e-6:
        db.update_budget_delta('INR', -current)
        db.increment_budget_spent('INR', 200)

resp = client.get('/analytics/remaining-daily-budget')
print('Status:', resp.status_code)
print('Response:', resp.json())
