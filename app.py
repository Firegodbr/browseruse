import os, time, json
from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller,BrowserConfig, Browser, ActionResult
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from browser_use.browser.context import BrowserContext
from playwright.async_api import async_playwright

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

async def get_cars(search):
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
	{'click_element': {'index': 7}}, # Options
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
    agent.browser.close()
    end_time  = time.time()
    execution_time = end_time - start_time
    print(f"⌚Execution time: {execution_time} seconds")
    if result:
        return result
    else:
        return extracted[len(extracted)-1]
        

async def make_appointament(info):
    controller = Controller(exclude_actions=['open_tab', 'search_google'])
    
    browser = Browser(config=config)
    # browser_context = BrowserContext(browser=browser)
    service_id = info["service_id"]
    telephone = info["telephone"]
    date = info["date"]
    car = info["car"]
    trasnport_mode = info["transport_mode"]
    # name = info["name"] if "name" in info else None
    start_time = time.time()
    # task = f"""
    # Your objective is to make an appointment for a car service provided by the SDSweb
    # Follow these instructions:
    # *- If there's a list of choices of car to be made:
    #     - Chose the {car}
    # 1 - To go to service press on the double arrow on the top right of webpage to go to services: ">>"
    # 2 - Press the "+" button on the top right of the webpage to see the service options
    # 3 - On the "Code OP (Trv/Table)" input you ad this service code: {service_id}; You know press enter
    # 4 - We have new element added to the list of services, press the double arrow on the top right of webpage to go to schedule page: ">>"
    # 5 - On the middle top of the screen there's the dropdown menu, select the mode of transport you press and press the transport of: {trasnport_mode}
    # 6 - On the middle of the screen we have the scheduler, you press and go until this date and choses on the screen the correct hour within this date string: {date}
    # 7 - Now you add Pris par you add the code: 5543
    # 8 - Lastly you press the banner of finished in the top right of the screen to finish the appointment. If it didn't show up now all information was added correctly, them you say that you failed.

    # """
    initial_task = f"""
    Book a car service appointment using the SDSweb platform.

    Instructions:
    If no car information is found, return: "No car information found with the given data."

    [Optional] Select Car
    If prompted to choose a car from a list, select the car labeled and click: {car}

    If the car was selected successfully a new webpage with the car is displayed with info of the car, return: "Success"
    else, return: "Failed"
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
	{'click_element': {'index': 7}}, # Options
    {'input_text': {'index': 37, 'text': telephone, "xpath":'//*[@id="CUSTOMER_PHONE"]'}}, # Telephone
    ]
    # if name:
    #     initial_actions.append({'input_text': {'index': 41, 'text': name, "xpath":'//*[@id="CUSTOMER_NAME"]"]'}})
    initial_actions.append({'click_element': {'index': 29}})
    async with async_playwright() as p:
        browser = await p.chromium.launch(config=config)
        browser_context = await browser.new_context()
        # agent = Agent(task=task, llm=ChatOpenAI(model="gpt-4o"),initial_actions=initial_actions, sensitive_data=sensitive_data)
        agent0 = Agent(task=initial_task, llm=ChatOpenAI(model="gpt-4o"),initial_actions=initial_actions,browser=browser,controller=controller, context=browser_context)

        historyInitial = await agent0.run()
        if "Failed" in historyInitial.final_result():
            return "Failed to select the car. Please check the car name or the list of cars."
        # result0 = history.final_result()
        agent1 = Agent(task=taskAddService, llm=ChatOpenAI(model="gpt-4o"),browser=browser,controller=controller,context=browser_context)
        historyService=await agent1.run()
        if "Failed" in historyService.final_result():
            return "Failed to select the service."
        # extracted = history.extracted_content()
        agent1.browser.close()
        end_time  = time.time()
        execution_time = end_time - start_time
        print(f"⌚Execution time: {execution_time} seconds")
        if "Success" in historyService.final_result():
            return "Success"
        else:
            return "Failed to select the service."
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

class AppointmentInfo(BaseModel):
    service_id: str
    car: str
    telephone: str
    date: str
    transport_mode: str

@app.post("/make_appointment")
async def make_appointment_api(info: AppointmentInfo):
    """
    API endpoint to scrape the SDSweb to make appointments.
    
    Example: 
    POST /make_appointment
    Format of params: 
    {
        "service_id": "01TZZ1S16Z",
        "car": "AUDI Q5 2016",
        "telephone": "5145856444",
        "date": "2025-05-01-15:00",
        "transport_mode": "Reconduire"
    }
    """
    if not info.service_id:
        raise HTTPException(status_code=400, detail="Service number is required.")    
    try:
        result = await make_appointament(info.model_dump())  # Assuming make_appointment accepts a dictionary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during web scraping: {str(e)}")
    
    return {"web_scrape_info": result}