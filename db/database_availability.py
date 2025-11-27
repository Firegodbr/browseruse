from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlmodel import select
from datetime import datetime, timedelta
from fastapi import HTTPException
# from sqlalchemy import MetaData
from sqlmodel import SQLModel, Field, create_engine, Session, Relationship, Column, String, Text
import re
import os
from sqlalchemy.orm import registry
from dotenv import load_dotenv
import calendar
load_dotenv()
# Define the database connection URL (e.g., SQLite or PostgreSQL)
# Change this URL for PostgreSQL or another DB
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///test.sqlite")
class DB_Availability(SQLModel, registry=registry()):
    pass
# Define the SQLModel classes
# Weeks Table
class Week(DB_Availability, table=True):
    week_id: int = Field(default=None, primary_key=True)
    start_date: str = Field(sa_column=Column(String(255)))  
    end_date: str = Field(sa_column=Column(String(255)))    
    week_label: str = Field(sa_column=Column(String(255)))  
    days: list["Day"] = Relationship(back_populates="week", cascade_delete=True)

# Days Table
class Day(DB_Availability, table=True):
    day_id: int = Field(default=None, primary_key=True)
    day_name: str
    week_id: int = Field(foreign_key="week.week_id", ondelete="CASCADE")
    week: "Week" = Relationship(back_populates="days")
    timeslots: list["Timeslot"] = Relationship(back_populates="day", cascade_delete=True)

# Timeslots Table
class Timeslot(DB_Availability, table=True):
    timeslot_id: int = Field(default=None, primary_key=True)
    time: str
    availability: bool
    day_id: int = Field(foreign_key="day.day_id", ondelete="CASCADE")
    day: "Day" = Relationship(back_populates="timeslots")
    

class Appointment(DB_Availability, table=True):
    id: int = Field(default=None, primary_key=True)
    car: str = Field(sa_column=Column(String(255)))
    service_code: str = Field(sa_column=Column(String(255)))
    service_description: str = Field(sa_column=Column(Text()))
    date: str = Field(sa_column=Column(String(255)))
    telephone: str = Field(sa_column=Column(String(255)))
    transport_mode: str = Field(sa_column=Column(String(255)))
    call_logs: list["Call_Log"] = Relationship(back_populates="appointment", cascade_delete=True)

class Call_Log(DB_Availability, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    telephone: str = Field(sa_column=Column(String(255)))
    time: str = Field(sa_column=Column(String(255)))
    status: str = Field(sa_column=Column(String(255)))
    error: str | None = Field(
        default=None,
        sa_column=Column(Text(), nullable=True)
    )
    appointment_id: int | None = Field(foreign_key="appointment.id", ondelete="CASCADE", nullable=True)  # Make it nullable
    appointment: "Appointment" = Relationship(back_populates="call_logs")
    feedback: "Feedback" = Relationship(back_populates="call_log", sa_relationship_kwargs={"uselist": False})


class Feedback(DB_Availability, table=True):
    id: int | None = Field(default=None, primary_key=True)
    call_log_id: int | None = Field(
        default=None,
        foreign_key="call_log.id",
        nullable=True,
        ondelete="CASCADE"
    )
    feedback: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )
    
    call_log: "Call_Log" = Relationship(back_populates="feedback")

# Connect to the Database
engine = create_engine(DATABASE_URL, echo=True)
# Create the tables in the database if they don't exist


def create_db_if_not_exists():
    # Check if the tables exist before creating
    DB_Availability.metadata.create_all(bind=engine, checkfirst=True)    


# Dependency to get the database session
def get_session():
    """
    Dependency to get the database session.

    Yields a database session object.
    """

    with Session(engine) as session:
        yield session


