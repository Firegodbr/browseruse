# database_ops.py
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

DB_FILE = "./db.sqlite"

# --- Database Initialization and Default Data ---
def create_db():
    """Initiate the DB and tables if they don't exist."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # --- Existing Tables ---

        # TRANSPORT Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS TRANSPORT(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type VARCHAR(25) UNIQUE NOT NULL, 
                description TEXT NOT NULL
            )
        ''')

        # APPOINTMENTS Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS APPOINTMENTS(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id TEXT NOT NULL,
                telephone VARCHAR(15) NOT NULL, 
                transport_id INTEGER,
                date TEXT NOT NULL, -- Expected format: YYYY-MM-DDTHH:MM:SS
                car TEXT,
                FOREIGN KEY (transport_id) REFERENCES TRANSPORT(id)
            )
        ''')

        # Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_telephone ON APPOINTMENTS (telephone)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON APPOINTMENTS (date)')

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS OilLookup (
            model TEXT,
            engine_type TEXT,
            year INTEGER,
            oil_type TEXT,
            is_suv BOOLEAN,
            cylinders INTEGER
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ServiceMapping (
            oil_type TEXT,
            is_suv BOOLEAN,
            cylinders INTEGER,
            service_id TEXT,
            description TEXT
        )
        """)

        conn.commit()
        
        print(f"Database '{DB_FILE}' initialized/verified successfully.")
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.close()

