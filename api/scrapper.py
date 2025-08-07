from scrapers.getCarScrapper import GetCarScrapper
from scrapers.modelAppointmentScrapper import MakeAppointmentScrapper
from fastapi import APIRouter, HTTPException, Query, Depends
from models.schemas import AppointmentInfo, CarInfoResponse, AppointmentResponse, AppointmentAvailability, AppointmentAvailabilityApi
from scrapers.availabilityScrapper import AvailabilityScrapper
import logging
from sqlalchemy.orm import Session
import db.database_availability as db_availability
from datetime import datetime
router = APIRouter(tags=["Scrapers"])
logger = logging.getLogger(__name__)


@router.get("/get_cars", summary="Scrape the SDSweb to get info of cars based on telephone number")
async def get_car_info_api(telephone: str = Query(..., example="5142069161", description="Customer telephone number")):
    """
    API endpoint to scrape SDSweb and get car info based on a telephone number.
    Example: GET /get_cars?telephone=5142069161
    """
    if not telephone.strip():
        raise HTTPException(
            status_code=400, detail="Telephone number is required")
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
    timeframe: str = Query(..., example="14:00-16:00",
                           description="Appointment timeframe"),
    weekdays: str = Query(..., example="Monday,Tuesday",
                          description="Days of the week")
):
    """
    API endpoint to get available appointments.
    Example: GET /check_availability?timeframe=14:00-16:00&days=Monday,Tuesday
    """
    # Convert the `days` string into a list of days
    days_list = weekdays.split(",")
    # Get the start and end times from the `timeframe`
    try:
        start_time_str, end_time_str = timeframe.split("-")
        start_time = datetime.strptime(start_time_str, "%H:%M").time()
        end_time = datetime.strptime(end_time_str, "%H:%M").time()
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid timeframe format. Use HH:MM-HH:MM.")
    check_values = AppointmentAvailabilityApi(timeframe=timeframe, days=days_list)

    # Use asyncio.gather to run multiple scrapers concurrently
    available_appointments = db_availability.get_available_appointments(
        check_values, start_time, end_time)
    return available_appointments


@router.get('/add_availabilities', summary="Add availability to database")
async def add_availabilities_api(db: Session = Depends(db_availability.get_session)):
    """
    Endpoint to scrape availability data and update the database.
    This endpoint scrapes availability for a set number of weeks, processes the data, and updates the DB.
    """
    # Define days of the week and the timeframe to be used in the availability query
    days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    timeframe = "06:45-17:00"

    # Create an AppointmentAvailability object with required details
    check_values = AppointmentAvailability(
        telephone="5142433043",  # Placeholder for a phone number, adjust accordingly
        timeframe=timeframe,
        days=days_list,
        number_of_weeks=3
    )

    try:
        # Fetch availability data
        data = await AvailabilityScrapper(check_values).get_availability()

        # If no data is returned, raise an error
        if not data:
            raise HTTPException(
                status_code=404, detail="No availability data found")

        # Process and update the database with the fetched schedule data
        db_availability.process_schedule_data(db, data)

        return {"message": "Availability successfully added to the database"}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
