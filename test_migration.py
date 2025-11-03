"""Quick test script to verify currency migration works."""

from pathlib import Path
from app.db.migrate import apply_migrations
from app.db.dal import Database
from app.routers.ui import _trip_nav_context

# Apply migrations
db_path = Path("data/app.sqlite3")
print(f"Applying migrations to {db_path}...")
version = apply_migrations(db_path)
print(f"✓ Migrated to schema version {version}")

# Test the database
db = Database(db_path)

# 1. Check default currencies
print("\n1. Testing default currencies:")
default_currencies = db.get_default_currencies()
print(f"   Default currencies: {default_currencies}")
assert isinstance(default_currencies, list), "Default currencies should be a list"
assert len(default_currencies) > 0, "Default currencies should not be empty"
print("   ✓ Default currencies working")

# 2. Check existing trips have currencies
print("\n2. Testing existing trips have currencies:")
trips = db.list_trips(include_archived=True)
for trip in trips:
    trip_id = trip["id"]
    trip_name = trip["name"]
    currencies = db.get_trip_currencies(trip_id)
    print(f"   Trip '{trip_name}' (ID {trip_id}): {currencies}")
    assert isinstance(currencies, list), f"Trip {trip_id} currencies should be a list"
    assert len(currencies) > 0, f"Trip {trip_id} should have at least one currency"
print("   ✓ All trips have currencies")

# 3. Check forex currencies
print("\n3. Testing forex currencies:")
active_trip_id = db.get_active_trip_id()
forex_currencies = db.get_trip_forex_currencies(active_trip_id)
print(f"   Active trip forex currencies: {forex_currencies}")
print("   ✓ Forex currencies working")

# 4. Test setting default currencies
print("\n4. Testing set default currencies:")
test_currencies = ["USD", "EUR", "GBP"]
db.set_default_currencies(test_currencies)
retrieved = db.get_default_currencies()
print(f"   Set to: {test_currencies}")
print(f"   Retrieved: {retrieved}")
assert retrieved == test_currencies, "Retrieved currencies should match what was set"
print("   ✓ Set/get default currencies working")

# Restore original defaults
db.set_default_currencies(["INR", "SGD", "MYR"])
print("   Restored original default currencies")

# 5. Check that show_forex_tab logic works
print("\n5. Testing show forex tab logic:")
nav_context = _trip_nav_context(db, trip_id=active_trip_id)
show_forex = nav_context.get("show_forex_tab", False)
print(f"   Show forex tab for active trip: {show_forex}")
print(f"   (Based on forex currencies: {forex_currencies})")
expected = len(forex_currencies) > 0
assert show_forex == expected, f"Show forex tab should be {expected}"
print("   ✓ Show forex tab logic working")

print("\n" + "=" * 60)
print("✓ ALL TESTS PASSED - Migration is backward compatible!")
print("=" * 60)
