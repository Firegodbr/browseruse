from scrapers.getCarScrapper import GetCarScrapper
from scrapers.modelAppointmentScrapper import MakeAppointmentScrapper
from fastapi import APIRouter, HTTPException, Query
from models.schemas import AppointmentInfo, CarInfoResponse, AppointmentResponse
import logging
router = APIRouter(tags=["Scrapers"])
logger = logging.getLogger(__name__)

@router.get("/get_cars", summary="Scrape the SDSweb to get info of cars based on telephone number")
async def get_car_info_api(telephone: str = Query(..., example="5142069161", description="Customer telephone number")):
    """
    API endpoint to scrape SDSweb and get car info based on a telephone number.
    Example: GET /get_cars?telephone=5142069161
    """
    if not telephone.strip():
        raise HTTPException(status_code=400, detail="Telephone number is required")
    scrapper = GetCarScrapper(telephone)
    result = await scrapper.get_cars()
    return CarInfoResponse(message=result)

@router.post("/make_appointment", summary="Make a car appointment in SDSweb")
async def make_appointment_api(info: AppointmentInfo):
    """
    API endpoint to make appointments.
    """
    scrapper = MakeAppointmentScrapper(info)
    message = await scrapper.makeAppointment()
    return AppointmentResponse(message=message)