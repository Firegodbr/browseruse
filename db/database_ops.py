# database_ops.py

from typing import Optional, Tuple
from sqlmodel import select
from pathlib import Path
from sqlmodel import SQLModel, Field, create_engine, Session, Relationship, select, MetaData, Column, JSON
from sqlalchemy.orm import registry
from typing import Optional, List, Dict, Any
import json
import os

DB_FILE = "./db.sqlite"
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(DATABASE_URL, echo=False)


def get_session():
    return Session(engine)


class DB_Operations(SQLModel, registry=registry()):
    pass

# --- SQLModel Models ---


class OilLookup(DB_Operations, table=True):
    id: int = Field(default=None, primary_key=True, )
    model: str
    engine_type: str
    year: int
    oil_type: str
    is_suv: bool
    cylinders: int


class ServiceMapping(DB_Operations, table=True):
    id: int = Field(default=None, primary_key=True, )
    oil_type: str
    is_suv: bool
    cylinders: int
    service_id: str
    processing_time_min: int
    description: str


class ServiceMaintenanceLookup(DB_Operations, table=True):
    id: int = Field(default=None, primary_key=True)
    model: str
    engine_type: str
    number_of_cylinders: int
    years: List[int] = Field(sa_column=Column(JSON))  # store as JSON array
    oil_type: Optional[str]  # could be a string or a list, normalize to str
    is_suv: bool
    oil_change_codes: List[str] = Field(sa_column=Column(JSON))
    service1_codes: List[str] = Field(sa_column=Column(JSON))
    service2_codes: List[str] = Field(sa_column=Column(JSON))
    service3_codes: List[str] = Field(sa_column=Column(JSON))

# --- DB Initialization Function ---


def create_db():
    """
    Creates the SQLite database and initializes tables using SQLModel.
    Equivalent to the original sqlite3 schema creation.
    Returns True if the database was created, False if it was already created.
    """
    if not os.path.exists(DB_FILE):
        print("Creating new database...")
        # Indicate that the database is being created
        db_created = True
    else:
        print("Verifying/Updating existing database...")
        db_created = False

    # Create tables or verify them
    DB_Operations.metadata.create_all(bind=engine, checkfirst=True)
    print(f"Database '{DB_FILE}' initialized/verified successfully.")

    return db_created


def load_json_to_db(json_file: str):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    with get_session() as session:
        for entry in data:
            # Oil type may be a string or list, normalize it
            oil_type = entry["Oil Type"]
            if isinstance(oil_type, list):
                oil_type = ", ".join(oil_type)

            service = ServiceMaintenanceLookup(
                model=entry["Model"],
                engine_type=entry["Engine Type"],
                number_of_cylinders=entry["Number of Cylinders"],
                years=entry["Years"],
                oil_type=oil_type,
                is_suv=entry["Is SUV"],
                oil_change_codes=entry.get("Oil Change Codes", []),
                service1_codes=entry.get("Service 1 Change Codes", []),
                service2_codes=entry.get("Service 2 Change Codes", []),
                service3_codes=entry.get("Service 3 Change Codes", [])
            )
            session.add(service)

        session.commit()


def get_service_id_service_number(
    model: str,
    number_of_cylinders: int,
    year: int,
    service_type: int  # 1, 2, or 3
) -> Optional[Tuple[str, int]]:
    """
    Returns the service_id and processing_time for a given vehicle and service type.

    service_type:
        1 -> Service 1 Change Codes
        2 -> Service 2 Change Codes
        3 -> Service 3 Change Codes
    """

    # Map service_type to CarService field names
    service_map = [
        "service1_codes",
        "service2_codes",
        "service3_codes",
    ]

    with get_session() as session:
        stmt = select(ServiceMaintenanceLookup).where(
            ServiceMaintenanceLookup.model == model,
            ServiceMaintenanceLookup.number_of_cylinders == number_of_cylinders,
        )

        results = session.exec(stmt).all()
        # print(model, number_of_cylinders, year, service_type, results)

        service_codes = []  # To hold the matching service codes

        for entry in results:
            if year in entry.years:
                codes = getattr(entry, service_map[service_type - 1])
                if codes:
                    # If service_type is 3, collect all the codes
                    service_codes.extend(codes)  # Collect all matching codes

        if service_codes:
            # Here you can return all matching service codes with a fixed processing time
            return [(code, 45) for code in service_codes]

    return None


def add_data_default_db():
    """Insert default data into SERVICE, TRANSPORT, and oil reference tables using SQLModel."""
    TOYOTA_OIL_JSON = Path("./Toyota Oil v5.json")
    SERVICE_ID_JSON = Path("./codes travail toyota.json")

    try:
        with get_session() as session:
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
                        cyl = int(float(cyl_key))
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
    load_json_to_db(Path("./Toyota Code Service et Oil V22.json"))
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


def get_service_by_id_db(service_id: int) -> Optional[Dict[str, Any]]:
    with get_session() as session:
        service = session.get(ServiceMapping, service_id)
        return service.dict() if service else None


def get_service_by_code_db(code: str) -> Optional[Dict[str, Any]]:
    with get_session() as session:
        stmt = select(ServiceMapping).where(ServiceMapping.code == code)
        service = session.exec(stmt).first()
        return service.dict() if service else None


if __name__ == '__main__':
    # For testing the database operations directly
    print("Running database_ops.py directly for testing...")
    # create_db()
    # add_data_default_db()

    print("\n--- Services ---")
    print(get_all_services_db())
    print(get_oil_type("RAV4", 2022, True, "4"))
    print(get_service_id("5W-30", True, "4"))