def add_data_default_db():
    """Insert default data into SERVICE, TRANSPORT, and oil reference tables."""
    conn = None
    TOYOTA_OIL_JSON = "./Toyota Oil v5.json"
    SERVICE_ID_JSON = "./codes travail toyota.json"
     
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Default Transport Options
        cursor.execute("SELECT COUNT(*) FROM TRANSPORT")
        if cursor.fetchone()[0] == 0:
            transport_data = [
                ("aucun", "No transport needed, customer has arrangements"),
                ("courtoisie", "Rental car required/arranged"),
                ("attente", "Customer will wait at the facility"),
                ("reconduire", "Shuttle service to local area"),
                ("laisser", "Customer will drop off the vehicle")
            ]
            cursor.executemany("INSERT INTO TRANSPORT (type, description) VALUES (?, ?)", transport_data)
            print("Added default data to TRANSPORT table.")

        # Load and insert Toyota Oil data
        if os.path.exists(TOYOTA_OIL_JSON) and os.path.isfile(SERVICE_ID_JSON):
            with open(TOYOTA_OIL_JSON, "r", encoding="utf-8") as oil_json_file:
                oil_data = json.load(oil_json_file)

            with open(SERVICE_ID_JSON, "r", encoding="utf-8") as service_id_json_file:
                service_id_data = json.load(service_id_json_file)

            # Insert models, engine types, and oil types
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
                        cursor.execute("""
                            INSERT INTO OilLookup (model, engine_type, year, oil_type, is_suv, cylinders)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (model.upper(), engine.upper(), year, oil.upper(), is_suv, cylinders))
            for cyl_key, oil_map in service_id_data["cylinder_types"].items():
            # Split to get cylinder and SUV flag
                if "-SUV" in cyl_key:
                    cyl = int(cyl_key.split("-")[0])
                    is_suv = True
                else:
                    cyl = int(float(cyl_key))  # "6.0" → 6
                    is_suv = False
                for oil_type, service_id in oil_map.items():
                    cursor.execute("""
                        INSERT INTO ServiceMapping (oil_type, is_suv, cylinders, service_id)
                        VALUES (?, ?, ?, ?)
                    """, (oil_type.upper(), is_suv, cyl, service_id))
            print("Toyota oil data added to database.")
        else:
            print(f"Toyota oil JSON file not found at: {TOYOTA_OIL_JSON}")

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding default data: {e}")
    except Exception as ex:
        print(f"Unexpected error: {ex}")
    finally:
        if conn:
            conn.close()

# --- Service Queries ---
def get_oil_type(model, year, is_hybrid, cylinders):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if is_hybrid:
        query = """
        SELECT oil_type, is_suv FROM OilLookup
        WHERE model = ? AND year = ? AND engine_type = ? AND cylinders = ?
        """
        cursor.execute(query, (model.upper(), year, "HV", cylinders))
        return [[row[0], row[1]] for row in cursor.fetchall()]
    else:
        query = """
        SELECT oil_type, is_suv FROM OilLookup
        WHERE model = ? AND year = ? AND cylinders = ?
        """
        cursor.execute(query, (model.upper(), year, cylinders))
        return [[row[0], row[1]] for row in cursor.fetchall()]

def get_service_id(oil_type, is_suv, cylinders):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = """
    SELECT service_id FROM ServiceMapping
    WHERE oil_type = ? AND is_suv = ? AND cylinders = ?
    """
    cursor.execute(query, (oil_type.upper(), is_suv, cylinders))
    result = cursor.fetchone()
    return result[0] if result else None

def get_all_services_db() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, service FROM SERVICE ORDER BY code")
    services = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return services

def get_all_date_db() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, date FROM APPOINTMENTS")
    services = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return services

def get_service_by_id_db(service_id: int) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, service FROM SERVICE WHERE id = ?", (service_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_service_by_code_db(code: str) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, service FROM SERVICE WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# --- Transport Queries ---
def get_all_transport_options_db() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, type, description FROM TRANSPORT ORDER BY type")
    options = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return options

def get_transport_by_id_db(transport_id: int) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, type, description FROM TRANSPORT WHERE id = ?", (transport_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_transport_by_type_db(transport_type: str) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, type, description FROM TRANSPORT WHERE type = ?", (transport_type,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# --- Appointment Queries and Mutations ---
def get_appointment_by_id_db(appointment_id: int) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, telephone, date, car, service_id, transport_id FROM APPOINTMENTS WHERE id = ?",
        (appointment_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_appointments_by_telephone_db(telephone: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, telephone, date, car, service_id, transport_id FROM APPOINTMENTS WHERE telephone = ? ORDER BY date",
        (telephone,)
    )
    appointments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return appointments

def get_all_appointment_datetimes_db() -> List[str]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM APPOINTMENTS ORDER BY date")
    datetimes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return datetimes

def add_appointment_db(details: Dict[str, Any]) -> Optional[int]:
    """
    Adds an appointment. Expects 'telephone', 'date', 'car', 
    'service_code', and 'transport_type' in details.
    Returns the ID of the newly created appointment or None on failure.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        service = get_service_by_code_db(details["service_code"])
        if not service:
            print(f"Service code {details['service_code']} not found.")
            return None
        service_id = service['id']

        transport = get_transport_by_type_db(details["transport_type"])
        if not transport:
            print(f"Transport type {details['transport_type']} not found.")
            return None
        transport_id = transport['id']

        cursor.execute(
            """
            INSERT INTO APPOINTMENTS (telephone, date, car, service_id, transport_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (details["telephone"], details["date"], details["car"], service_id, transport_id)
        )
        conn.commit()
        new_id = cursor.lastrowid
        return new_id
    except sqlite3.Error as e:
        print(f"Error adding appointment: {e}")
        if conn:
            conn.rollback() # Rollback on error
        return None
    finally:
        if conn:
            conn.close()

def delete_all_appointments_by_telephone_db(telephone: str) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM APPOINTMENTS WHERE telephone = ?", (telephone,))
        conn.commit()
        return cursor.rowcount > 0 # Return True if any rows were deleted
    except sqlite3.Error as e:
        print(f"Error deleting appointments by telephone {telephone}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_appointments_by_telephone_and_date_db(telephone: str, date_str: str) -> bool:
    """
    Deletes appointments for a given telephone on a specific date (YYYY-MM-DD).
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Normalize date_str to YYYY-MM-DD for matching against the date part
        normalized_date = date_str.split("T")[0].split(" ")[0]
        cursor.execute(
            "DELETE FROM APPOINTMENTS WHERE telephone = ? AND strftime('%Y-%m-%d', date) = ?",
            (telephone, normalized_date)
        )
        conn.commit()
        print(f"Delete {cursor.rowcount > 0}")
        return cursor.rowcount > 0 # Return True if any rows were deleted
    except sqlite3.Error as e:
        print(f"Error deleting appointments for {telephone} on {normalized_date}: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # For testing the database operations directly
    print("Running database_ops.py directly for testing...")
    create_db()
    add_data_default_db()

    print("\n--- Services ---")
    print(get_all_services_db())
    print(get_service_by_code_db("35"))

    print("\n--- Transport Options ---")
    print(get_all_transport_options_db())
    print(get_transport_by_type_db("Wait"))

    print("\n--- Appointments ---")
    test_appt_details = {
        "telephone": "5551234567",
        "date": "2025-12-01T10:00:00",
        "car": "Honda Civic 2021",
        "service_code": "35",
        "transport_type": "Wait"
    }
    new_appt_id = add_appointment_db(test_appt_details)
    if new_appt_id:
        print(f"Added test appointment with ID: {new_appt_id}")
        print("Appointment by ID:", get_appointment_by_id_db(new_appt_id))
    
    test_appt_details_2 = {
        "telephone": "5551234567",
        "date": "2025-12-05T14:00:00",
        "car": "Honda Civic 2021",
        "service_code": "55",
        "transport_type": "None"
    }
    add_appointment_db(test_appt_details_2)

    print("\nAppointments for 5551234567:")
    print(get_appointments_by_telephone_db("5551234567"))
    
    print("\nAll appointment datetimes:")
    print(get_all_appointment_datetimes_db())

    print("\nDeleting appointments for 5551234567 on 2025-12-01...")
    delete_appointments_by_telephone_and_date_db("5551234567", "2025-12-01")
    print("Appointments for 5551234567 after deletion:", get_appointments_by_telephone_db("5551234567"))

    print("\nDeleting all remaining appointments for 5551234567...")
    delete_all_appointments_by_telephone_db("5551234567")
    print("Appointments for 5551234567 after full deletion:", get_appointments_by_telephone_db("5551234567"))
