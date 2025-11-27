from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Annotated, List
from datetime import datetime
import strawberry
from enum import StrEnum
import re


class CallLogCreate(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "telephone": "1234567890",
                "time": "1131421341",
                "status": "not completed call",
                "error": None,
            }
        },
    )

    telephone: Annotated[str, Field(description="Customer telephone number")]
    name: Annotated[Optional[str], Field(default=None, description="Customer name (optional)")]
    time: Annotated[str, Field(description="Call timestamp or time string")]
    status: Annotated[str, Field(description="Status of the call")]
    error: Annotated[Optional[str], Field(default=None, description="Error message if any")]
    appointment_id: Annotated[Optional[int], Field(default=None, description="Associated appointment ID")]

class FeedbackCreate(BaseModel):
    feedback: Annotated[str, Field(description="Customer feedback")]
    phone_number: Annotated[str, Field(description="Customer phone number")]

class TransportModeEnum(StrEnum):  # StrEnum ensures JSON-friendly string behavior
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
    service_id: Annotated[
        str,
        Field(
            description="Unique service identifier",
            json_schema_extra={"example": "01TZZ1S16Z"}
        )
    ]

    car: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Car make and model (optional)",
            json_schema_extra={"example": "TOYOTA RAV4 2022"}
        )
    ]

    telephone: Annotated[
        str,
        Field(
            description="Customer telephone number",
            json_schema_extra={"example": "5142069161"}
        )
    ]

    date: Annotated[
        datetime,
        Field(
            description="Appointment date and time",
            json_schema_extra={"example": "2026-05-04T15:00:00"}
        )
    ]

    transport_mode: "TransportModeEnum"




class AppointmentAvailabilityApi(BaseModel):
    timeframe: str
    days: List[str]



class AppointmentAvailability(BaseModel):
    telephone: Annotated[str, Field(description="Customer telephone number")]
    timeframe: Annotated[str, Field(description="Time slot (HH:MM-HH:MM)")]
    days: Annotated[List[str], Field(description="List of available days")]
    number_of_weeks: Annotated[int, Field(description="Number of weeks ahead for availability")]

    @field_validator('timeframe')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        # Time format: HH:MM-HH:MM
        if not re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", v):
            raise ValueError("Invalid time format. Use HH:MM-HH:MM.")
        start_time, end_time = v.split("-")
        start_hour, start_minute = map(int, start_time.split(":"))
        end_hour, end_minute = map(int, end_time.split(":"))

        if (start_hour > end_hour) or (start_hour == end_hour and start_minute >= end_minute):
            raise ValueError("Start time must be earlier than end time.")
        return v


# Response routes
class CarInfoResponse(BaseModel):
    message: Annotated[List[dict] | str, Field(description="Car information or message")]


class AppointmentResponse(BaseModel):
    message: Annotated[str, Field(description="Response message")]
    appointment_id: Annotated[int, Field(description="Appointment ID")]


class ServiceSchema(BaseModel):
    timestamp: Annotated[str, Field(description="Timestamp of the service event")]
    service: Annotated[str, Field(description="Service type or name")]
    kilometers: Annotated[int, Field(description="Car mileage in kilometers")]
