from .scrapper import Scrapper, RetryConfig, NavigationError, ElementNotFoundError
import logging
import os
from playwright.async_api import Playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from models.schemas import AppointmentInfo
from dotenv import load_dotenv
from datetime import datetime, timedelta
from db.database_availability import insert_appointment_db, Appointment

load_dotenv(override=True)
logger = logging.getLogger(__name__)


class MakeAppointmentScrapper(Scrapper):
    transport_types = ["aucun", "courtoisie", "attente", "reconduire", "laisser"]

    def __init__(self, config: AppointmentInfo):
        super().__init__(config.telephone)
        self.config = config

    async def makeAppointment(self):
        """Public method to create appointment"""
        return await self.action()

    # ==================== Helper Functions ====================

    def data_index(self, timeHM: str) -> int:
        """
        Get the correct position of the time on the schedule table.
        
        Args:
            timeHM: Time in HH:MM format
            
        Returns:
            Index of the position (1-based)
            
        Raises:
            ValueError: If time format is invalid or out of bounds
        """
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
            raise ValueError(
                f"Time is out of bounds (must be between {START_TIME_STR} and {END_TIME_STR}, exclusive)"
            )

        delta = target_dt - start_dt
        total_minutes = delta.total_seconds() / 60
        index = int(total_minutes // INTERVAL_MINUTES) + 1
        
        # Adjust for afternoon times
        if int(timeHM.split(":")[0]) >= 12:
            index += 1
            
        return index

    def get_weeks_until_date(self, target_datetime_str: str) -> tuple[int, str, str]:
        """
        Calculate weeks until target date and extract day/time info.
        
        Args:
            target_datetime_str: Date/time in "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DD HH:MM:SS" format
            
        Returns:
            Tuple of (full_weeks, weekday_name, time_HH:MM)
            
        Raises:
            ValueError: If datetime format is invalid
        """
        try:
            target_datetime = datetime.strptime(target_datetime_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            try:
                target_datetime = datetime.strptime(target_datetime_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise ValueError(
                    "target_datetime_str must be in 'YYYY-MM-DDTHH:MM:SS' or 'YYYY-MM-DD HH:MM:SS' format"
                )

        current_date = datetime.now().date()
        target_date = target_datetime.date()

        current_monday = current_date - timedelta(days=current_date.weekday())
        target_monday = target_date - timedelta(days=target_date.weekday())

        delta_days = (target_monday - current_monday).days
        full_weeks = delta_days // 7

        return full_weeks, target_datetime.strftime("%A"), target_datetime.strftime("%H:%M")

    # ==================== Navigation & Operations ====================

    async def navigate_to_car_page(self) -> None:
        """Navigate to the car selection page and proceed"""
        with self._track_operation("navigate_to_car_page"):
            logger.info("Verifying we are on the car info page")
            
            await self.wait_for_selector_safe(
                self.selectors["make-appointment"]["car-page"],
                timeout=self.timeout.MEDIUM
            )
            
            if not await self.click_with_retry(
                self.selectors["make-appointment"]["next-step"],
                timeout=self.timeout.DEFAULT
            ):
                raise NavigationError("Failed to proceed from car info page")
            
            logger.info("Successfully navigated past car info page")

    async def add_service_operation(self) -> None:
        """Add service operation to the appointment"""
        with self._track_operation("add_service_operation"):
            logger.info(f"Adding operation: {self.config.service_id}")
            
            # Click add operation button
            if not await self.click_with_retry(
                self.selectors["make-appointment"]["add-operation-button"],
                timeout=self.timeout.MEDIUM
            ):
                raise ElementNotFoundError("Add operation button not found")
            
            # Fill operation input
            await self.wait_for_selector_safe(
                self.selectors["make-appointment"]["operation-input"],
                timeout=self.timeout.MEDIUM
            )
            
            if not await self.fill_with_retry(
                self.selectors["make-appointment"]["operation-input"],
                self.config.service_id
            ):
                raise ElementNotFoundError("Operation input field not found")
            
            await self.page.keyboard.press("Enter")
            await self.page.click("body")  # Dismiss any dropdowns
            
            # Proceed to next step
            await self.wait_for_selector_safe(
                self.selectors["make-appointment"]["next-step"],
                timeout=self.timeout.MEDIUM
            )
            
            if not await self.click_with_retry(
                self.selectors["make-appointment"]["next-step"]
            ):
                raise NavigationError("Failed to proceed after adding operation")
            
            logger.info("Successfully added service operation")

    async def select_transport_mode(self) -> None:
        """Select transport mode for the appointment"""
        logger.info(f"Selecting transport mode: {self.config.transport_mode}")
        
        transport_locator = self.page.locator(
            self.selectors["make-appointment"]["transport-input"]
        )
        
        for i, transport in enumerate(self.transport_types):
            if transport == self.config.transport_mode.lower():
                try:
                    await transport_locator.nth(i).click(timeout=self.timeout.DEFAULT)
                    logger.info(f"Successfully selected transport mode: {transport}")
                    return
                except Exception as e:
                    logger.error(f"Failed to select transport mode: {e}")
                    raise ElementNotFoundError(f"Transport mode '{transport}' not found")
        
        logger.warning(f"Transport mode '{self.config.transport_mode}' not found in list")

    async def navigate_to_week(self, weeks_to_click: int) -> None:
        """Navigate forward through calendar weeks"""
        logger.info(f"Navigating {weeks_to_click} weeks forward in calendar")
        
        for i in range(weeks_to_click):
            await self._safe_wait(300)  # Prevent stale element issues
            
            if not await self.click_with_retry(
                self.selectors["make-appointment"]["calender-next"],
                retry_config=RetryConfig(max_attempts=3, base_delay=0.3)
            ):
                raise NavigationError(f"Failed to navigate to week {i + 1}/{weeks_to_click}")
        
        logger.info(f"Successfully navigated {weeks_to_click} weeks")

    async def scroll_to_time_slot(self, time_index: int, day_index: int) -> bool:
        """
        Scroll the time slot into view using targeted scrolling.
        
        Args:
            time_index: Index of the time slot
            day_index: Index of the day (1-7)
            
        Returns:
            True if successful, False otherwise
        """
        time_slot_selector = (
            f"div[data-index='{time_index}'] "
            f"div div.css-122qvno.e1ri7uk73:nth-child({day_index})"
        )
        
        logger.info(f"Scrolling to time slot: index={time_index}, day={day_index}")
        logger.debug(f"Using selector: {time_slot_selector}")
        
        time_slot_locator = self.page.locator(time_slot_selector)
        scroll_container_selector = self.selectors["make-appointment"]["time-scrooler"]
        
        max_retries = 20
        for attempt in range(max_retries):
            # Check if element is visible
            try:
                if await time_slot_locator.is_visible():
                    logger.info(f"Time slot element is now visible (attempt {attempt + 1})")
                    return True
            except Exception as e:
                logger.debug(f"Visibility check failed: {e}")
            
            # Scroll if not visible
            logger.debug(f"Scrolling container... (Attempt {attempt + 1}/{max_retries})")
            try:
                await self.page.evaluate(f"""
                    let container = document.querySelector("{scroll_container_selector}");
                    if (container) {{
                        container.scrollBy(0, 200);
                    }}
                """)
                await self._safe_wait(300)
            except Exception as e:
                logger.warning(f"Scroll attempt {attempt + 1} failed: {e}")
        
        logger.error(f"Could not find time slot after {max_retries} attempts")
        return False

    async def select_time_slot(self, weekday: str, timeHM: str) -> None:
        """
        Select a specific time slot in the calendar.
        
        Args:
            weekday: Day of the week (e.g., "Monday")
            timeHM: Time in HH:MM format
            
        Raises:
            ElementNotFoundError: If time slot cannot be found or clicked
        """
        with self._track_operation("select_time_slot"):
            time_index = self.data_index(timeHM)
            day_index = self.daysWeek[weekday]
            
            logger.info(f"Selecting time slot: {weekday} at {timeHM} (index={time_index}, day={day_index})")
            
            # Scroll to time slot
            if not await self.scroll_to_time_slot(time_index, day_index):
                raise ElementNotFoundError(
                    f"Time slot not found after scrolling: {weekday} {timeHM}"
                )
            
            # Click the time slot
            time_slot_selector = (
                f"div[data-index='{time_index}'] "
                f"div div.css-122qvno.e1ri7uk73:nth-child({day_index})"
            )
            
            if not await self.click_with_retry(
                time_slot_selector,
                retry_config=RetryConfig(max_attempts=3, base_delay=0.5)
            ):
                raise ElementNotFoundError(f"Failed to click time slot: {weekday} {timeHM}")
            
            logger.info("Successfully selected time slot")

    async def finalize_appointment(self) -> None:
        """Finalize the appointment with advisor information"""
        with self._track_operation("finalize_appointment"):
            logger.info("Finalizing the appointment")
            
            # Enter advisor code
            taken_by_selector = self.selectors["make-appointment"]["taken-by"]
            await self.page.type(taken_by_selector, "5543")
            await self.page.click(taken_by_selector)  # Focus to ensure value is set
            
            # Wait for and click finalize button
            finalize_button = self.page.locator(
                self.selectors["make-appointment"]["finalize-qppointment"]
            )
            
            await finalize_button.wait_for(
                state="visible",
                timeout=self.timeout.MEDIUM
            )
            await finalize_button.click()
            
            logger.info("Clicked finalize button, waiting for confirmation")
            await self._safe_wait(2000)

    async def verify_appointment_creation(self) -> bool:
        """
        Verify that appointment was created successfully by checking URL.
        
        Returns:
            True if appointment was created, False otherwise
        """
        expected_url = f'{os.getenv("SDS_URL")}t1/appointments-qab/1'
        current_url = self.page.url
        
        if current_url == expected_url:
            logger.info("Appointment created successfully - URL verification passed")
            return True
        else:
            logger.error(f"Appointment creation failed - URL: {current_url}")
            return False

    # ==================== Main Scraper Method ====================

    async def scrapper(self, playwright: Playwright) -> dict:
        """
        Main scraping method to create an appointment.
        
        Returns:
            Dict with success message and appointment ID, or error message
        """
        browser = None

        try:
            # --- 1. BROWSER SETUP ---
            with self._track_operation("browser_setup"):
                chromium = playwright.chromium
                browser = await chromium.launch(
                    headless=False,
                    args=["--start-maximized"]
                )
                self.page = await browser.new_page(
                    viewport={"width": 1920, "height": 1080}
                )

            # --- 2. LOGIN AND NAVIGATION ---
            with self._track_operation("login_and_navigation"):
                await self.page.goto(
                    f"{os.getenv('SDS_URL')}/login",
                    wait_until="networkidle"
                )
                await self.login()
                await self.navigate_to_appointments()
                await self.insert_phone_number()

            # --- 3. CAR SELECTION ---
            with self._track_operation("car_selection"):
                logger.info("Handling car selection and intermediate popups")
                await self.select_car_by_parts(
                    *self.config.car.split(" ")  # "2020 TOYOTA CAMRY" -> year, maker, model
                )
                await self.clear_intermediate_popups()

            # --- 4. NAVIGATE TO CAR PAGE ---
            await self.navigate_to_car_page()

            # --- 5. ADD SERVICE OPERATION ---
            await self.add_service_operation()

            # --- 6. SCHEDULE APPOINTMENT ---
            with self._track_operation("schedule_appointment"):
                logger.info("Navigating calendar to schedule appointment")
                
                # Wait for calendar to load
                await self.wait_for_selector_safe(
                    self.selectors["make-appointment"]["calender-next"],
                    timeout=self.timeout.NAVIGATION
                )

                # Select transport mode
                await self.select_transport_mode()

                # Navigate to correct week and select time slot
                weeks, weekday, timeHM = self.get_weeks_until_date(self.config.date)
                await self.navigate_to_week(weeks)
                await self.select_time_slot(weekday, timeHM)

            # --- 7. FINALIZE APPOINTMENT ---
            await self.finalize_appointment()

            # --- 8. VERIFY SUCCESS ---
            if not await self.verify_appointment_creation():
                return {
                    "error": "Appointment creation failed",
                    "message": "URL verification failed"
                }

            # --- 9. SAVE TO DATABASE ---
            with self._track_operation("database_save"):
                appointment = Appointment(
                    telephone=self.config.telephone,
                    car=self.config.car,
                    service_code=self.config.service_id,
                    date=self.config.date,
                    transport_mode=self.config.transport_mode
                )
                appointment_id = insert_appointment_db(appointment)
                logger.info(f"Appointment saved to database with ID: {appointment_id}")

            return {
                "message": "Appointment made successfully",
                "id": appointment_id
            }

        except ValueError as e:
            error_msg = f"Invalid input data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg, "message": "Invalid appointment data"}

        except ElementNotFoundError as e:
            error_msg = f"Element not found: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg, "message": "Failed to find required element"}

        except NavigationError as e:
            error_msg = f"Navigation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg, "message": "Failed to navigate through appointment flow"}

        except PlaywrightTimeoutError as e:
            error_msg = f"Timeout error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg, "message": "Operation timed out"}

        except Exception as e:
            error_msg = f"Unexpected error during appointment creation: {str(e)}"
            logger.critical(error_msg, exc_info=True)
            return {"error": error_msg, "message": "Appointment creation failed"}

        finally:
            if browser:
                await browser.close()
                logger.info("Browser closed")