import os, sys, tempfile, json
from datetime import date
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Settings
from app.models.expense import ExpenseIn

"""Smoke test for T07.02 external-http provider.
Creates an SGD expense under static provider and under external-http provider
showing (likely) different exchange_rate or verifying graceful fallback.
"""


def run():
    with tempfile.TemporaryDirectory() as d:
        s_static = Settings(
            db_path=os.path.join(d, "static.db"), exchange_rate_provider="static"
        )
        app_static = create_app(settings_override=s_static)
        c_static = TestClient(app_static)
        payload = ExpenseIn(
            amount=10,
            currency="SGD",
            category="other",
            description=None,
            date=date.today(),
            payment_method="cash",
        )
        r_static = c_static.post("/expenses/", json=json.loads(payload.json()))

        s_http = Settings(
            db_path=os.path.join(d, "http.db"), exchange_rate_provider="external-http"
        )
        app_http = create_app(settings_override=s_http)
        c_http = TestClient(app_http)
        r_http = c_http.post("/expenses/", json=json.loads(payload.json()))

        print(
            json.dumps(
                {"static": r_static.json(), "external_http": r_http.json()}, indent=2
            )
        )


if __name__ == "__main__":
    sys.path.append(os.getcwd())
    run()
