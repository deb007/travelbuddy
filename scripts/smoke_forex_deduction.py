import os
import tempfile
import json
from datetime import date
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Settings
from app.models.expense import ExpenseIn


def run():
    with tempfile.TemporaryDirectory() as d:
        settings = Settings(db_path=os.path.join(d, "test.db"))
        app = create_app(settings_override=settings)
        client = TestClient(app)
        # Direct Database handle not required for this smoke test; using API routes

        # 1. Load forex card (SGD)
        client.put("/forex-cards/SGD", json={"loaded_amount": 1000})

        # 2. Create forex expense SGD 200
        e1 = ExpenseIn(
            amount=200,
            currency="SGD",
            category="other",
            description=None,
            date=date.today(),
            payment_method="forex",
        )
        client.post("/expenses/", json=json.loads(e1.json()))

        # 3. Create non-forex expense SGD 50 (cash) -> should NOT affect forex spent
        e2 = ExpenseIn(
            amount=50,
            currency="SGD",
            category="other",
            description=None,
            date=date.today(),
            payment_method="cash",
        )
        client.post("/expenses/", json=json.loads(e2.json()))

        # 4. Patch first expense from 200 -> 250 (forex) delta +50
        # fetch list, find id of forex expense
        expenses = client.get("/expenses").json()
        forex_exp = next(
            e
            for e in expenses
            if e["payment_method"] == "forex" and e["currency"] == "SGD"
        )
        client.patch(f"/expenses/{forex_exp['id']}", json={"amount": 250})

        # 5. Patch forex -> cash (should subtract 250 from forex spent)
        client.patch(f"/expenses/{forex_exp['id']}", json={"payment_method": "cash"})

        # 6. Create new cash expense then patch to forex 80 (adds 80)
        e3 = ExpenseIn(
            amount=80,
            currency="SGD",
            category="other",
            description=None,
            date=date.today(),
            payment_method="cash",
        )
        resp = client.post("/expenses/", json=json.loads(e3.json()))
        e3_id = resp.json()["id"]
        client.patch(f"/expenses/{e3_id}", json={"payment_method": "forex"})

        # 7. Delete the patched (now forex 80) -> subtract 80
        client.delete(f"/expenses/{e3_id}")

        # Inspect final forex card state
        forex_cards = client.get("/forex-cards/").json()
        sgd_card = next(c for c in forex_cards if c["currency"] == "SGD")

        print(
            json.dumps(
                {
                    "sgd_card_final": sgd_card,
                    "all_expenses": client.get("/expenses").json(),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    run()
