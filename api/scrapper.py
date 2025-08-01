from scrapers.getCarScrapper import GetCarScrapper
from scrapers.modelAppointmentScrapper import MakeAppointmentScrapper
from fastapi import APIRouter, HTTPException, Query
from models.schemas import AppointmentInfo, CarInfoResponse, AppointmentResponse, AppointmentAvailability
from scrapers.availabilityScrapper import AvailabilityScrapper
import logging
import asyncio
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


@router.get("/check_availability", summary="Get available appointments for a customer")
async def get_appointments_api(
    timeframe: str = Query(..., example="14:00-16:00", description="Appointment timeframe"),
    weekdays: str = Query(..., example="Monday,Tuesday", description="Days of the week"),
    number_of_weeks: int = Query(..., example="1", description="How many weeks to check"),
):
    """
    API endpoint to get available appointments.
    Example: GET /check_availability?timeframe=14:00-16:00&days=Monday,Tuesday&number_of_weeks=1
    """
    # Convert the `days` string into a list of days
    days_list = weekdays.split(",")
    check_values = AppointmentAvailability(telephone="5142433043", timeframe=timeframe, days=days_list, number_of_weeks=number_of_weeks)

    # Use asyncio.gather to run multiple scrapers concurrently
    available_appointments = await AvailabilityScrapper(check_values).get_availability()
    return available_appointments