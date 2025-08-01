from pydantic import BaseModel, Field, field_validator
from typing import  Optional, List
import strawberry
from enum import Enum
import re

class TransportModeEnum(str, Enum):
    aucun = "aucun"
    courtoisie = "courtoisie"
    attente = "attente"
    reconduire = "reconduire"
    laisser = "laisser"

@strawberry.input
class AppointmentInfoQL:
    service_id: str  # Use camelCase
    car: Optional[str] = None
    telephone: str
    date: str
    transport_mode: TransportModeEnum 

class AppointmentInfo(BaseModel):
    service_id: str = Field(..., example="01TZZ1S16Z", description="Unique service identifier")
    car: Optional[str] = Field(None, example="TOYOTA RAV4 2022", description="Car make and model (optional)")
    telephone: str = Field(..., example="5142069161", description="Customer telephone number")
    date: str = Field(..., example="2026-05-04T15:00:00", description="Appointment date and time")
    transport_mode: TransportModeEnum


class AppointmentAvailability(BaseModel):
    telephone: str
    timeframe: str
    days: List[str]
    number_of_weeks: int

    @field_validator('timeframe')
    def validate_time_format(cls, v):
        # Time format: HH:MM-HH:MM
        if not re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", v):
            raise ValueError("Invalid time format. Use HH:MM-HH:MM.")
        start_time, end_time = v.split("-")
        start_hour, start_minute = map(int, start_time.split(":"))
        end_hour, end_minute = map(int, end_time.split(":"))
        
        # Check if the start time is earlier than the end time
        if (start_hour > end_hour) or (start_hour == end_hour and start_minute >= end_minute):
            raise ValueError("Start time must be earlier than end time.")
        
        return v




class CarInfoResponse(BaseModel):
    message: List[dict]|str
class AppointmentResponse(BaseModel):
    message: str