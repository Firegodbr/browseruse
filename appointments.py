import os, sqlite3

DB_FILE = "./db.sqlite"

def create_db():
    """ Initiate the DB if DB is not configurate created """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS SERVICE(
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                code VARCHAR,
                                service TEXT NOT NULL
                            )
                            ''')
        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS TRANSPORT(
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                type VARCHAR(15),
                                description TEXT NOT NULL
                            )
                            ''')
        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS APPOINTMENTS(
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                service_id INTEGER,
                                telephone VARCHAR(12),
                                car VARCHAR,
                                transport_id INTEGER,
                                date TEXT NOT NULL,
                                FOREIGN KEY (service_id) REFERENCES SERVICE(id),
                                FOREIGN KEY (transport_id) REFERENCES TRANSPORT(id)
                            )
                            ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_telephone ON APPOINTMENTS (telephone)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_date ON APPOINTMENTS (date)
        ''')
        conn.commit()
        print(f"Database initialized")

    except sqlite3.Error as e:
        print(f"Database didn't initialize: {e}")
    finally:
        if conn:
            conn.close()
            
def add_data_default_db():
    """Insert default data to db if tables are empty."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Check if SERVICE table is empty before inserting
        cursor.execute("SELECT COUNT(*) FROM SERVICE")
        if cursor.fetchone()[0] == 0:
            services = [
                ("55", "Oil change"),
                ("35", "Vehicle maintenance"),
                ("TIRE", "Tire Rotation"),
                ("BRAKE", "Brake Inspection")
            ]
            cursor.executemany(''' INSERT INTO SERVICE (code, service) VALUES (?, ?)''', services)
            print("Added default data to SERVICE table.")
        else:
            print("SERVICE table already has data.")

        # Check if TRANSPORT table is empty before inserting
        cursor.execute("SELECT COUNT(*) FROM TRANSPORT")
        if cursor.fetchone()[0] == 0:
            transports = [
                ("None", "No transport needed"),
                ("Rental", "Rental car available"),
                ("Wait", "Customer can wait at the center"),
                ("Shuttle", "Shuttle service available"),
                ("Drop-off", "Drop-off service available")
            ]
            cursor.executemany(''' INSERT INTO TRANSPORT (type, description) VALUES (?, ?)''', transports)
            print("Added default data to TRANSPORT table.")
        else:
            print("TRANSPORT table already has data.")

        conn.commit()
    except sqlite3.Error as e:
        print(f"Problem in adding default data to database: {e}")
    finally:
        if conn:
            conn.close()

def get_all_appointment_datetimes_db() -> list:
    """
    Retrieves the full datetime string of all appointments from the SQLite database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT date FROM APPOINTMENTS ORDER BY date")
        rows = cursor.fetchall()
        return [row[0] for row in rows] # Returns full datetime string
    except sqlite3.Error as e:
        print(f"An error occurred while fetching appointment datetimes: {e}")
        return []
    finally:
        if conn:
            conn.close()

def delete_all_appointments_by_telephone_db(telephone: str) -> bool:
    """
    Deletes all appointments for a given telephone number from the APPOINTMENTS table.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM APPOINTMENTS WHERE telephone = ?", (telephone,))
        conn.commit()
        print(f"Deleted {cursor.rowcount} appointments for telephone {telephone}.")
        return True
    except sqlite3.Error as e:
        print(f"An error occurred while deleting all appointments for {telephone}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_appointments_by_telephone_and_date_db(telephone: str, date_str: str) -> bool:
    """
    Deletes appointments for a given telephone number on a specific date.
    The date_str can be 'YYYY-MM-DD' or a full datetime string 'YYYY-MM-DDTHH:MM:SS'.
    It will match all appointments on that calendar day.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Normalize the input date_str to 'YYYY-MM-DD' for comparison target
        # This ensures we match the day, regardless of time in date_str
        normalized_target_date = date_str.split("T")[0].split(" ")[0]

        cursor.execute("""
            DELETE FROM APPOINTMENTS
            WHERE telephone = ? AND strftime('%Y-%m-%d', date) = ?
        """, (telephone, normalized_target_date))
        conn.commit()
        print(f"Deleted {cursor.rowcount} appointments for telephone {telephone} on date {normalized_target_date}.")
        return True
    except sqlite3.Error as e:
        print(f"An error occurred while deleting appointments for {telephone} on date {date_str}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_all_appointments_by_telephone_db(telephone: str) -> list:
    """
    Retrieves all appointments for a given telephone number, joining with SERVICE and TRANSPORT tables.
    Returns a list of dictionaries with detailed appointment information.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row # Access columns by name
        cursor = conn.cursor()
        query = """
            SELECT
                a.id AS appointment_id,
                a.telephone,
                a.date,
                a.car,
                s.code AS service_code,
                s.service AS service_description,
                t.type AS transport_type,
                t.description AS transport_description
            FROM APPOINTMENTS a
            LEFT JOIN SERVICE s ON a.service_id = s.id
            LEFT JOIN TRANSPORT t ON a.transport_id = t.id
            WHERE a.telephone = ?
            ORDER BY a.date
        """
        cursor.execute(query, (telephone,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"An error occurred while fetching appointments for {telephone}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def add_appointment_db(appointment_details: dict) -> bool:
    """
    Adds a new appointment to the APPOINTMENTS table.
    appointment_details dictionary should contain:
    "telephone": str
    "date": str (full datetime string e.g., "YYYY-MM-DDTHH:MM:SS")
    "car": str
    "service_code": str (code from SERVICE table, e.g., "35")
    "transport_type": str (type from TRANSPORT table, e.g., "None")
    """
    conn = None
    required_keys = {"telephone", "date", "car", "service_code", "transport_type"}
    if not required_keys.issubset(appointment_details.keys()):
        missing_keys = required_keys - appointment_details.keys()
        print(f"Missing required keys in appointment_details: {missing_keys}")
        return False

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Get service_id from SERVICE table
        cursor.execute("SELECT id FROM SERVICE WHERE code = ?", (appointment_details["service_code"],))
        service_row = cursor.fetchone()
        if not service_row:
            print(f"Error: Service code '{appointment_details['service_code']}' not found in SERVICE table.")
            return False
        db_service_id = service_row[0]

        # Get transport_id from TRANSPORT table
        cursor.execute("SELECT id FROM TRANSPORT WHERE type = ?", (appointment_details["transport_type"],))
        transport_row = cursor.fetchone()
        if not transport_row:
            print(f"Error: Transport type '{appointment_details['transport_type']}' not found in TRANSPORT table.")
            return False
        db_transport_id = transport_row[0]

        # Insert into APPOINTMENTS
        cursor.execute("""
            INSERT INTO APPOINTMENTS (telephone, date, car, service_id, transport_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            appointment_details["telephone"],
            appointment_details["date"],
            appointment_details["car"],
            db_service_id,
            db_transport_id
        ))
        conn.commit()
        print(f"Successfully added appointment for {appointment_details['telephone']} on {appointment_details['date']}.")
        return True
    except sqlite3.IntegrityError as e: # Catch issues like foreign key constraints if IDs were wrong (though checked)
        print(f"Database integrity error while adding appointment: {e}")
        return False
    except sqlite3.Error as e:
        print(f"An error occurred while adding appointment: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_db()
    add_data_default_db()