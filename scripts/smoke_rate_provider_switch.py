import os
import tempfile
import json
from datetime import date
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Settings
from app.models.expense import ExpenseIn

"""Smoke test for T07.01 provider switch.
Creates one SGD expense under 'static' provider and one under 'external-placeholder'
with same original amount to show differing exchange_rate and inr_equivalent.
"""


def run():
    with tempfile.TemporaryDirectory() as d:
        # Static provider
        settings_static = Settings(
            db_path=os.path.join(d, "s1.db"), exchange_rate_provider="static"
        )
        app_static = create_app(settings_override=settings_static)
        client_static = TestClient(app_static)
        e = ExpenseIn(
            amount=1,
            currency="SGD",
            category="other",
            description=None,
            date=date.today(),
            payment_method="cash",
        )
        resp_static = client_static.post("/expenses/", json=json.loads(e.json()))

        # External placeholder provider
        settings_ext = Settings(
            db_path=os.path.join(d, "s2.db"),
            exchange_rate_provider="external-placeholder",
        )
        app_ext = create_app(settings_override=settings_ext)
        client_ext = TestClient(app_ext)
        resp_ext = client_ext.post("/expenses/", json=json.loads(e.json()))

        print(
            json.dumps(
                {
                    "static_provider_expense": resp_static.json(),
                    "external_placeholder_expense": resp_ext.json(),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    run()
