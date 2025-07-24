from playwright.async_api import async_playwright, Playwright, Page
from datetime import datetime, timedelta
from .const import selectors, login, daysWeek, transport_types, insert_phone_number, click_redenvous, chose_aviseurs
# from const import selectors, login, daysWeek
from models.schemas import AppointmentInfo
import os, time, logging
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)
transport_types = ["aucun", "courtoisie", "attente", "reconduire", "laisser"]

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

async def handle_popup(page: Page, telephone_number: str, car: str) -> None:
    await page.wait_for_timeout(1000)
    logger.info(f" Checking for existing popup dialog for {telephone_number}")
    # Wait up to 2 seconds for the popup to appear instead of sleeping blindly
    popup_locator = page.locator(selectors["popupTitle"])
    count = await popup_locator.count()
    if count == 0:
        logger.info(f" No existing popup dialog found for {telephone_number}")
        return
    try:
        text = await popup_locator.text_content()
        logger.info(f" Existing popup dialog found for {telephone_number}: {text}")

        if text == "Rendez-vous existants":
            # More efficient way to click the ancestor button
            await page.locator(selectors["popupTitle-add-redenvous"]).locator("xpath=ancestor::button[1]").click()
            await page.wait_for_timeout(500)
            await popup_locator.wait_for(state="detached", timeout=2000)
            # Wait for popup to potentially change instead of using timeout
            # await page.wait_for_load_state('networkidle')
            logger.info(" Clicked to resolve 'Rendez-vous existants' popup")
            await handle_popup(page, telephone_number, car)
        
        elif text == "Véhicules":
            await find_car(page, car)
            await page.wait_for_timeout(500)
            await handle_popup(page, telephone_number, car)
            
    
    except TimeoutError:
        logger.info(f" No existing popup dialog found for {telephone_number}")



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
async def find_car(page: Page, car: str) -> str:
    """Find the car on the list

    Args:
        page (Page): Playwright page
        car (str): Car to find

    Returns:
        str: Determines if the car was found
    """
    located_cars = page.locator(selector=selectors["carsList"])
    count = await located_cars.count()
    for i in range(count):
        car_text = (await located_cars.nth(i).text_content()).strip()
        print(car_text, car)
        if car_text == car.strip():
            await located_cars.nth(i).click()
            break
    return "Car found"
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
    browser = await chromium.launch(headless=False, args=["--start-maximized"] ) # Set to True for production
    page = await browser.new_page(viewport={"width": 1920, "height": 1080})
    error_message = None
    try:
        await page.goto(f"{os.getenv("SDS_URL")}/login", wait_until="networkidle")
        
        username = os.getenv('USERNAME_SDS')
        password = os.getenv('PASSWORD_SDS')
        logger.info(f" Login")
        await login(page, username, password)
        logger.info(f" Pressing redenvous button")
        await click_redenvous(page)
        logger.info(f" Chosing avior button")
        await chose_aviseurs(page)
        logger.info(f" Searching with telephone number: {telephone_number}")
        await insert_phone_number(page, telephone_number)
        logger.info(f" Check for an existing appointment: {telephone_number}")
        await handle_popup(page, telephone_number, car)
        
        logger.info(" Moving to car info")
        await page.wait_for_selector(selectors["make-appointment"]["car-page"], timeout=10000)
        await page.click(selectors["make-appointment"]["next-step"])
        
        logger.info(" Add operation to car")
        await page.wait_for_selector(selectors["make-appointment"]["add-operation-button"], timeout=10000)
        await page.click(selectors["make-appointment"]["add-operation-button"])
        
        await page.wait_for_selector(selectors["make-appointment"]["operation-input"], timeout=10000) # Wait for the container to appear
        await page.fill(selectors["make-appointment"]["operation-input"], service_id)
        await page.keyboard.press("Enter")
        # await page.wait_for_timeout(1000)
        await page.wait_for_selector(selectors["make-appointment"]["next-step"], timeout=10000) # Wait for the container to appear
        await page.click(selectors["make-appointment"]["next-step"])
        logger.info(" Schedule operation")
        await page.wait_for_selector(selectors["make-appointment"]["calender-next"],timeout=30000)
        await page.wait_for_timeout(1000)
        logger.info(" Schedule operation: chose the right transport")
        locator = page.locator(selectors["make-appointment"]["transport-input"])
        for i, transport in enumerate(transport_types):
            if transport == transport_mode.lower():
                await locator.nth(i).click()
                break
        logger.info(" Schedule operation: chose the right week")
        clicks, weekday, timeHM = get_weeks_until_date(date)
        for i in range(int(clicks)):
            await page.wait_for_timeout(500)
            await page.click(selectors["make-appointment"]["calender-next"])
        
        logger.info(" Schedule operation: chose the correct hour")
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
                    logger.info(" Element found")
                    break
                except Exception as e:
                    logger.info(f" Element exists but failed to check. Error: {e}")
            else:
                logger.info(" Element not found yet. Scrolling...")

            await page.evaluate(f"""
                document.querySelector("{selectors["make-appointment"]['time-scrooler']}").scrollBy(0, 200);
            """)
            await page.wait_for_timeout(500)
            retries += 1
        if not found:
            logger.info("ERROR: Max retries reached. Element not found.")
        else:
            day = daysWeek[weekday]
            # Once the element is found, click the time-table
            await page.click(f"div[data-index='{time_index}'] div div.css-122qvno.e1ri7uk73:nth-child({day})")

        logger.info(" Schedule operation: chose the correct transport mode")
        
        await page.type(selectors["make-appointment"]["taken-by"], "5543")
        await page.click(selectors["make-appointment"]["finalize-qppointment"])
        # await page.wait_for_timeout(100000)
        logger.info(" Appointment made successfully")
        await page.wait_for_timeout(1500)
    except Exception as e:  
        error_message = f"An error occurred: {e}"
        logger.error(f"An error occurred: {e}")
    finally:
        await browser.close()
        end_time = time.time()
        execution_time = end_time - start_time
        # logging.info(f" Total execution time: {execution_time:.2f} seconds")
        logger.debug(f" Total execution time: {execution_time:.2f} seconds")
        if error_message:
            return error_message
        else:
            return "Appotintment made successfully"

if __name__ == "__main__":
    # info = AppointmentInfo(
    #     service_id="01TZZ1S16Z",
    #     car="TOYOTA RAV4 2022",
    #     telephone="5142433043",
    #     date="2025-07-01T15:00:00",
    #     transport_mode="None"
    # )
    # # logger.info(get_weeks_until_date(info.date))
    # result = asyncio.run(make_appointment_scrape(info))
    result = get_weeks_until_date("2026-07-01T15:00:00")
    logger.info(f"Final result: {result}")