import pytest
from scrapers.getCarScrapper import GetCarScrapper
class TestGetCarScrapper:
    
    @pytest.mark.asyncio
    async def test_get_cars(self):
        scrapper = GetCarScrapper("5142069161", None)
        cars = await scrapper.get_cars()
        
        assert len(cars) > 0