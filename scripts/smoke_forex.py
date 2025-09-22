from app.main import create_app
from fastapi.testclient import TestClient
from app.core.config import Settings
import tempfile
import os
import json


def run():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "test.db")
        settings = Settings(db_path=db_path)
        app = create_app(settings_override=settings)
        client = TestClient(app)

        results = {}
        results["list_empty"] = client.get("/forex-cards/").json()
        results["create_eur"] = client.put(
            "/forex-cards/eur", json={"loaded_amount": 500}
        ).json()
        results["update_eur"] = client.put(
            "/forex-cards/EUR", json={"loaded_amount": 800}
        ).json()
        neg_resp = client.put("/forex-cards/EUR", json={"loaded_amount": -10})
        results["negative_status"] = neg_resp.status_code
        results["negative_body"] = neg_resp.json()
        unsup_resp = client.put("/forex-cards/XYZ", json={"loaded_amount": 100})
        results["unsupported_status"] = unsup_resp.status_code
        results["unsupported_body"] = unsup_resp.json()
        results["final_list"] = client.get("/forex-cards/").json()
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run()
