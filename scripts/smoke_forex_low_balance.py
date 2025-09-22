import os
import tempfile
import json
from datetime import date
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Settings
from app.models.expense import ExpenseIn

"""Smoke test for T06.04 low balance flag.
Scenario:
1. Load SGD 1000
2. Spend 700 forex (30% remaining -> not low)
3. Spend additional 110 forex (remaining 190 -> 19% -> low)
4. Delete last 110 expense (remaining back to 300 -> 30% -> not low)
"""


def run():
    with tempfile.TemporaryDirectory() as d:
        settings = Settings(db_path=os.path.join(d, "test.db"))
        app = create_app(settings_override=settings)
        client = TestClient(app)

        client.put("/forex-cards/SGD", json={"loaded_amount": 1000})

        def make_exp(amount):
            return ExpenseIn(
                amount=amount,
                currency="SGD",
                category="other",
                description=None,
                date=date.today(),
                payment_method="forex",
            )

        # Spend 700
        e1 = make_exp(500)
        client.post("/expenses/", json=json.loads(e1.json()))
        e2 = make_exp(200)
        client.post("/expenses/", json=json.loads(e2.json()))

        # Spend 110 (cross below 20%)
        e3 = make_exp(110)
        resp = client.post("/expenses/", json=json.loads(e3.json()))
        e3_id = resp.json()["id"]

        def card():
            return next(
                c for c in client.get("/forex-cards/").json() if c["currency"] == "SGD"
            )

        state_after_910 = card()

        # Delete 110 expense -> should move above threshold again
        client.delete(f"/expenses/{e3_id}")
        state_after_delete = card()

        print(
            json.dumps(
                {
                    "after_910_spent": state_after_910,
                    "after_delete": state_after_delete,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    run()
