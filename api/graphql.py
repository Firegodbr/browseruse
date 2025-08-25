import strawberry
from strawberry.fastapi import GraphQLRouter
from typing import List, Optional
import logging
# Import database operations
import db.database_ops as db
from models.schemas import AppointmentInfoQL

from dotenv import load_dotenv
load_dotenv()

# Import the shared logger setup from the main app
logger = logging.getLogger(__name__)


# --- Strawberry GraphQL Type Definitions ---
@strawberry.type
class ServiceType:
    id: strawberry.ID
    code: str
    service: str


@strawberry.type
class TransportType:
    id: strawberry.ID
    type: str
    description: str


@strawberry.type
class ServiceResult:
    service_id: List[str]


@strawberry.type
class AppointmentType:
    id: strawberry.ID
    telephone: str
    date: str  # ISO 8601 format string
    car: Optional[str]
    service_id: Optional[str]
    transport_id: Optional[str]

    @strawberry.field
    def service(self) -> Optional[ServiceType]:
        # 'self' here is an instance of AppointmentType, which was originally a dict from DB
        # We need to ensure service_id is passed to AppointmentType instances
        if hasattr(self, 'service_id') and self.service_id is not None:
            service_data = db.get_service_by_id_db(self.service_id)
            if service_data:
                return ServiceType(id=strawberry.ID(str(service_data['id'])), code=service_data['code'], service=service_data['service'])
        return None

    @strawberry.field
    def transport(self) -> Optional[TransportType]:
        # Similar to service, ensure transport_id is available
        if hasattr(self, 'transport_id') and self.transport_id is not None:
            transport_data = db.get_transport_by_id_db(self.transport_id)
            if transport_data:
                return TransportType(id=strawberry.ID(str(transport_data['id'])), type=transport_data['type'], description=transport_data['description'])
        return None

# Custom constructor for AppointmentType to handle DB dictionary


def appointment_from_db(db_row: dict) -> AppointmentType:
    return AppointmentType(
        id=strawberry.ID(str(db_row['id'])),
        telephone=db_row['telephone'],
        date=db_row['date'],
        car=db_row.get('car'),
        # Store these for resolver use, Strawberry doesn't automatically pass non-field attributes
        service_id=db_row.get('service_id'),
        transport_id=db_row.get('transport_id')
    )


# --- Strawberry Query Definition ---
@strawberry.type
class Query:
    @strawberry.field
    def all_services(self) -> List[ServiceType]:
        services_data = db.get_all_services_db()
        return [ServiceType(id=strawberry.ID(str(s['id'])), code=s['code'], service=s['service']) for s in services_data]

    @strawberry.field
    def all_dates(self) -> List[ServiceType]:
        services_data = db.get_all_date_db()
        return [ServiceType(id=strawberry.ID(str(s['id'])), date=s['date']) for s in services_data]

    @strawberry.field
    def all_transport_options(self) -> List[TransportType]:
        transport_data = db.get_all_transport_options_db()
        return [TransportType(id=strawberry.ID(str(t['id'])), type=t['type'], description=t['description']) for t in transport_data]

    @strawberry.field
    def transport_by_type(self, type: str) -> Optional[TransportType]:
        t = db.get_transport_by_type_db(type)
        if t:
            return TransportType(id=strawberry.ID(str(t['id'])), type=t['type'], description=t['description'])
        return None

    @strawberry.field
    def appointments_by_telephone(self, telephone: str) -> List[AppointmentType]:
        appts_data = db.get_appointments_by_telephone_db(telephone)
        # Need to map db_row to AppointmentType and ensure service_id/transport_id are passed
        return [appointment_from_db(appt) for appt in appts_data]

    @strawberry.field
    def all_appointment_date_times(self) -> List[str]:
        return db.get_all_appointment_datetimes_db()

    @strawberry.field
    def appointment_by_id(self, id: strawberry.ID) -> Optional[AppointmentType]:
        appt_data = db.get_appointment_by_id_db(int(id))
        if appt_data:
            return appointment_from_db(appt_data)
        return None

    @strawberry.field(name="getServiceIdFromCarInfo")
    def get_service_id_from_car_info(
        self,
        model: str,
        year: int,
        is_hybrid: bool,
        cylinders: int
    ) -> ServiceResult:
        oil_suv_types = db.get_oil_type(model, year, is_hybrid, cylinders)
        results = []

        for oil, is_suv in oil_suv_types:
            service_id = db.get_service_id(oil, is_suv, cylinders)
            results.append(service_id)
        if not results:
            return ServiceResult(service_id=['01T6CLS8FZ'])
        else:
            return ServiceResult(service_id=list(set(results)))

# --- Strawberry Mutation Definition ---
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def add_appointment(self, input: AppointmentInfoQL) -> Optional[AppointmentType]:
        # Step 1: Prepare the appointment data (the same as input)
        details = {
            "telephone": input.telephone,
            "date": input.date,
            "car": input.car,
            "service_code": input.service_id,
            "transport_type": str(input.transport_mode.lower()),
        }
        print("Details:", details)
        # Step 2: Insert the appointment into the database
        new_appointment_id = db.add_appointment_db(details)

        if new_appointment_id:
            # Step 3: Fetch the newly created appointment details
            new_appt_data = db.get_appointment_by_id_db(new_appointment_id)
            if new_appt_data:
                # Convert the DB data to the GraphQL AppointmentType
                appointment = appointment_from_db(new_appt_data)

                # Step 4: Perform the scraping operation to make the appointment
                # Directly passing the input object
                # result = await make_appointment_scrape(input)

                # Optionally, process the result further here (e.g., log, update DB status)
                # print(f"Appointment scrape result: {result}")

                return appointment

        return None

    @strawberry.mutation
    def delete_appointments_by_telephone(self, telephone: str) -> bool:
        return db.delete_all_appointments_by_telephone_db(telephone)

    @strawberry.mutation
    def delete_appointments_by_telephone_and_date(self, telephone: str, date: str) -> bool:
        # date is expected to be YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        # The DB function handles normalization to YYYY-MM-DD for matching
        return db.delete_appointments_by_telephone_and_date_db(telephone, date)


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)
