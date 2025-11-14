import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


class TestScraperEndpoints(unittest.TestCase):

    @patch("api.scrapper.GetCarScrapper")
    def test_get_cars_success(self, mock_scraper):
        """Test /scraper/get_cars with valid telephone."""
        mock_scraper.return_value.get_cars = AsyncMock(return_value="Car info result")

        response = client.get("/scraper/get_cars?telephone=5149661015")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Car info result", response.text)

    def test_get_cars_missing_telephone(self):
        """Test /scraper/get_cars missing telephone."""
        response = client.get("/scraper/get_cars?telephone=")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Telephone number is required", response.text)
    @patch("api.scrapper.MakeAppointmentScrapper")
    def test_make_appointment_success(self, mock_scraper):
        """Test /scraper/make_appointment with valid input."""
        mock_scraper.return_value.makeAppointment = AsyncMock(
            return_value={"message": "Appointment created", "id": 123}
        )

        response = client.post("/scraper/make_appointment", json={
            "service_id": "01TZZ1S16Z",
            "car": "TOYOTA RAV4 2022",
            "telephone": "5142069161",
            "date": "2026-05-04T15:00:00",
            "transport_mode": "courtoisie"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Appointment created")

    @patch("api.scrapper.MakeAppointmentScrapper")
    def test_make_appointment_failure(self, mock_scraper):
        """Test /scraper/make_appointment with scraper error."""
        mock_scraper.return_value.makeAppointment = AsyncMock(
            return_value={"error": "Something failed", "message": "Invalid data"}
        )

        response = client.post("/scraper/make_appointment", json={
            "service_id": "01TZZ1S16Z",
            "car": "TOYOTA RAV4 2022",
            "telephone": "5142069161",
            "date": "2026-05-04T15:00:00",
            "transport_mode": "courtoisie"
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid data", response.text)

    # @patch("api.scrapper.db_availability.insert_call_log_db")
    # @patch("api.scrapper.db_availability.get_session")
    # def test_call_log_success(self, mock_session, mock_insert):
    #     """Test /scraper/call_log inserts successfully."""
    #     mock_db = MagicMock()
    #     mock_session.return_value = mock_db
    #     mock_db.query.return_value.filter.return_value.first.return_value = True

    #     response = client.post("/scraper/call_log", json={
    #         "telephone": "5149661015",
    #         "time": "1131421341",
    #         "status": "completed call",
    #         "error": None,
    #         "appointment_id": 1
    #     })

    #     self.assertEqual(response.status_code, 200)
    #     self.assertIn("Call log added", response.text)

    # @patch("api.scrapper.db_availability.get_session")
    # def test_call_log_appointment_not_found(self, mock_session):
    #     """Test /scraper/call_log when appointment not found."""
    #     mock_db = MagicMock()
    #     mock_session.return_value = mock_db
    #     mock_db.query.return_value.filter.return_value.first.return_value = None

    #     response = client.post("/scraper/call_log", json={
    #         "telephone": "5149661015",
    #         "time": "1131421341",
    #         "status": "not completed call",
    #         "error": None,
    #         "appointment_id": 999
    #     })
    #     self.assertEqual(response.status_code, 400)
    #     self.assertIn("Appointment not found", response.text)



if __name__ == "__main__":
    unittest.main()