def get_next_available_time():
    # Get current time
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")  # Time in "HH:MM" format

    # Get today's date and day of the week
    day_of_week = now.strftime('%A')  # Example: 'Monday', 'Tuesday', etc.

    # Query the database for all available timeslots for today
    with Session(engine) as session:
        # Find the day record based on the current day of the week (e.g., 'Monday')
        day = session.query(Day).filter(Day.day_name == day_of_week).first()

        if not day:
            raise HTTPException(
                status_code=404, detail=f"No available slots for {day_of_week}")

        # Get the available timeslots for the current day
        available_timeslots = (
            session.query(Timeslot)
            .filter(Timeslot.day_id == day.day_id)
            .filter(Timeslot.availability == True)
            .all()
        )

        # Find the next available timeslot
        for timeslot in available_timeslots:
            if timeslot.time > current_time_str:
                return timeslot.time

    # If no available timeslot is found
    raise HTTPException(
        status_code=404, detail="No available timeslot found after now.")


def check_and_update_availability(session: Session, week_label: str, day_name: str, timeslot_data: dict):
    try:
        print(f"Searching for Week with label: '{week_label}'")  # Debug print

        # Fetch the Week record, or create it if not found
        week = session.exec(select(Week).filter(
            Week.week_label == week_label)).first()

        if not week:
            # Debug print
            print(
                f"Week with label {week_label} not found, creating new week.")
            # Create a new Week record if not found
            start_date, end_date =parse_time_labels(week_label)
            week = Week(week_label=week_label, start_date=start_date, end_date=end_date, created_at=datetime.utcnow())
            session.add(week)
            session.commit()  # Commit to get the generated `week_id`
            print(f"Created new week: {week_label}")

        print(f"Found Week: {week}")

        # Fetch the Day record for the specific week and day_name, or create if not found
        day = session.exec(select(Day).filter(
            Day.week_id == week.week_id, Day.day_name == day_name)).first()

        if not day:
            # Debug print
            print(
                f"Day {day_name} not found in week {week_label}, creating new day.")
            # Create a new Day record if not found
            day = Day(week_id=week.week_id, day_name=day_name,
                      created_at=datetime.utcnow())
            session.add(day)
            session.commit()  # Commit to get the generated `day_id`
            print(f"Created new day: {day_name} in week {week_label}")

        # Iterate through timeslot data
        for time, availability in timeslot_data.items():
            try:
                # Try to get the existing timeslot, or create a new one if not found
                timeslot = session.exec(select(Timeslot).filter(
                    Timeslot.day_id == day.day_id, Timeslot.time == time)).first()

                if timeslot:
                    # If availability changed, update it
                    if timeslot.availability != availability:
                        timeslot.availability = availability
                        session.add(timeslot)
                        print(
                            f"Updated availability for {week_label} - {day_name} - {time}")
                else:
                    # If no timeslot exists, create a new one
                    new_timeslot = Timeslot(
                        day_id=day.day_id, time=time, availability=availability)
                    session.add(new_timeslot)
                    print(
                        f"Added new timeslot for {week_label} - {day_name} - {time}")
            except SQLAlchemyError as e:
                # Catch any database-related error (e.g., integrity constraint violations)
                session.rollback()  # Rollback the session in case of error
                print(
                    f"Error occurred while processing timeslot for {week_label} - {day_name} - {time}: {str(e)}")
                raise HTTPException(
                    status_code=500, detail=f"Error occurred while processing timeslot {time} for {day_name}.")

        # Commit the changes after processing all timeslots for the day
        session.commit()
    except SQLAlchemyError as e:
        # General database error handling
        print(
            f"Database error occurred while processing {week_label} - {day_name}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Database error occurred: {str(e)}")

    except Exception as e:
        # Catch all other errors
        print(f"Unexpected error occurred: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Unexpected error occurred: {str(e)}")

def delete_old_weeks(session: Session, week_labels: list):
    """
    Delete old weeks from the database.
    Args:
        session: SQLAlchemy session object.
        week_labels: List of week labels to keep.
    """
    try:
        # Get all weeks from the database
        weeks = session.exec(select(Week)).all()
        for week in weeks:
            if week.week_label not in week_labels:
                session.delete(week)
        session.commit()
    except SQLAlchemyError as e:
        # Handle database errors
        session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Database error occurred: {str(e)}")

