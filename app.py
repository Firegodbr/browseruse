import os, time, json
from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller,BrowserConfig, Browser
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from getCar import get_cars
from db import write_json_file, read_json_file, get_all_appointments_number, delete_all_appointments, delete_appointments_date, db_file
from typing import Union
# Initialize FastAPI app
app = FastAPI()
load_dotenv()
config = BrowserConfig(
    headless=False, # If the browser appears or not
    disable_security=False
)
selectors = {
    "redezvous": {"search_button": "#root > div.css-pxu7mn.evwjw926 > div > div > div.css-48tder.evwjw922 > div.css-wefypi.e1p817c0 > div.css-1qvekf5.e12pldzn0 > div > div > div > div > div > div > div > div.css-1v69dku.e1f378bo2 > div > div.e1f378bo1.css-1yghlif.e1bwztlu13 > div.css-zjik7.e1f378bo0 > span:nth-child(2) > button > div > div > svg"}
}



async def get_cars_browser_use(search):
    browser = Browser(config=config)
    telephone = search
    # name = search["name"] if "name" in search else None
    start_time = time.time()
    task = f"""
    Follow these instructions:
    Check if the page shows a list of cars or a single car:
    1 - If no car information is found: 
        - "No car information found with the given data."
    2 - If a list of elements (users) is displayed:
        - Return the car names displayed.
    3 - If a single car is displayed:
        - Return the name of the car.
    4 - There's multiple companies
        return the name of the company
    """
    # Pass the sensitive data to the agent
    initial_actions = [
	{'go_to_url': {'url': 'https://toyosteu.sdswebapp.com:6819/SDSWeb/login'}},
	{'input_text': {'index': 4, 'text': os.getenv('USERNAME_SDS')}, "has_sensitive_data": True},
	{'input_text': {'index': 7, 'text': os.getenv('PASSWORD_SDS')}, "has_sensitive_data": True},
	{'send_keys': {"keys":"Enter"}}, # Login
	# {'click_element': {'index': 11}},
	{'click_element': {'index': 12}}, # Redez-vous
    {'wait': {'seconds': 2}},
	{'click_element': {'index': 8}}, # Options
    {'wait': {'seconds': 2}},
    {'input_text': {'index': 37, 'text': telephone, "xpath":'//*[@id="CUSTOMER_PHONE"]'}}, # Telephone
    ]
    # if name:
    #     initial_actions.append({'input_text': {'index': 41, 'text': name, "xpath":'//*[@id="CUSTOMER_NAME"]"]'}})
    initial_actions.append({'click_element': {'index': 29}})
        # agent = Agent(task=task, llm=ChatOpenAI(model="gpt-4o"),initial_actions=initial_actions, sensitive_data=sensitive_data)
    agent = Agent(task=task, llm=ChatOpenAI(model="gpt-4o"),initial_actions=initial_actions,browser=browser)
    history =  await agent.run()
    result = history.final_result()
    extracted = history.extracted_content()
    await agent.browser.close()
    end_time  = time.time()
    execution_time = end_time - start_time
    print(f"⌚Execution time: {execution_time} seconds")
    if result:
        return result
    else:
        return extracted[len(extracted)-1]
        

