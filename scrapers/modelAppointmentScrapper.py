from .scrapper import Scrapper
import logging
import os
from playwright.async_api import Playwright, Locator
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
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
        # --- BEST PRACTICE: Define timeouts in one place ---
        self.default_timeout = 10000
        self.quick_timeout = 2000

    async def makeAppointment(self):
        return await self.action()

    # --- HELPER FUNCTIONS: These are self-contained utilities ---

    
    def data_index(self, timeHM: str) -> int:
        START_TIME_STR = "06:45"
        END_TIME_STR = "22:00"
        INTERVAL_MINUTES = 15

        start_dt = datetime.strptime(START_TIME_STR, "%H:%M")
        end_dt = datetime.strptime(END_TIME_STR, "%H:%M")

        try:
            target_dt = datetime.strptime(timeHM, "%H:%M")
        except ValueError:
            raise ValueError("timeHM must be in HH:MM 24-hour format")

        if target_dt < start_dt or target_dt >= end_dt:
            raise ValueError(f"Time is out of bounds (must be between {START_TIME_STR} and {END_TIME_STR}, exclusive)")

        delta = target_dt - start_dt
        total_minutes = delta.total_seconds() / 60
        index = int(total_minutes // INTERVAL_MINUTES) + 1  # or remove +1 if 0-based
        if int(timeHM.split(":")[0]) >= 12:
            index += 1
        return index


    def get_weeks_until_date(self, target_datetime_str: str) -> tuple[int, str, str]:
        """
        Returns:
            - Number of full weeks between current Monday and target date's Monday
            - Weekday name of target date (e.g., "Monday")
            - Time of day in HH:MM format (e.g., "14:30")
        
        Accepted formats:
            - "YYYY-MM-DDTHH:MM:SS"
            - "YYYY-MM-DD HH:MM:SS"
        """
        try:
            target_datetime = datetime.strptime(target_datetime_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            try:
                target_datetime = datetime.strptime(target_datetime_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise ValueError("target_datetime_str must be in 'YYYY-MM-DDTHH:MM:SS' or 'YYYY-MM-DD HH:MM:SS' format")

        current_date = datetime.now().date()
        target_date = target_datetime.date()

        current_monday = current_date - timedelta(days=current_date.weekday())
        target_monday = target_date - timedelta(days=target_date.weekday())

        delta_days = (target_monday - current_monday).days
        full_weeks = delta_days // 7

        return full_weeks, target_datetime.strftime("%A"), target_datetime.strftime("%H:%M")



    async def _select_car_from_popup(self, car_name: str) -> None:
        """
        Waits for the 'Véhicules' popup and clicks on the button corresponding to the specified car.
        This is a critical step to ensure the correct vehicle is chosen before proceeding.
        """
        logger.info(
            f"Waiting for multiple cars popup to select '{car_name}'...")
        try:
            # Wait for the popup itself to be visible by its title.
            popup_title_selector = f'{self.selectors["popupTitle"]}:has-text("Véhicules"), {self.selectors["popupTitle"]}:has-text("VÃ©hicules")'
            await self.page.locator(popup_title_selector).wait_for(state="visible", timeout=self.default_timeout)
            logger.info("Multiple cars popup is visible.")

            # Find and click the specific car button
            year, maker, model = car_name.split(" ")
            car_buttons = self.page.locator(self.selectors["carsList"])
            count = await car_buttons.count()

            car_found = False
            for i in range(count):
                car_text = (await car_buttons.nth(i).text_content()).strip()
                if year in car_text and maker in car_text and model in car_text:
                    await car_buttons.nth(i).click()
                    car_found = True
                    break

            if not car_found:
                raise Exception(
                    f"Car '{car_name}' not found in the list of vehicles.")

            # Short wait for the click to process.
            await self.page.wait_for_timeout(500)
            logger.info(f"Successfully clicked on '{car_name}'.")

        except PlaywrightTimeoutError:
            logger.error("Timed out waiting for the multiple cars popup.")
            # This might not be an error if there's only one car, so we can continue.
            logger.info("Assuming single car for this user, proceeding.")
        except Exception as e:
            logger.error(
                f"An error occurred while selecting the car from the popup: {e}")
            raise e  # Re-raise the exception to stop the process

    async def _clear_all_intermediate_popups(self, max_attempts: int = 3) -> None:
        """
        Iteratively checks for and dismisses known intermediate popups until the page is clear.
        This handles 'Rendez-vous existants' and 'Révision des alertes'.
        """
        logger.info("Starting iterative popup clearing process...")
        for attempt in range(max_attempts):
            # Wait for potential popups to render
            await self.page.wait_for_timeout(1000)

            try:
                popup_title_loc = self.page.locator(
                    self.selectors["popupTitle"])
                if not await popup_title_loc.is_visible(timeout=self.quick_timeout):
                    logger.info("No more popups detected. Page is clear.")
                    return

                title = (await popup_title_loc.text_content() or "").strip()
                logger.info(
                    f"Attempt {attempt + 1}: Found popup with title '{title}'")

                if "Rendez-vous existants" in title:
                    logger.info("Handling 'Rendez-vous existants' popup.")
                    await self.page.locator(self.selectors["popupTitle-add-redenvous"]).locator("xpath=ancestor::button[1]").click()
                    continue

                elif "Révision des alertes" in title or "RÃ©vision des alertes" in title:
                    logger.info("Handling 'Révision des alertes' popup.")
                    # Easiest way to dismiss this one
                    await self.page.keyboard.press("Escape")
                    continue

                # If it's the 'Véhicules' popup, we assume _select_car_from_popup handled it.
                elif "Véhicules" in title or "VÃ©hicules" in title:
                    logger.warning(
                        "Car selection popup appeared again. Something might be wrong.")
                    # We break because this should have been handled already.
                    return

                else:
                    logger.info(
                        f"Detected an unhandled popup ('{title}'). Stopping clearing process.")
                    return

            except PlaywrightTimeoutError:
                logger.info(
                    f"No popups found within the timeout on attempt {attempt + 1}. Page is clear.")
                return
            except Exception as e:
                logger.warning(f"An error occurred during popup clearing: {e}")
                await self.page.keyboard.press("Escape")

        logger.warning("Reached max attempts for clearing popups.")

    # --- MAIN SCRAPPER METHOD: Refactored for resilience ---

    async def scrapper(self, playwright: Playwright) -> dict:
        browser = None
        error_message = None

        try:
            # --- 1. SETUP AND LOGIN ---
            chromium = playwright.chromium
            browser = await chromium.launch(headless=True, args=["--start-maximized"])
            self.page = await browser.new_page(viewport={"width": 1920, "height": 1080})

            await self.page.goto(f"{os.getenv('SDS_URL')}/login", wait_until="networkidle")
            await self.login()
            await self.click_redenvous()
            await self.chose_aviseurs()
            await self.insert_phone_number()

            # --- 2. ROBUST NAVIGATION TO CAR PAGE ---
            # This new section replaces the old `handle_popup` logic
            logger.info(
                "Now robustly handling car selection and intermediate popups.")
            await self._select_car_from_popup(self.config.car)
            await self._clear_all_intermediate_popups()

            # --- 3. VERIFY AND PROCEED TO OPERATIONS ---
            logger.info(
                "Verifying we are on the car info page before proceeding.")
            await self.page.wait_for_selector(self.selectors["make-appointment"]["car-page"], timeout=self.default_timeout)
            await self.page.click(self.selectors["make-appointment"]["next-step"])
            logger.info("Successfully navigated past car info page.")

            # --- 4. ADD OPERATION (Service) ---
            logger.info(f"Adding operation: {self.config.service_id}")
            await self.page.wait_for_selector(self.selectors["make-appointment"]["add-operation-button"], timeout=self.default_timeout)
            await self.page.click(self.selectors["make-appointment"]["add-operation-button"])

            await self.page.wait_for_selector(self.selectors["make-appointment"]["operation-input"], timeout=self.default_timeout)
            await self.page.fill(self.selectors["make-appointment"]["operation-input"], self.config.service_id)
            await self.page.keyboard.press("Enter")
            await self.page.click("body")  # To dismiss any dropdowns

            await self.page.wait_for_selector(self.selectors["make-appointment"]["next-step"], timeout=self.default_timeout)
            await self.page.click(self.selectors["make-appointment"]["next-step"])

            # --- 5. SCHEDULE THE APPOINTMENT ---
            logger.info("Navigating the calendar to schedule the appointment.")
            await self.page.wait_for_selector(self.selectors["make-appointment"]["calender-next"], timeout=30000)

            # Select transport mode
            transport_locator = self.page.locator(
                self.selectors["make-appointment"]["transport-input"])
            for i, transport in enumerate(self.transport_types):
                if transport == self.config.transport_mode.lower():
                    await transport_locator.nth(i).click()
                    break

            # Navigate to the correct week
            clicks, weekday, timeHM = self.get_weeks_until_date(
                self.config.date)
            for i in range(int(clicks)):
                # Small delay to prevent stale element issues
                await self.page.wait_for_timeout(300)
                await self.page.click(self.selectors["make-appointment"]["calender-next"])

            # Select the correct time slot
            # ... inside the scrapper method ...
            # Select the correct time slot
            logger.info(
                f"Attempting to select time slot for {weekday} at {timeHM}.")
            time_index = self.data_index(timeHM)
            day_index = self.daysWeek[weekday]
            time_slot_selector = f"div[data-index='{time_index}'] div div.css-122qvno.e1ri7uk73:nth-child({day_index})"
            print(time_slot_selector)
            time_slot_locator = self.page.locator(time_slot_selector)

            # NEW: Targeted scrolling loop
            max_retries = 20
            found = False
            for i in range(max_retries):
                # Check if the element is now visible in the viewport
                if await time_slot_locator.is_visible():
                    logger.info("Time slot element is now visible.")
                    found = True
                    break

                # If not visible, scroll the specific container down
                logger.info(
                    f"Scrolling container to find time slot... (Attempt {i+1}/{max_retries})")
                scroll_container_selector = self.selectors["make-appointment"]['time-scrooler']
                await self.page.evaluate(f"""
                    let container = document.querySelector("{scroll_container_selector}");
                    if (container) {{
                        container.scrollBy(0, 200);
                    }}
                """)
                await self.page.wait_for_timeout(300)  # Brief pause for scroll to render

            if not found:
                raise Exception(
                    f"Could not find time slot element after {max_retries} scroll attempts.")

            # Once found, click the element
            await time_slot_locator.click()
            
            logger.info("Successfully clicked the time slot.")
            # ...
            # --- 6. FINALIZE ---
            logger.info("Finalizing the appointment.")
            await self.page.type(self.selectors["make-appointment"]["taken-by"], "5543")
            await self.page.click(self.selectors["make-appointment"]["taken-by"])

            finalize_button = self.page.locator(
                self.selectors["make-appointment"]["finalize-qppointment"])
            await finalize_button.wait_for(state="visible", timeout=self.default_timeout)
            await finalize_button.click()

            logger.info(
                "Appointment made successfully. Waiting for confirmation.")
            # Wait for confirmation to appear / page to change
            await self.page.wait_for_timeout(2000)
            url = self.page.url
            if url == f'{os.getenv('SDS_URL')}t1/appointments-qab/1':
                logger.info("Appointment made successfully.")
            else:
                error_message = "Appointment creation failed."
                logger.error("Appointment creation failed.")

        except Exception as e:
            error_message = f"An error occurred during appointment creation: {e}"
            logger.error(error_message, exc_info=True)
            # You could add screenshot logic here for debugging
            # await self.page.screenshot(path=f"error_{self.config.telephone}.png")

        finally:
            if browser:
                await browser.close()

            if error_message:
                return {"error": error_message, "message": "Appointment creation failed"}
            else:
                appointment = Appointment(
                    telephone=self.config.telephone,
                    car=self.config.car,
                    service_code=self.config.service_id,  # if `service_id` maps to `service_code`
                    date=self.config.date,
                    transport_mode=self.config.transport_mode
                )
                appointment_id = insert_appointment_db(appointment)
                return {"message": "Appointment made successfully", "id": appointment_id}
