from playwright.async_api import async_playwright, Playwright, Page
import os, time, logging
from datetime import datetime, timedelta
from .const import selectors, login, daysWeek
# from const import selectors, login, daysWeek
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

def data_index(timeHM: str) -> int:
    """Get the correct position of the time on the schedule table

    Args:
        time (str): Time in HH:MM format

    Returns:
        int: index of the position starting from 1 and goes until 63
    """
    starts = "6:45"
    start_dt = datetime.strptime(starts, "%H:%M")
    target_dt = datetime.strptime(timeHM, "%H:%M")
    interval = 15  # minutes

    # Ensure the time is within the valid range
    if target_dt < start_dt or target_dt > datetime.strptime("22:00", "%H:%M"):
        raise ValueError("Time is out of bounds (must be between 06:45 and 22:00)")

    # Compute the number of intervals passed
    delta = target_dt - start_dt
    total_minutes = delta.total_seconds() / 60

    # Calculate the index (1-based)
    index = int(total_minutes // interval) + 2

    return index


def get_weeks_until_date(target_datehour: str) -> tuple[int, str, str]:
    """Calculate how many full weeks from today until the given target datehour.

    Args:
        target_datehour (str): datehour in format YYYY-MM-DDTHH:MM:SS

    Returns:
        tuple: Number of full weeks, day of the week, and time (HH:MM) of the target.
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
    return full_weeks, target_datetime.strftime("%A"),  target_datetime.strftime("%H:%M")

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
        clicks, weekday, timeHM = get_weeks_until_date(date)
        for i in range(int(clicks)):
            await page.wait_for_timeout(500)
            await page.click(selectors["calender-next"])
        
        print("INFO: Schedule operation: chose the correct hour")
        time_index = data_index(timeHM)
        max_retries = 20
        retries = 0
        found = False

        while not found and retries < max_retries:
            locator = page.locator(f"div[data-index='{time_index}']")
            if await locator.count() > 0:
                try:
                    await locator.scroll_into_view_if_needed()
                    found = True
                    print("INFO: Element found")
                    break
                except Exception as e:
                    print(f"INFO: Element exists but failed to check. Error: {e}")
            else:
                print("INFO: Element not found yet. Scrolling...")

            await page.evaluate(f"""
                document.querySelector("{selectors['time-scrooler']}").scrollBy(0, 200);
            """)
            await page.wait_for_timeout(500)
            retries += 1
        if not found:
            print("ERROR: Max retries reached. Element not found.")
        else:
            day = daysWeek[weekday]
            # Once the element is found, click the time-table
            await page.click(f"div[data-index='{time_index}'] div div.css-122qvno.e1ri7uk73:nth-child({day})")
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