async def make_appointament(info):
    
    # browser_context = BrowserContext(browser=browser)
    service_id = info["service_id"]
    telephone = info["telephone"]
    date = info["date"]
    car = info["car"]
    trasnport_mode = info["transport_mode"]
    # name = info["name"] if "name" in info else None
    start_time = time.time()
    initial_task = f"""
    Book a car service appointment using the SDSweb platform.

    Instructions:
    If no car information is found, return: "No car information found with the given data."

    [Optional] Select Car
    If prompted to choose a car from a list, select the car labeled and click: {car}

    Book a car service appointment using the SDSweb platform.
    Instructions:
    Navigate to Services
    Click the Services Element on the right of the element Revision.
    
    Add a Service
    Click the "+" (plus) button at the top-right of the screen to display service options with the index of 15.

    Enter Service Code
    In the "Code OP (Trv/Table)" input field, enter the following service code: {service_id}
    """
    # Click the double arrow ("»") located at the top-right of the webpage with index around 25 to enter the Services section.
    taskAddService = f"""
    Book a car service appointment using the SDSweb platform.
    Instructions:
    Navigate to Services
    Click the Services Element on the right of the element Revision.
    
    Add a Service
    Click the "+" (plus) button at the top-right of the screen to display service options with the index of 15.

    Enter Service Code
    In the "Code OP (Trv/Table)" input field, enter the following service code: {service_id}

    If the service code was entered successfully, you will see the service on the main page. With that return: "Success"
    else, return: "Failed"
    """
    task = f""""
    Book a car service appointment using the SDSweb platform.

    Instructions:
    If no car information is found, return: "No car information found with the given data."

    [Optional] Select Car
    If prompted to choose a car from a list, select the car labeled: {car}

    Step 1: Navigate to Services
    Click the double arrow ("»") located at the top-right of the webpage with index around 25 to enter the Services section.

    Step 2: Add a Service
    Click the "+" (plus) button at the top-right of the screen to display service options with the index of 15.

    Step 3: Enter Service Code
    In the "Code OP (Trv/Table)" input field, enter the following service code: {service_id}

    Press Enter to confirm.

    A new service item should now appear in the list.

    Step 4: Go to the Schedule Page
    Again, click the double arrow ("»") at the top-right with index around 25 to go to the Schedule page.

    Step 5: Choose Transport Mode
    In the dropdown menu at the top-middle of the screen, select the transport mode labeled: {trasnport_mode}

    Step 6: Pick a Date and Time
    In the middle section of the screen, locate the calendar/scheduler.

    Navigate to the date: {date}

    Click to choose the correct hour on that date.

    Step 7: Enter "Pris par" Code
    In the "Pris par" field, enter the following code: 5543

    Step 8: Finalize Appointment
    Click the "Finished" banner/button located at the top-right of the screen.

    If the button does not appear, assume that the form is incomplete and the booking has failed.
    """
    # Pass the sensitive data to the agent
    initial_actions = [
	{'go_to_url': {'url': 'https://toyosteu.sdswebapp.com:6819/SDSWeb/login'}},
	{'input_text': {'index': 4, 'text': os.getenv('USERNAME_SDS')}, "has_sensitive_data": True},
	{'input_text': {'index': 7, 'text': os.getenv('PASSWORD_SDS')}, "has_sensitive_data": True},
	{'send_keys': {"keys":"Enter"}}, # Login
	# {'click_element': {'index': 11}},
	{'click_element': {'index': 12}}, # Redez-vous
	{'wait': {'seconds': 2}},
	{'click_element': {'index': 8}}, # Options
    {'input_text': {'index': 37, 'text': telephone, "xpath":'//*[@id="CUSTOMER_PHONE"]'}}, # Telephone
    ]
    # if name:
    #     initial_actions.append({'input_text': {'index': 41, 'text': name, "xpath":'//*[@id="CUSTOMER_NAME"]"]'}})
    initial_actions.append({'click_element': {'index': 29}})
    browser = None # Initialize browser to None for finally block safety
    try:
        # Launch the browser instance
        # Assuming Browser() handles launching. Adjust if using Playwright directly.
        # If Browser is just a wrapper, you might need playwright.chromium.launch() etc.
        browser = Browser(config=config)

        # Create ONE context for the entire session
        # async with await browser.new_context() as context: # Use 'context' variable here
        context = await browser.new_context()
        controller = Controller(exclude_actions=['open_tab', 'search_google'])

        # Agent 0: Login and Car Selection
        print("Running Agent 0: Login and Car Selection...")
        # Pass the ACTUAL 'context' object to the agent
        agent0 = Agent(task=initial_task, llm=ChatOpenAI(model="gpt-4o"), initial_actions=initial_actions, browser=browser, controller=controller, context=context)
        historyInitial = await agent0.run()
        result0 = historyInitial.final_result()
        print(f"Agent 0 Result: {result0}")

        if "Failed" in result0 or "No car information found" in result0:
                print(f"Process stopped after Agent 0: {result0}")
                # No need to return here if finally block handles cleanup
                raise Exception(f"Agent 0 Failed: {result0}") # Raise exception to trigger finally

        # Agent 1: Add Service
        # This agent continues in the SAME context, no initial_actions needed
        print("Running Agent 1: Add Service...")
        # Pass the SAME 'context' object
        agent1 = Agent(task=taskAddService, llm=ChatOpenAI(model="gpt-4o"), browser=browser, controller=controller, context=context)
        historyService = await agent1.run()
        result1 = historyService.final_result()
        print(f"Agent 1 Result: {result1}")

        if "Failed" in result1:
            print(f"Process stopped after Agent 1: {result1}")
            raise Exception(f"Agent 1 Failed: {result1}") # Raise exception

        # Agent 2: Schedule and Finalize (Uncommented and corrected)
        print("Running Agent 2: Schedule and Finalize...")
        # Pass the SAME 'context' object
        # agent2 = Agent(task=taskScheduleFinalize, llm=ChatOpenAI(model="gpt-4o"), browser=browser, controller=controller, context=context)
        # historyFinal = await agent2.run()
        # result2 = historyFinal.final_result()
        # print(f"Agent 2 Result: {result2}")

        # if "Failed" in result2:
        #      print(f"Process stopped after Agent 2: {result2}")
        #      raise Exception(f"Agent 2 Failed: {result2}") # Raise exception

        # If all agents succeeded
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"⌚Execution time: {execution_time} seconds")
        print("Appointment booking process completed successfully.")
        return "Success" # Or return more detailed success info

    except Exception as e:
        print(f"An error occurred during the process: {e}")
        # Optionally log the full traceback
        # import traceback
        # traceback.print_exc()
        return f"Failed due to an error: {e}"

    finally:
        # Cleanup: The 'async with' statement handles context closing automatically.
        # You primarily need to ensure the browser instance is closed if you launched it.
        print("Starting cleanup...")
        if browser:
             # Check if the specific library requires an await for closing
             # Check browser object type and method signature
             # E.g., if it's raw Playwright: await browser.close()
             # If it's a wrapper, it might be browser.close() or await browser.close_async() etc.
             try:
                 # Attempt to close, adjust based on your Browser class implementation
                 if hasattr(browser, 'close_async') and callable(browser.close_async):
                      await browser.close_async()
                 elif hasattr(browser, 'close') and callable(browser.close):
                     # Check if close is async or sync
                     import inspect
                     if inspect.iscoroutinefunction(browser.close):
                         await browser.close()
                     else:
                         browser.close() # Or run in executor if it's blocking sync
                 print("Browser closed.")
             except Exception as close_err:
                 print(f"Error closing browser: {close_err}")
        else:
            print("Browser object was not initialized.")
        print("Cleanup finished.")
    # if result:
    #     return result
    # else:
    #     return extracted[len(extracted)-1]