def process_schedule_data(session: Session, schedule_data: dict):
    """
    Process the full schedule data and update the database.
    Args:
        session: SQLAlchemy session object.
        schedule_data: Dictionary with availability data for each week, day, and timeslot.
    """
    try:
        week_labels = []
        for week_label, week_data in schedule_data.items():
            new_week_label = week_label.replace("Sem. du ", "").strip()
            week_labels.append(new_week_label)
            for day_name, timeslot_data in week_data.items():
                try:
                    # Call the check_and_update_availability function for each week and day
                    check_and_update_availability(
                        session, new_week_label, day_name, timeslot_data)
                except HTTPException as e:
                    # If an HTTPException is raised during the process, we log and continue with the next one
                    print(
                        f"Error while processing schedule for {new_week_label} - {day_name}: {e.detail}")
                    continue
        delete_old_weeks(session, week_labels)
        # Commit the changes after processing all schedule data
        session.commit()

    except SQLAlchemyError as e:
        # Handle any errors related to SQLAlchemy
        print(
            f"Database error occurred while processing the schedule: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Database error occurred: {str(e)}")

    except Exception as e:
        # Catch all other errors in processing
        print(
            f"Unexpected error occurred while processing the schedule: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Unexpected error occurred: {str(e)}")

    return {"message": "Schedule successfully processed"}

month_map = {
    'janv.': 'January', 'févr.': 'February', 'mars': 'March', 'avr.': 'April', 
    'mai': 'May', 'juin': 'June', 'juil.': 'July', 'août': 'August', 'sept.': 'September',
    'oct.': 'October', 'nov.': 'November', 'déc.': 'December'
}

# Function to convert French date string to datetime
def convert_french_date_to_datetime(date_str):
    # Match the day and month from the French date string
    for french_month, english_month in month_map.items():
        if french_month in date_str:
            # Find the day and month
            date_parts = re.findall(r'(\d{1,2})\s' + french_month, date_str)
            if date_parts:
                day = int(date_parts[0])
                month = english_month
                year = datetime.now().year  # Assuming current year if no year is specified
                return datetime(year, datetime.strptime(month, '%B').month, day)
    return None

# Function to parse the given time labels
def parse_time_labels(label):
    # Pattern for case: "17 au 23 août 2025"
    match1 = re.match(r'(\d{1,2})\s+au\s+(\d{1,2})\s+([a-zéû\.]+)\s+(\d{4})', label, re.IGNORECASE)
    if match1:
        start_day = int(match1.group(1))
        end_day = int(match1.group(2))
        month_str = match1.group(3).strip()
        year = int(match1.group(4))

        if month_str in month_map:
            month_name = month_map[month_str]
            month_num = datetime.strptime(month_name, '%B').month
            start_date = datetime(year, month_num, start_day)
            end_date = datetime(year, month_num, end_day)
            return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

    # Pattern for case: "31 août au 6 sept. 2025"
    match2 = re.match(r'(\d{1,2})\s+([a-zéû\.]+)\s+au\s+(\d{1,2})\s+([a-zéû\.]+)\s+(\d{4})', label, re.IGNORECASE)
    if match2:
        start_day = int(match2.group(1))
        start_month_str = match2.group(2).strip()
        end_day = int(match2.group(3))
        end_month_str = match2.group(4).strip()
        year = int(match2.group(5))

        if start_month_str in month_map and end_month_str in month_map:
            start_month_name = month_map[start_month_str]
            end_month_name = month_map[end_month_str]
            start_month_num = datetime.strptime(start_month_name, '%B').month
            end_month_num = datetime.strptime(end_month_name, '%B').month
            start_date = datetime(year, start_month_num, start_day)
            end_date = datetime(year, end_month_num, end_day)
            return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

    return None, None
