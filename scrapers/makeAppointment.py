from playwright.async_api import async_playwright, Playwright, Page
import os, time, logging
from datetime import datetime, timedelta
# from .const import selectors, login
from const import selectors, login
# from models.schemas import AppointmentInfo
from dotenv import load_dotenv
import asyncio
from dataclasses import dataclass
load_dotenv()

logger = logging.getLogger(__name__)
@dataclass
class AppointmentInfo:
    service_id: str
    car: str
    telephone: str
    date: str
    transport_mode: str


def get_weeks_until_date(target_datehour: str) -> tuple[int, str]:
    """Calculate how many full weeks from today until the given target datehour.

    Args:
        target_datehour (str): datehour in format YYYY-MM-DDTHH:MM:SS

    Returns:
        tuple: Number of full weeks and the day of the week when the target is reached.
    """
    # Parse the target datehour
    target_datetime = datetime.strptime(target_datehour, "%Y-%m-%dT%H:%M:%S")

    # Get today's date and strip time (use date only)
    current_date = datetime.now().date()
    target_date = target_datetime.date()

    # Align to Monday of current and target week
    current_monday = current_date - timedelta(days=current_date.weekday())
    target_monday = target_date - timedelta(days=target_date.weekday())

    # Calculate the number of full weeks between the two Mondays
    delta = target_monday - current_monday
    full_weeks = delta.days // 7

    # Return number of weeks and day of the week of the target date
    return full_weeks, target_datetime.strftime("%A")

async def make_appointment_scrape(info: AppointmentInfo):
    async with async_playwright() as playwright:
        result = await making_appointment(playwright, info)
        # You can add further processing for returned_data here
    return result

async def making_appointment(playwright: Playwright, info: AppointmentInfo) -> str:
    """Make an appointment

    Args:
        playwright (Playwright): Playwright Intializer
        info (AppointmentInfo): Information relevant to the appointment
    """

    service_id = info.service_id
    car = info.car
    telephone_number = info.telephone
    date = info.date
    transport_mode = info.transport_mode
    start_time = time.time()
    chromium = playwright.chromium
    browser = await chromium.launch(headless=False) # Set to True for production
    page = await browser.new_page()
    
    try:
        await page.goto(os.getenv("SDS_URL"), wait_until="networkidle")
        
        username = os.getenv('USERNAME_SDS')
        password = os.getenv('PASSWORD_SDS')
        print(f"INFO: Login")
        await login(page, username, password)
        await page.wait_for_selector(selectors["redenzvous"], timeout=15000)
        await page.click(selectors["redenzvous"])

        await page.wait_for_selector(selectors["popupAvisaur"], timeout=10000)
        await page.click(selectors["chris"])
        await page.wait_for_selector(selectors["telephoneInput"], timeout=10000)
        print(f"INFO: Searching with telephone number: {telephone_number}")
        await page.fill(selectors["telephoneInput"], str(telephone_number))
        await page.keyboard.press("Enter")

        print("INFO: Moving to car info")
        await page.wait_for_selector(selectors["car-page"], timeout=10000)
        await page.click(selectors["next-step"])
        
        print("INFO: Add operation to car")
        await page.wait_for_selector(selectors["add-operation-button"], timeout=10000)
        await page.click(selectors["add-operation-button"])
        
        await page.wait_for_selector(selectors["operation-input"], timeout=10000) # Wait for the container to appear
        await page.fill(selectors["operation-input"], service_id)
        await page.keyboard.press("Enter")
        # await page.wait_for_timeout(1000)
        await page.wait_for_selector(selectors["next-step"], timeout=10000) # Wait for the container to appear
        await page.click(selectors["next-step"])
        print("INFO: Schedule operation")
        await page.wait_for_selector(selectors["calender-next"],timeout=30000)
        await page.wait_for_timeout(1000)
        
        print("INFO: Schedule operation: chose the right week")
        clicks, weekday = get_weeks_until_date(date)
        for i in range(int(clicks)):
            await page.wait_for_timeout(500)
            await page.click(selectors["calender-next"])
        
        print("INFO: Schedule operation: chose the correct hour")
        
        await page.wait_for_timeout(30000)
        
        
    except Exception as e:  
        print(f"An error occurred: {e}")
    finally:
        await browser.close()
        end_time = time.time()
        execution_time = end_time - start_time
        # logging.info(f"INFO: Total execution time: {execution_time:.2f} seconds")
        print(f"INFO: Total execution time: {execution_time:.2f} seconds")
        return "Appotintment made successfully"

if __name__ == "__main__":
    info = AppointmentInfo(
        service_id="01TZZ1S16Z",
        car="TOYOTA RAV4 2022",
        telephone="5142069161",
        date="2025-07-01T15:00:00",
        transport_mode="None"
    )
    # print(get_weeks_until_date(info.date))
    result = asyncio.run(make_appointment_scrape(info))

    print(f"Final result: {result}")