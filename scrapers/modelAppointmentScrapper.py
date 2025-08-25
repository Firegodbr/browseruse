from .scrapper import Scrapper
import logging
import os
from playwright.async_api import Playwright
from models.schemas import AppointmentInfo
from dotenv import load_dotenv
from datetime import datetime, timedelta
from db.database_availability import insert_appointment_db, Appointment
load_dotenv(override=True)

logger = logging.getLogger(__name__)


class MakeAppointmentScrapper(Scrapper):
    transport_types = ["aucun", "courtoisie",
                       "attente", "reconduire", "laisser"]

    def __init__(self, config: AppointmentInfo):
        super().__init__(config.telephone)
        self.config = config

    async def makeAppointment(self):
        return await self.action()

    def data_index(self, timeHM: str) -> int:
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
            raise ValueError(
                "Time is out of bounds (must be between 06:45 and 22:00)")

        # Compute the number of intervals passed
        delta = target_dt - start_dt
        total_minutes = delta.total_seconds() / 60

        # Calculate the index (1-based)
        index = int(total_minutes // interval) + 2

        return index

    def get_weeks_until_date(self, target_datehour: str) -> tuple[int, str, str]:
        """Calculate how many full weeks from today until the given target datehour.

        Args:
            target_datehour (str): datehour in format YYYY-MM-DDTHH:MM:SS

        Returns:
            tuple: Number of full weeks, day of the week, and time (HH:MM) of the target.
        """
        # Parse the target datehour
        target_datetime = datetime.strptime(
            target_datehour, "%Y-%m-%dT%H:%M:%S")

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

    async def find_car(self, car: str) -> str:
        """Find the car on the list

        Args:
            page (Page): Playwright page
            car (str): Car to find

        Returns:
            str: Determines if the car was found
        """
        located_cars = self.page.locator(selector=self.selectors["carsList"])
        count = await located_cars.count()
        year, maker, model = car.split(" ")
        for i in range(count):
            car_text = (await located_cars.nth(i).text_content()).strip()
            print(car_text, car)
            if year in car_text and maker in car_text and model in car_text:
                await located_cars.nth(i).click()
                break
        return "Car found"

    async def handle_popup(self, car: str) -> None:
        await self.page.wait_for_timeout(1000)
        logger.info(
            f" Checking for existing popup dialog for {self.telephone}")
        # Wait up to 2 seconds for the popup to appear instead of sleeping blindly
        popup_locator = self.page.locator(self.selectors["popupTitle"])
        count = await popup_locator.count()
        if count == 0:
            logger.info(
                f" No existing popup dialog found for {self.telephone}")
            return
        try:
            text = await popup_locator.text_content()
            logger.info(
                f" Existing popup dialog found for {self.telephone}: {text}")

            if text == "Rendez-vous existants":
                # More efficient way to click the ancestor button
                await self.page.locator(self.selectors["popupTitle-add-redenvous"]).locator("xpath=ancestor::button[1]").click()
                await self.page.wait_for_timeout(500)
                await popup_locator.wait_for(state="detached", timeout=2000)
                # Wait for popup to potentially change instead of using timeout
                # await page.wait_for_load_state('networkidle')
                logger.info(
                    " Clicked to resolve 'Rendez-vous existants' popup")
                await self.handle_popup(car)

            elif text == "Véhicules":
                await self.find_car(car)
                await self.page.wait_for_timeout(500)
                await self.handle_popup(car)

        except TimeoutError:
            logger.info(
                f" No existing popup dialog found for {self.telephone}")

    async def scrapper(self, playwright: Playwright) -> dict:

        service_id = self.config.service_id
        car = self.config.car
        telephone_number = self.config.telephone
        date = self.config.date
        transport_mode = self.config.transport_mode
        chromium = playwright.chromium
        # Set to True for production
        browser = await chromium.launch(headless=True, args=["--start-maximized"])
        self.page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        error_message = None
        try:
            await self.page.goto(f"{os.getenv("SDS_URL")}/login", wait_until="networkidle")

            logger.info(f" Login")
            await self.login()
            logger.info(f" Pressing redenvous button")
            await self.click_redenvous()
            logger.info(f" Chosing avior button")
            await self.chose_aviseurs()
            logger.info(
                f" Searching with telephone number: {telephone_number}")
            await self.insert_phone_number()
            logger.info(
                f" Check for an existing appointment: {telephone_number}")
            await self.handle_popup(car)

            logger.info(" Moving to car info")
            await self.page.wait_for_selector(self.selectors["make-appointment"]["car-page"], timeout=10000)
            await self.page.click(self.selectors["make-appointment"]["next-step"])

            logger.info(" Add operation to car")
            await self.page.wait_for_selector(self.selectors["make-appointment"]["add-operation-button"], timeout=10000)
            await self.page.click(self.selectors["make-appointment"]["add-operation-button"])

            # Wait for the container to appear
            await self.page.wait_for_selector(self.selectors["make-appointment"]["operation-input"], timeout=10000)
            await self.page.fill(self.selectors["make-appointment"]["operation-input"], service_id)
            await self.page.keyboard.press("Enter")
            await self.page.click("body")
            # await page.wait_for_timeout(1000)
            # Wait for the container to appear
            await self.page.wait_for_selector(self.selectors["make-appointment"]["next-step"], timeout=10000)
            await self.page.click(self.selectors["make-appointment"]["next-step"])
            logger.info(" Schedule operation")
            await self.page.wait_for_selector(self.selectors["make-appointment"]["calender-next"], timeout=30000)
            await self.page.wait_for_timeout(1000)
            logger.info(" Schedule operation: chose the right transport")
            locator = self.page.locator(
                self.selectors["make-appointment"]["transport-input"])
            for i, transport in enumerate(self.transport_types):
                if transport == transport_mode.lower():
                    await locator.nth(i).click()
                    break
            logger.info(" Schedule operation: chose the right week")
            clicks, weekday, timeHM = self.get_weeks_until_date(date)
            for i in range(int(clicks)):
                await self.page.wait_for_timeout(500)
                await self.page.click(self.selectors["make-appointment"]["calender-next"])

            logger.info(" Schedule operation: chose the correct hour")
            time_index = self.data_index(timeHM)
            max_retries = 20
            retries = 0
            found = False

            while not found and retries < max_retries:
                locator = self.page.locator(f"div[data-index='{time_index}']")
                if await locator.count() > 0:
                    try:
                        await locator.scroll_into_view_if_needed()
                        found = True
                        logger.info(" Element found")
                        break
                    except Exception as e:
                        logger.info(
                            f" Element exists but failed to check. Error: {e}")
                else:
                    logger.info(" Element not found yet. Scrolling...")

                await self.page.evaluate(f"""
                    document.querySelector("{self.selectors["make-appointment"]['time-scrooler']}").scrollBy(0, 200);
                """)
                await self.page.wait_for_timeout(500)
                retries += 1
            if not found:
                logger.info("ERROR: Max retries reached. Element not found.")
            else:
                day = self.daysWeek[weekday]
                # Once the element is found, click the time-table
                await self.page.click(f"div[data-index='{time_index}'] div div.css-122qvno.e1ri7uk73:nth-child({day})")

            logger.info(
                " Schedule operation: chose the correct transport mode")

            await self.page.type(self.selectors["make-appointment"]["taken-by"], "5543")
            await self.page.click(self.selectors["make-appointment"]["taken-by"])
            try:
                await self.page.wait_for_selector(self.selectors["make-appointment"]["finalize-qppointment"], timeout=10000)
                await self.page.click(self.selectors["make-appointment"]["finalize-qppointment"], timeout=10000)
            except Exception as e:
                logger.error(f"An error occurred: {e}")
                error_message = "Appotintment was unable to be made on the last step. Please try again later with another time perhaps."
            # await page.wait_for_timeout(100000)
            logger.info(" Appointment made successfully")
            await self.page.wait_for_timeout(1500)
        except Exception as e:
            error_message = f"An error occurred: {e}"
            logger.error(f"An error occurred: {e}")
        finally:
            # logging.info(f" Total execution time: {execution_time:.2f} seconds")
            await browser.close()
            if error_message:
                return error_message
            else:
                appointment = Appointment(
                    telephone_number, car, service_id, date, transport_mode)
                id = insert_appointment_db(appointment)
                return {"message": "Appotintment made successfully", "id": id}