# Define FastAPI route
@app.get("/")
def index():
    """
    API endpoint to welcome.
    Example: GET /
    """
    return {"message": "Hello world"}

@app.get("/get_cars")
@app.get("/get_cars")
async def get_car_info_api(search_json_string: str):
    """
    API endpoint to scrape the SDSweb to get info of cars.
    Example: GET /get_cars?search_json_string=<search_info_string>
    Format of params: 
    search_json_string: {"telephone": "5142069161"}
    """
    if search_json_string == None or search_json_string == "":
        return {"message": "No data sent"}
    tel = search_json_string
    # result = await get_cars(json.loads(search_json_string))
    result = await get_cars(tel)
    return {"web_scrape_info": result}

@app.get("/current_appointments")
def get_appoitments():
    """
    Get current marked appointments (dates only).
    """
    result = read_json_file()
    return result

@app.get("/appointments_number")
def get_appoitments_number(telephone: str):
    """
    Get array of marked appointments related to a telephone number.
    """
    result = get_all_appointments_number(telephone)
    return result

class AppointmentHourInfo(BaseModel):
    date: str

@app.post("/check_appointment_availability")
def check_appoitment_availability(info: AppointmentHourInfo):
    """
    Check appointment availability for a specific date.
    {"date":"YYYY-MM-DD"}
    """
    result = read_json_file()
    # read_json_file returns only the date part (YYYY-MM-DD), so comparison should be safe.
    return "It's not available" if info.date in result else "It's available"

class AppointmentInfo(BaseModel):
    service_id: Union[str, int]
    car: str
    telephone: str
    date: str
    transport_mode: str

@app.post("/make_appointment")
async def make_appointment_api(info: AppointmentInfo):
    """
    API endpoint to make appointments.
    
    Example: 
    POST /make_appointment
    Format of params: 
    {
        "service_id": "01TZZ1S16Z",
        "car": "AUDI Q5 2016",
        "telephone": "5145856444",
        "date": "2025-05-01T15:00:00",
        "transport_mode": "Reconduire"
    }
    """
    if not info.service_id:
        raise HTTPException(status_code=400, detail="Service number is required.") 
    
    try:
        # Check if the exact datetime is already booked
        # We need to read the full data to check for exact date and time conflicts
        with open(db_file, 'r') as f:
            existing_appointments = json.load(f)
        
        # Check for conflicts based on exact date and time string
        is_booked = any(
            appointment["date"] == info.date and appointment["telephone"] == info.telephone
            for appointment in existing_appointments
        )
        
        if is_booked: 
            return {
                "detail": "It's not available on the date and time given for this telephone number."
            } 
        else:
            info.service_id = str(info.service_id)
            result = write_json_file(info.model_dump()) # Use model_dump() to convert Pydantic model to dict
            return {
                "detail": "The appointment was successfully marked." if result 
                          else "Failed to mark the appointment."
            }
            
    except FileNotFoundError:
        # If db.json doesn't exist, create it with the new appointment
        info.service_id = str(info.service_id)
        result = write_json_file(info.model_dump())
        return {
            "detail": "The appointment was successfully marked." if result 
                      else "Failed to mark the appointment."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error making appointment: {str(e)}")

@app.delete("/delete_all_appointments/{telephone}")
def delete_all_appointments_api(telephone: str):
    """
    Delete all appointments for a given telephone number.
    Example: DELETE /delete_all_appointments/5145856444
    """
    success = delete_all_appointments(telephone)
    if success:
        return {"message": f"All appointments for telephone {telephone} deleted successfully."}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to delete appointments for telephone {telephone}.")

@app.delete("/delete_appointments_date")
def delete_appointments_date_api(telephone: str, date: str):
    """
    Delete appointments for a specific telephone number and date.
    Example: DELETE /delete_appointments_date?telephone=5145856444&date=2025-05-22
    Date format: YYYY-MM-DD (or YYYY-MM-DDTHH:MM:SS)
    """
    success = delete_appointments_date(telephone, date)
    if success:
        return {"message": f"Appointments for telephone {telephone} on {date} deleted successfully."}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to delete appointments for telephone {telephone} on {date}.")
