from pydantic import BaseModel, Field
from typing import Literal, Optional, List
class AppointmentInfo(BaseModel):
    service_id: str = Field(..., example="01TZZ1S16Z", description="Unique service identifier")
    car: Optional[str] = Field(None, example="TOYOTA RAV4 2022", description="Car make and model (optional)")
    telephone: str = Field(..., example="5142069161", description="Customer telephone number")
    date: str = Field(..., example="2026-05-01T15:00:00", description="Appointment date and time")
    transport_mode: Literal["aucun", "courtoisie", "attente", "reconduire", "laisser"] = Field(
        ..., example="reconduire", description="Mode of transport"
    )
class CarInfoResponse(BaseModel):
    message: List[str]
class AppointmentResponse(BaseModel):
    message: str