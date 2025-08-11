# database_ops.py

from pathlib import Path
from sqlmodel import SQLModel, Field, create_engine, Session, Relationship, select
from typing import Optional, List, Dict, Any
import json
import sqlite3
import os

DB_FILE = "./db.sqlite"
DATABASE_URL = f"sqlite:///{DB_FILE}"
engine = create_engine(DATABASE_URL, echo=False)
def get_session():
    return Session(engine)
# --- SQLModel Models ---


class Transport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(index=True, unique=True, max_length=25)
    description: str

    appointments: List["Appointment"] = Relationship(
        back_populates="transport")


class Appointment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_id: str
    telephone: str = Field(index=True, max_length=15)
    transport_id: Optional[int] = Field(
        default=None, foreign_key="transport.id")
    date: str = Field(index=True)  # ISO format: YYYY-MM-DDTHH:MM:SS
    car: Optional[str] = None

    transport: Optional[Transport] = Relationship(
        back_populates="appointments")


class OilLookup(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True, )
    model: str
    engine_type: str
    year: int
    oil_type: str
    is_suv: bool
    cylinders: int


class ServiceMapping(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True, )
    oil_type: str
    is_suv: bool
    cylinders: int
    service_id: str
    processing_time_min: int
    description: str


# --- DB Initialization Function ---
def create_db():
    """
    Creates the SQLite database and initializes tables using SQLModel.
    Equivalent to the original sqlite3 schema creation.
    """
    if not os.path.exists(DB_FILE):
        print("Creating new database...")
    else:
        print("Verifying/Updating existing database...")

    SQLModel.metadata.create_all(engine)
    print(f"Database '{DB_FILE}' initialized/verified successfully.")


def add_data_default_db():
    """Insert default data into SERVICE, TRANSPORT, and oil reference tables using SQLModel."""
    TOYOTA_OIL_JSON = Path("./Toyota Oil v5.json")
    SERVICE_ID_JSON = Path("./codes travail toyota.json")

    try:
        with get_session() as session:
            # --- Add Default Transport Options ---
            # existing_transport = session.exec(select(Transport)).first()
            # if not existing_transport:
            #     transport_data = [
            #         Transport(
            #             type="aucun", description="No transport needed, customer has arrangements"),
            #         Transport(type="courtoisie",
            #                   description="Rental car required/arranged"),
            #         Transport(type="attente",
            #                   description="Customer will wait at the facility"),
            #         Transport(type="reconduire",
            #                   description="Shuttle service to local area"),
            #         Transport(type="laisser",
            #                   description="Customer will drop off the vehicle"),
            #     ]
            #     session.add_all(transport_data)
            #     print("Added default data to TRANSPORT table.")

            # --- Load and insert Toyota Oil data ---
            if TOYOTA_OIL_JSON.exists() and SERVICE_ID_JSON.exists():
                with TOYOTA_OIL_JSON.open("r", encoding="utf-8") as f:
                    oil_data = json.load(f)

                with SERVICE_ID_JSON.open("r", encoding="utf-8") as f:
                    service_id_data = json.load(f)

                # Insert into OilLookup
                for entry in oil_data:
                    model = entry["Model"]
                    engine = entry["Engine Type"]
                    is_suv = entry["Is SUV"]
                    cylinders = entry["Number of Cylinders"]
                    oil_types = entry["Oil Type"]
                    if not isinstance(oil_types, list):
                        oil_types = [oil_types]
                    for year in entry["Years"]:
                        for oil in oil_types:
                            oil_entry = OilLookup(
                                model=model.upper(),
                                engine_type=engine.upper(),
                                year=year,
                                oil_type=oil.upper(),
                                is_suv=is_suv,
                                cylinders=cylinders
                            )
                            session.add(oil_entry)

                # Insert into ServiceMapping
                for cyl_key, oil_map in service_id_data["cylinder_types"].items():
                    if "-SUV" in cyl_key:
                        cyl = int(cyl_key.split("-")[0])
                        is_suv = True
                    else:
                        cyl = int(float(cyl_key))  # e.g., "6.0" → 6
                        is_suv = False

                    for oil_type, service_info in oil_map.items():
                        try:
                            service_id = service_info["id"]
                            processing_time = int(
                                service_info["process-time-minutes"])
                        except (KeyError, TypeError, ValueError) as e:
                            print(
                                f"Error parsing service info for {cyl_key} / {oil_type}: {e}")
                            continue

                        service_mapping = ServiceMapping(
                            oil_type=oil_type.upper(),
                            is_suv=is_suv,
                            cylinders=cyl,
                            service_id=service_id,
                            processing_time_min=processing_time,
                            description=""  # Optional: add description logic here if needed
                        )
                        session.add(service_mapping)

                print("Toyota oil data added to database.")
            else:
                print(
                    f"JSON file(s) not found: {TOYOTA_OIL_JSON} or {SERVICE_ID_JSON}")

            session.commit()
    except Exception as ex:
        print(f"Error adding default data: {ex}")
    print("Default data added to database.")

# --- Service Queries ---
def get_oil_type(model, year, is_hybrid, cylinders):
    with get_session() as session:
        stmt = select(OilLookup.oil_type, OilLookup.is_suv).where(
            OilLookup.model == model.upper(),
            OilLookup.year == year,
            OilLookup.cylinders == cylinders
        )
        if is_hybrid:
            stmt = stmt.where(OilLookup.engine_type == "HV")

        results = session.exec(stmt).all()
        return [[oil_type, is_suv] for oil_type, is_suv in results]