def get_available_appointments(check_values, start_time, end_time):
    """
    Get availability data from the database and group available timeslots into timeframes,
    but only for today or future days.
    """
    available_appointments = []

    # Get today's date
    today = datetime.today().date()

    # If start_time and end_time are datetime objects, extract just the time part
    if isinstance(start_time, datetime):
        start_time = start_time.time()  # Extract time only
    if isinstance(end_time, datetime):
        end_time = end_time.time()  # Extract time only

    # If start_time and end_time are strings, convert them to datetime.time objects
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, '%H:%M').time()
    if isinstance(end_time, str):
        end_time = datetime.strptime(end_time, '%H:%M').time()

    with Session(engine) as db:
        # Retrieve weeks, assuming you're looking for the current week or a specific one
        weeks = db.query(Week).all()
        if not weeks:
            raise HTTPException(status_code=404, detail="Weeks not found.")
        
        for day_name in check_values.days:
            # Iterate through weeks to get matching days
            for week in weeks:
                # Fetch days for each week in bulk
                days = db.query(Day).filter(Day.week_id == week.week_id, Day.day_name == day_name).all()
                if not days:
                    continue  # Skip if the day is not found

                for day in days:
                    # Convert start_date (string) to a datetime.date object
                    day_start_date = datetime.strptime(week.start_date, '%Y-%m-%d').date()
                    # Convert day name to index (Monday=0, Sunday=6)
                    target_weekday = list(calendar.day_name).index(day_name)

                    # Get actual date of that day in the current week
                    day_date = day_start_date + timedelta(days=(target_weekday - day_start_date.weekday()) % 7)

                    # Then use this for filtering
                    if day_date < today:
                        continue

                    # Fetch timeslots for each day
                    timeslots = db.query(Timeslot).filter(Timeslot.day_id == day.day_id).all()

                    # Prepare a list of available timeslots (timeslot.time as datetime.time object)
                    available_times = []
                    for timeslot in timeslots:
                        if isinstance(timeslot.time, str):
                            timeslot_time = datetime.strptime(timeslot.time, '%H:%M').time()  # Convert string to time
                        else:
                            timeslot_time = timeslot.time  # Already a datetime.time object

                        if start_time <= timeslot_time <= end_time and timeslot.availability:
                            available_times.append(timeslot_time)

                    # Now group the available times into timeframes
                    if available_times:
                        # Sort the available times
                        available_times.sort()

                        # Create timeframes by grouping consecutive available times
                        timeframes = []
                        current_start = available_times[0]
                        current_end = available_times[0]

                        for i in range(1, len(available_times)):
                            if available_times[i] == (datetime.combine(datetime.today(), current_end) + timedelta(minutes=15)).time():
                                # Continue the current timeframe (assuming each slot is 15 minutes)
                                current_end = available_times[i]
                            else:
                                # End the current timeframe and start a new one
                                timeframes.append({
                                    "day": day_name,
                                    "week": week.week_label,
                                    "time": f"{current_start} to {current_end}"
                                })
                                current_start = available_times[i]
                                current_end = available_times[i]

                        # Append the last timeframe
                        timeframes.append({
                            "day": day_name,
                            "week": week.week_label,
                            "time": f"{current_start} to {current_end}"
                        })

                        available_appointments.extend(timeframes)

    return available_appointments

def insert_appointment_db(appointment: Appointment):
    with Session(engine) as db:
        db.add(appointment)
        db.commit()
        return appointment.id
def insert_call_log_db(db: Session, call_log: Call_Log):
    db.add(call_log)
    db.commit()
    db.refresh(call_log)
    return call_log.id

def insert_feedback_db(db: Session, feedback: Feedback):
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback.id

def get_latest_feedback(db: Session, phone_number: str) -> Feedback | None:
    statement = (
        select(Feedback)
        .join(Feedback.call_log)
        .where(Call_Log.telephone == phone_number)
        .order_by(Feedback.id.desc())
        .limit(1)
    )
    return db.exec(statement).first()

def update_feedback_db(db: Session, feedback: Feedback) -> Feedback:
    updated = db.merge(feedback)
    db.commit()
    db.refresh(updated)
    return updated

if __name__ == "__main__":
    print(parse_time_labels("17  au 23 août 2025"))
    print(parse_time_labels("31 août au 6 sept. 2025"))