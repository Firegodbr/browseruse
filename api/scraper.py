from scrapers.getCar import get_cars
from scrapers.makeAppointment import making_appointment
from helpers.function import normalize_canadian_number
from fastapi import APIRouter, HTTPException
from models.schemas import AppointmentInfo
import logging
router = APIRouter(tags=["Scrapers"])
logger = logging.getLogger(__name__)

@router.get("/get_cars", summary="Scrape the SDSweb to get info of cars base on telephone number")
async def get_car_info_api(search_json_string: str):
    """
    API endpoint to scrape the SDSweb to get info of cars.
    Example: GET /get_cars?search_json_string=<search_info_string>
    Format of params: 
    search_json_string: {"telephone": "5142069161"}
    """
    if search_json_string == None or search_json_string == "":
        return {"message": "No data sent"}
    tel = search_json_string
    # result = await get_cars(json.loads(search_json_string))
    result = await get_cars(normalize_canadian_number(tel))
    return {"web_scrape_info": result}

# @router.post("/make_appointment",tags=["make_appointment"], summary="Make a car appointment in SDSweb")
# async def make_appointment_api(info: AppointmentInfo):
#     """
#     API endpoint to make appointments.
    
#     Example: 
#     POST /make_appointment
#     Format of params: 
#     {
#         "service_id": "01TZZ1S16Z",
#         "car": "AUDI Q5 2016",
#         "telephone": "5145856444",
#         "date": "2025-05-01T15:00:00",
#         "transport_mode": "Reconduire"
#     }
#     """
#     if not info.service_id:
#         raise HTTPException(status_code=400, detail="Service number is required.")
#     if not info.car:
#         raise HTTPException(status_code=400, detail="Car name is required.")
#     if not info.telephone:
#         raise HTTPException(status_code=400, detail="Telephone number is required.")
#     if not info.date:
#         raise HTTPException(status_code=400, detail="Date is required.")
#     if not info.transport_mode:
#         raise HTTPException(status_code=400, detail="Transport mode is required.")
#     return await making_appointment(info)
    