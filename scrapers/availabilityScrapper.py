from scrapers.scrapper import Scrapper, RetryConfig, NavigationError, ElementNotFoundError
from models.schemas import AppointmentAvailability
from playwright.async_api import Playwright
import os
import math
from dotenv import load_dotenv
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
load_dotenv(override=True)


class AvailabilityScrapper(Scrapper):
    day_position = {
        "Sunday": 1, "Monday": 2, "Tuesday": 3, "Wednesday": 4,
        "Thursday": 5, "Friday": 6, "Saturday": 7
    }
    
    MAX_RETRIES = int(os.getenv("MAX_RETRIES_AVAILABILITY", 20))
    RETRY_DELAY_MS = int(os.getenv("RETRY_AVAILABILITY_DELAY_MS", 500))

    def __init__(self, config: AppointmentAvailability):
        super().__init__(config.telephone)
        self.config = config

    async def get_availability(self):
        """Public method to check availability"""
        return await self.action()

    # ==================== Helper Functions ====================

    def get_weeks_until_date(self, target_date: str) -> int:
        """
        Calculate number of weeks until target date.
        
        Args:
            target_date: Date in YYYY-MM-DD format
            
        Returns:
            Number of weeks (rounded up)
        """
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        delta_days = (target - today).days
        return math.ceil(delta_days / 7)

    def data_index(self, timeHM: str) -> int:
        """
        Get the correct position of the time on the schedule table.
        
        Args:
            timeHM: Time in HH:MM format
            
        Returns:
            Index of the position (1-based, starts at 6:45, 15-min intervals)
            
        Raises:
            ValueError: If time is out of bounds
        """
        START_TIME = "6:45"
        END_TIME = "22:00"
        INTERVAL_MINUTES = 15

        start_dt = datetime.strptime(START_TIME, "%H:%M")
        target_dt = datetime.strptime(timeHM, "%H:%M")
        end_dt = datetime.strptime(END_TIME, "%H:%M")

        # Validate time range
        if target_dt < start_dt or target_dt > end_dt:
            raise ValueError(
                f"Time is out of bounds (must be between {START_TIME} and {END_TIME})"
            )

        # Compute number of intervals
        delta = target_dt - start_dt
        total_minutes = delta.total_seconds() / 60
        index = int(total_minutes // INTERVAL_MINUTES) + 2

        return index

    def timeframe_index(self, timeHM: str) -> tuple[int, int]:
        """
        Returns the start and end index of the timeframe.
        
        Args:
            timeHM: Time range in HH:MM-HH:MM format
            
        Returns:
            Tuple of (start_index, end_index)
        """
        timeframe = timeHM.split("-")
        start_index = self.data_index(timeframe[0])
        end_index = self.data_index(timeframe[1])
        return start_index, end_index

    def format_time(self, time_str: str) -> str:
        """
        Format time string to ensure leading zero.
        
        Args:
            time_str: Time string that may be missing leading zero
            
        Returns:
            Properly formatted time string (HH:MM)
        """
        hour = time_str.split(":")[0]
        return f"0{time_str}" if len(hour) == 1 else time_str

    # ==================== Scrolling Operations ====================

    async def scroll_by_pixels(self, pixels: int) -> None:
        """
        Scroll the time container by specified pixels.
        
        Args:
            pixels: Number of pixels to scroll (positive = down, negative = up)
        """
        scroll_selector = self.selectors["make-appointment"]["time-scrooler"]
        
        try:
            await self.page.evaluate(f"""
                document.querySelector("{scroll_selector}").scrollBy(0, {pixels});
            """)
            await self._safe_wait(100)  # Brief wait for scroll to render
        except Exception as e:
            logger.warning(f"Scroll by pixels failed: {e}")

    async def scroll_to_timeframe_index(self, target_index: int) -> tuple[int, int]:
        """
        Scroll to make a specific time index visible in the viewport.
        
        Args:
            target_index: The data-index value to scroll to
            
        Returns:
            Tuple of (first_visible_index, last_visible_index)
            
        Raises:
            ElementNotFoundError: If target index cannot be reached
        """
        item_list = self.page.locator("div[data-testid='virtuoso-item-list']")
        scroll_step = 300
        max_attempts = 60
        first_index = None
        last_index = None

        for attempt in range(max_attempts):
            # Check if target is now visible
            target_locator = self.page.locator(
                f"div[data-testid='virtuoso-item-list'] > div[data-index='{target_index}']"
            )
            
            if await target_locator.count() > 0:
                logger.info(f"Target index {target_index} is now visible")
                return first_index, last_index

            # Get current visible range
            first_child = item_list.locator(":scope > *").first
            last_child = item_list.locator(":scope > *").last

            first_index_str = await first_child.get_attribute("data-index")
            last_index_str = await last_child.get_attribute("data-index")

            if first_index_str is None or last_index_str is None:
                await self._safe_wait(100)
                continue

            first_index = int(first_index_str)
            last_index = int(last_index_str)

            # If target matches boundary, force small scroll to refresh
            if target_index == first_index or target_index == last_index:
                logger.debug(f"Target {target_index} at boundary. Forcing refresh scroll.")
                await self.scroll_by_pixels(scroll_step)
                await self._safe_wait(250)
                continue

            # Determine scroll direction
            if target_index > last_index:
                direction = "down"
                await self.scroll_by_pixels(scroll_step)
            elif target_index < first_index:
                direction = "up"
                await self.scroll_by_pixels(-scroll_step)
            else:
                direction = "in range"
                logger.debug(f"Target {target_index} is in visible range")
                return first_index, last_index

            logger.debug(
                f"Attempt {attempt + 1}: First={first_index}, Last={last_index}, "
                f"Target={target_index}, Scrolling {direction}"
            )

            await self._safe_wait(250)

        raise ElementNotFoundError(
            f"Failed to scroll to target index {target_index} after {max_attempts} attempts"
        )

    async def scroll_to_time(self) -> tuple[int, int, int, int]:
        """
        Scroll to the configured timeframe in the schedule.
        
        Returns:
            Tuple of (start_timeframe, end_timeframe, number_of_timeframes, scroll_amount)
            
        Raises:
            ElementNotFoundError: If time slot cannot be found
        """
        start_timeframe, end_timeframe = self.timeframe_index(self.config.timeframe)
        number_of_timeframes = end_timeframe - start_timeframe + 1
        scroll_direction = -100 if start_timeframe <= 10 else 100
        
        logger.info(
            f"Checking availability for timeframe indices: {start_timeframe} to {end_timeframe}"
        )
        
        scroll_amount = 0
        
        # Handle case where start and end are the same
        if start_timeframe == end_timeframe:
            logger.debug("Start and end timeframes are the same. Forcing small scroll.")
            await self.scroll_by_pixels(scroll_direction)

        # Retry loop to find the element
        async def find_and_scroll():
            nonlocal scroll_amount
            retries = 0
            
            while retries < self.MAX_RETRIES:
                locator = self.page.locator(f"div[data-index='{start_timeframe}']")
                
                if await locator.count() > 0:
                    try:
                        await locator.scroll_into_view_if_needed()
                        logger.info(
                            f"Time slot at index {start_timeframe} found after {retries} retries"
                        )
                        return True
                    except Exception as e:
                        logger.warning(f"Element found but scroll failed: {e}")
                else:
                    logger.debug(f"Element at index {start_timeframe} not found. Retrying...")

                await self.scroll_by_pixels(scroll_direction)
                scroll_amount += scroll_direction
                retries += 1
                await self._safe_wait(self.RETRY_DELAY_MS)
            
            return False

        if not await find_and_scroll():
            raise ElementNotFoundError(
                f"Time slot element not found after {self.MAX_RETRIES} retries"
            )
        
        logger.info(f"Time slot element found at index {start_timeframe}")
        return start_timeframe, end_timeframe, number_of_timeframes, scroll_amount

    # ==================== Availability Checking ====================

    async def check_availability(
        self,
        start_timeframe: int,
        number_of_timeframes: int
    ) -> dict:
        """
        Check availability for specified timeframes across configured days.
        
        Args:
            start_timeframe: Starting time index
            number_of_timeframes: Number of time slots to check
            
        Returns:
            Dict mapping days to availability data
        """
        availability = {day: {} for day in self.config.days}
        logger.info(
            f"Checking availability from index {start_timeframe} "
            f"for {number_of_timeframes} slots"
        )

        for tf_offset in range(number_of_timeframes):
            time_slot_index = start_timeframe + tf_offset
            
            # Scroll to the time slot
            await self.scroll_to_timeframe_index(time_slot_index)
            
            # Find the time slot element with retry
            time_slot_locator = None
            
            async def find_time_slot():
                nonlocal time_slot_locator
                retries = 0
                
                while retries < self.MAX_RETRIES:
                    time_slot_locator = await self.page.query_selector(
                        f"div[data-index='{time_slot_index}']"
                    )
                    if time_slot_locator:
                        return True
                    
                    await self.scroll_by_pixels(200)
                    await self._safe_wait(self.RETRY_DELAY_MS)
                    retries += 1
                
                return False

            if not await find_time_slot():
                logger.warning(f"Time slot {time_slot_index} not found after scrolling")
                continue

            # Check each configured day
            for day_name in self.config.days:
                day_index = self.day_position[day_name]
                
                try:
                    # Selector for the day's time slot
                    day_selector = (
                        f"div.css-122qvno.e1ri7uk73:nth-child({day_index}) "
                        f"div.e1ri7uk72.KL-Tile-root:nth-child(1)"
                    )
                    day_locator = await time_slot_locator.query_selector(day_selector)
                    
                    if day_locator:
                        time = await day_locator.text_content()
                        
                        # Check if available (not disabled)
                        available_selector = (
                            f"div.css-122qvno.e1ri7uk73:nth-child({day_index}) "
                            f"div.e1ri7uk72.KL-Tile-root:not(.KL-Tile-disabled):nth-child(1)"
                        )
                        day_locator_available = await time_slot_locator.query_selector(
                            available_selector
                        )
                        
                        is_available = day_locator_available is not None
                        formatted_time = self.format_time(time)
                        
                        availability[day_name][formatted_time] = is_available
                        logger.debug(
                            f"{day_name} @ {formatted_time}: "
                            f"{'Available' if is_available else 'Not available'}"
                        )
                    else:
                        logger.warning(f"Time slot not found for {day_name} @ index {time_slot_index}")
                        
                except Exception as e:
                    logger.error(f"Error checking {day_name} @ index {time_slot_index}: {e}")
                    availability[day_name]["Error"] = str(e)

        return availability

    async def check_calendar(self) -> dict:
        """
        Check availability across multiple weeks in the calendar.
        
        Returns:
            Dict mapping week labels to availability data
            
        Raises:
            ElementNotFoundError: If calendar navigation fails
        """
        result = {}
        
        with self._track_operation("check_calendar"):
            await self._safe_wait(self.timeout.QUICK)
            
            # Get timeframe indices (only once)
            start_timeframe, end_timeframe, number_of_timeframes, _ = await self.scroll_to_time()
            
            logger.info(
                f"Checking availability from index {start_timeframe} "
                f"for {number_of_timeframes} slots across {self.config.number_of_weeks} weeks"
            )
            
            for week_num in range(self.config.number_of_weeks):
                # Get week label
                week_selector = self.selectors["make-appointment"]["week"]
                week_element = await self.page.query_selector(week_selector)
                
                if not week_element:
                    logger.warning(f"Week label not found for week {week_num + 1}")
                    week_label = f"Week {week_num + 1}"
                else:
                    week_label = await week_element.text_content()
                
                logger.info(f"Checking week: {week_label}")
                
                # Check availability for this week
                result[week_label] = await self.check_availability(
                    start_timeframe=start_timeframe,
                    number_of_timeframes=number_of_timeframes
                )
                
                # Navigate to next week if not last week
                if week_num < self.config.number_of_weeks - 1:
                    await self._safe_wait(500)
                    
                    if not await self.click_with_retry(
                        self.selectors["make-appointment"]["calender-next"],
                        retry_config=RetryConfig(max_attempts=3, base_delay=0.3)
                    ):
                        logger.error(f"Failed to navigate to week {week_num + 2}")
                        break

        return result

    # ==================== Main Scraper Method ====================

    async def scrapper(self, playwright: Playwright) -> dict:
        """
        Main scraping method to check appointment availability.
        
        Returns:
            Dict mapping weeks to day/time availability
        """
        results = {}
        browser = None

        try:
            # --- 1. BROWSER SETUP ---
            with self._track_operation("browser_setup"):
                chromium = playwright.chromium
                browser = await chromium.launch(headless=True)
                self.page = await browser.new_page()
                await self.page.set_viewport_size({"width": 1920, "height": 1080})

            # --- 2. LOGIN AND NAVIGATION ---
            with self._track_operation("login_and_navigation"):
                await self.page.goto(
                    f"{os.getenv('SDS_URL')}login",
                    wait_until="networkidle"
                )
                await self.login()
                await self.navigate_to_appointments()
                await self.insert_phone_number()

            # --- 3. NAVIGATE TO CAR PAGE ---
            with self._track_operation("navigate_to_car_page"):
                logger.info("Moving to car info page")
                await self.wait_for_selector_safe(
                    self.selectors["make-appointment"]["car-page"],
                    timeout=self.timeout.MEDIUM
                )
                
                if not await self.click_with_retry(
                    self.selectors["make-appointment"]["next-step"]
                ):
                    raise NavigationError("Failed to proceed from car page")

            # --- 4. ADD OPERATION ---
            with self._track_operation("add_operation"):
                logger.info("Adding operation to car")
                
                # Click add operation button
                await self.wait_for_selector_safe(
                    self.selectors["make-appointment"]["add-operation-button"],
                    timeout=self.timeout.MEDIUM
                )
                
                if not await self.click_with_retry(
                    self.selectors["make-appointment"]["add-operation-button"]
                ):
                    raise ElementNotFoundError("Add operation button not found")

                # Fill operation code
                await self.wait_for_selector_safe(
                    self.selectors["make-appointment"]["operation-input"],
                    timeout=self.timeout.MEDIUM
                )
                
                if not await self.fill_with_retry(
                    self.selectors["make-appointment"]["operation-input"],
                    "01T4CLC8FZ"
                ):
                    raise ElementNotFoundError("Operation input not found")
                
                await self.page.keyboard.press("Enter")
                await self.page.click("body")  # Dismiss dropdown

                # Proceed to next step
                await self.wait_for_selector_safe(
                    self.selectors["make-appointment"]["next-step"],
                    timeout=self.timeout.MEDIUM
                )
                
                if not await self.click_with_retry(
                    self.selectors["make-appointment"]["next-step"]
                ):
                    raise NavigationError("Failed to proceed after adding operation")

            # --- 5. CHECK AVAILABILITY ---
            logger.info("Verifying availability")
            await self.wait_for_selector_safe(
                self.selectors["make-appointment"]["calender-next"],
                timeout=self.timeout.NAVIGATION
            )
            
            results = await self.check_calendar()
            
            logger.info(f"Successfully checked availability for {len(results)} weeks")

        except ValueError as e:
            logger.error(f"Invalid configuration: {e}", exc_info=True)
            results = {"error": f"Invalid configuration: {str(e)}"}

        except ElementNotFoundError as e:
            logger.error(f"Element not found: {e}", exc_info=True)
            results = {"error": f"Element not found: {str(e)}"}

        except NavigationError as e:
            logger.error(f"Navigation failed: {e}", exc_info=True)
            results = {"error": f"Navigation failed: {str(e)}"}

        except Exception as e:
            logger.critical(f"Unexpected error: {e}", exc_info=True)
            results = {"error": f"An unexpected error occurred: {str(e)}"}

        finally:
            if browser:
                await browser.close()
                logger.info("Browser closed")

        return results