from datetime import date
import os
import sys
import sqlite3
import tempfile

# Establish isolated temp directory and set env BEFORE importing settings
TEMP_DIR = tempfile.mkdtemp(prefix="phase_test_")
os.environ["DATA_DIR"] = TEMP_DIR
os.environ["DB_FILENAME"] = "test.sqlite3"

# Ensure project root on path when executed directly
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient
from app.main import create_app
from app.db.schema import init_db
from app.core.config import Settings
from app.db.dal import Database
from app.models.expense import ExpenseIn

# Create fresh Settings instance (not cached) and init DB
settings = Settings()
settings.init_post_load()
init_db(settings.db_path)

db = Database(settings.db_path)

# Seed trip dates
trip_start = date(2025, 9, 1)
trip_end = date(2025, 9, 20)
db.set_trip_dates(trip_start, trip_end)

# Insert deterministic expenses: 2 pre-trip, 2 trip
entries = [
    (date(2025, 8, 25), 100),  # pre-trip
    (date(2025, 8, 28), 200),  # pre-trip
    (date(2025, 9, 1), 300),  # trip start
    (date(2025, 9, 2), 400),  # trip
]
for d, amt in entries:
    e = ExpenseIn(
        amount=amt,
        currency="INR",
        category="other",
        description=None,
        date=d,
        payment_method="cash",
    )
    db.insert_expense_with_budget(e, amt, 1.0)

app = create_app(settings_override=settings)
client = TestClient(app)

all_resp = client.get("/expenses").json()
pre_resp = client.get("/expenses", params={"phase": "pre-trip"}).json()
trip_resp = client.get("/expenses", params={"phase": "trip"}).json()

print("ALL count", len(all_resp))
print("PRE count", len(pre_resp), "dates", sorted({e["date"] for e in pre_resp}))
print("TRIP count", len(trip_resp), "dates", sorted({e["date"] for e in trip_resp}))

# Remove trip dates to exercise option A semantics
conn = sqlite3.connect(settings.db_path)
cur = conn.cursor()
cur.execute("DELETE FROM metadata WHERE key in ('trip_start_date','trip_end_date')")
conn.commit()
conn.close()

pre_no = client.get("/expenses", params={"phase": "pre-trip"}).json()
trip_no = client.get("/expenses", params={"phase": "trip"}).json()
print("NO DATES pre-trip count (expect 0):", len(pre_no))
print("NO DATES trip count (expect ALL):", len(trip_no))

# Basic assertions (will raise if mismatch)
assert len(pre_resp) == 2, f"expected 2 pre-trip got {len(pre_resp)}"
assert len(trip_resp) == 2, f"expected 2 trip got {len(trip_resp)}"
assert len(pre_no) == 0, "pre-trip should be empty when trip dates unset"
assert len(trip_no) == len(all_resp), "trip should return all when dates unset"
print("Phase filter smoke test: PASS")