def get_service_id(oil_type, is_suv, cylinders):
    with get_session() as session:
        stmt = select(ServiceMapping.service_id, ServiceMapping.processing_time_min).where(
            ServiceMapping.oil_type == oil_type.upper(),
            ServiceMapping.is_suv == is_suv,
            ServiceMapping.cylinders == cylinders
        )
        result = session.exec(stmt).first()
        return result if result else None


def get_all_services_db() -> List[Dict[str, Any]]:
    with get_session() as session:
        services = session.exec(
            select(ServiceMapping).order_by(ServiceMapping.service_id)).all()
        return [service.dict() for service in services]


def get_all_date_db() -> List[Dict[str, Any]]:
    with get_session() as session:
        results = session.exec(select(Appointment.id, Appointment.date)).all()
        return [{"id": id, "date": date} for id, date in results]


def get_service_by_id_db(service_id: int) -> Optional[Dict[str, Any]]:
    with get_session() as session:
        service = session.get(ServiceMapping, service_id)
        return service.dict() if service else None


def get_service_by_code_db(code: str) -> Optional[Dict[str, Any]]:
    with get_session() as session:
        stmt = select(ServiceMapping).where(ServiceMapping.code == code)
        service = session.exec(stmt).first()
        return service.dict() if service else None


# --- Transport Queries ---


# def get_all_transport_options_db() -> List[Dict[str, Any]]:
#     conn = sqlite3.connect(DB_FILE)
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()
#     cursor.execute("SELECT id, type, description FROM TRANSPORT ORDER BY type")
#     options = [dict(row) for row in cursor.fetchall()]
#     conn.close()
#     return options


# def get_transport_by_id_db(transport_id: int) -> Optional[Dict[str, Any]]:
#     conn = sqlite3.connect(DB_FILE)
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()
#     cursor.execute(
#         "SELECT id, type, description FROM TRANSPORT WHERE id = ?", (transport_id,))
#     row = cursor.fetchone()
#     conn.close()
#     return dict(row) if row else None


# def get_transport_by_type_db(transport_type: str) -> Optional[Dict[str, Any]]:
#     conn = sqlite3.connect(DB_FILE)
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()
#     cursor.execute(
#         "SELECT id, type, description FROM TRANSPORT WHERE type = ?", (transport_type,))
#     row = cursor.fetchone()
#     conn.close()
#     return dict(row) if row else None

# --- Appointment Queries and Mutations ---


# def get_appointment_by_id_db(appointment_id: int) -> Optional[Dict[str, Any]]:
#     with get_session() as session:
#         appointment = session.get(Appointment, appointment_id)
#         return appointment.dict() if appointment else None


# def get_appointments_by_telephone_db(telephone: str) -> List[Dict[str, Any]]:
#     conn = sqlite3.connect(DB_FILE)
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()
#     cursor.execute(
#         "SELECT id, telephone, date, car, service_id, transport_id FROM APPOINTMENTS WHERE telephone = ? ORDER BY date",
#         (telephone,)
#     )
#     appointments = [dict(row) for row in cursor.fetchall()]
#     conn.close()
#     return appointments


# def get_all_appointment_datetimes_db() -> List[str]:
#     conn = sqlite3.connect(DB_FILE)
#     cursor = conn.cursor()
#     cursor.execute("SELECT date FROM APPOINTMENTS ORDER BY date")
#     datetimes = [row[0] for row in cursor.fetchall()]
#     conn.close()
#     return datetimes


# def add_appointment_db(details: Dict[str, Any]) -> Optional[int]:
#     """
#     Adds an appointment. Expects 'telephone', 'date', 'car',
#     'service_id' (as string), and 'transport_type'.
#     """
#     try:
#         with get_session() as session:
#             transport = session.exec(
#                 select(Transport).where(Transport.type == details["transport_type"])
#             ).first()
#             if not transport:
#                 print(f"Transport type {details['transport_type']} not found.")
#                 return None

#             appointment = Appointment(
#                 telephone=details["telephone"],
#                 date=details["date"],
#                 car=details["car"],
#                 service_id=details["service_id"],  # Note: this is a string, not a foreign key
#                 transport_id=transport.id
#             )
#             session.add(appointment)
#             session.commit()
#             session.refresh(appointment)
#             return appointment.id
#     except Exception as e:
#         print(f"Error adding appointment: {e}")
#         return None


# def delete_all_appointments_by_telephone_db(telephone: str) -> bool:
#     try:
#         with get_session() as session:
#             stmt = select(Appointment).where(Appointment.telephone == telephone)
#             appointments = session.exec(stmt).all()
#             if not appointments:
#                 return False
#             for appt in appointments:
#                 session.delete(appt)
#             session.commit()
#             return True
#     except Exception as e:
#         print(f"Error deleting appointments: {e}")
#         return False


# def delete_appointments_by_telephone_and_date_db(telephone: str, date_str: str) -> bool:
#     normalized_date = date_str.split("T")[0].split(" ")[0]
#     try:
#         with get_session() as session:
#             stmt = select(Appointment).where(Appointment.telephone == telephone)
#             matches = [
#                 appt for appt in session.exec(stmt).all()
#                 if appt.date.startswith(normalized_date)
#             ]
#             for appt in matches:
#                 session.delete(appt)
#             session.commit()
#             return bool(matches)
#     except Exception as e:
#         print(f"Error deleting appointments for {telephone} on {normalized_date}: {e}")
#         return False

if __name__ == '__main__':
    # For testing the database operations directly
    print("Running database_ops.py directly for testing...")
    # create_db()
    # add_data_default_db()

    print("\n--- Services ---")
    print(get_all_services_db())
    print(get_oil_type("RAV4", 2022, True, "4"))
    print(get_service_id("5W-30", True, "4"))
    