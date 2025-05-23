import json

db_file = "./db.json"

def read_json_file():
    def date_only(d):
        # This function extracts only the date part of the datetime string
        return d["date"].split("T")[0] if "T" in d["date"] else d["date"].split(" ")[0]

    with open(db_file, 'r') as f:
        data = json.load(f)
        if len(data) > 0:
            return list(map(date_only, data))
        else:
            return []

def delete_all_appointments(telephone):
    try:
        with open(db_file, 'r') as f:
            data = json.load(f)
        
        # Filter out appointments that match the given telephone number
        updated_data = [appointment for appointment in data if appointment["telephone"] != telephone]
        
        with open(db_file, 'w') as f:
            json.dump(updated_data, f, indent=4)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def delete_appointments_date(telephone, date):
    try:
        with open(db_file, 'r') as f:
            data = json.load(f)
        
        # Normalize the input date to match the format in the JSON file for comparison
        # This assumes dates in the JSON are either "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DD HH:MM"
        normalized_input_date = date.split("T")[0] if "T" in date else date.split(" ")[0]

        # Filter out appointments that match both the telephone and the date
        updated_data = [
            appointment for appointment in data
            if not (
                appointment["telephone"] == telephone and 
                (appointment["date"].split("T")[0] if "T" in appointment["date"] else appointment["date"].split(" ")[0]) == normalized_input_date
            )
        ]
        
        with open(db_file, 'w') as f:
            json.dump(updated_data, f, indent=4)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def get_all_appointments_number(telephone):
    def telephone_only(d):
        return d["telephone"] == telephone
    with open(db_file, 'r') as f:
        data = json.load(f)
        if len(data) > 0:
            return list(filter(telephone_only, data))
        else:
            return []
            
def write_json_file(data_write : dict):
    try:
        with open(db_file, 'r') as file: # Changed 'db.json' to db_file
            data: list[dict] = json.load(file) 
        data.append(dict(data_write))

        with open(db_file, 'w') as file: # Changed 'db.json' to db_file
            json.dump(data, file, indent=4)
        return True
    except FileNotFoundError:
        # If the file doesn't exist, create it with the new data
        with open(db_file, 'w') as file:
            json.dump([data_write], file, indent=4)
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False