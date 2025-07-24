from pydantic import BaseModel, Field
from typing import  Optional, List
import strawberry
from enum import Enum
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
class CarInfoResponse(BaseModel):
    message: List[dict]|str
class AppointmentResponse(BaseModel):
    message: str