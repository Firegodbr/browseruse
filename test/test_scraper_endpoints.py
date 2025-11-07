from fastapi.testclient import TestClient
from app import app
import pytest

@pytest.fixture
def client():
    return TestClient(app)
class TestEndpoints:
    def test_get_all_cars(self, client: TestClient):
        response = client.get("/scraper/get_cars?telephone=5142069161")
        assert response.status_code == 200

