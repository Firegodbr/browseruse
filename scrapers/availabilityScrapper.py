from scrapers.scrapper import Scrapper
from models.schemas import AppointmentAvailability
from playwright.async_api import Playwright
import os
import math
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
load_dotenv(override=True)


class AvailabilityScrapper(Scrapper):
    day_position = {"Sunday": 1, "Monday": 2, "Tuesday": 3, "Wednesday": 4,
                    "Thursday": 5, "Friday": 6, "Saturday": 7}
    MAX_RETRIES = int(os.getenv("MAX_RETRIES_AVAILABILITY", 20))
    RETRY_DELAY_MS = int(os.getenv("RETRY_AVAILABILITY_DELAY_MS", 500))

    def __init__(self, config: AppointmentAvailability):
        super().__init__(config.telephone)
        self.config = config

    async def get_availability(self):
        return await self.action()

    def get_weeks_until_date(self,target_date: str) -> int:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        delta_days = (target - today).days
        return math.ceil(delta_days / 7)

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

    def timeframe_index(self, timeHM: str) -> tuple[int, int]:
        """Returns the start and end index of the timeframe

        Args:
            timeHM (str): Start time and end time in HH:MM-HH:MM format

        Returns:
            tuple[int, int]: Start index and end index
        """
        timeframe = timeHM.split("-")
        start_index = self.data_index(timeframe[0])
        end_index = self.data_index(timeframe[1])
        return start_index, end_index

    async def scroll_by(self, pixels: int) -> None:
        await self.page.evaluate(f"""
            document.querySelector("{self.selectors["make-appointment"]["time-scrooler"]}").scrollBy(0, {pixels});
        """)

    async def scroll_to_time(self) -> tuple[int, int, int, int]:
        start_timeframe, end_timeframe = self.timeframe_index(
            self.config.timeframe)
        number_of_timeframes = end_timeframe - start_timeframe + 1
        scroll_direction = -100 if start_timeframe <= 10 else 100
        retries = 0
        found = False

        logger.info(f"Checking availability for timeframe indices: {start_timeframe} to {end_timeframe}")
        scroll_amount = 0
        
        # Handle case where start and end timeframe are the same
        if start_timeframe == end_timeframe:
            logger.debug(f"Start and End timeframes are the same. Forcing small scroll to ensure proper visibility.")
            await self.scroll_by(scroll_direction)

        while not found and retries < self.MAX_RETRIES:
            locator = self.page.locator(f"div[data-index='{start_timeframe}']")
            if await locator.count() > 0:
                try:
                    await locator.scroll_into_view_if_needed()
                    found = True
                    logger.info(f"Time slot element at index {start_timeframe} found after {retries} retries.")
                    break
                except Exception as e:
                    logger.warning(f"Element found but failed to scroll. Error: {e}")
            else:
                logger.debug(f"Element at index {start_timeframe} not found. Retrying scroll...")

            await self.scroll_by(scroll_direction)
            scroll_amount += scroll_direction
            retries += 1

        if not found:
            raise Exception(f"Time slot element not found after {self.MAX_RETRIES} retries.")
        
        logger.info(f"Time slot element found at index {start_timeframe}.")
        return start_timeframe, end_timeframe, number_of_timeframes, scroll_amount

    async def scroll_to_timeframe_index(self, target_index: int) -> tuple[int, int]:
        # Use the container where scrolling *actually* happens (often parent)
        item_list = self.page.locator("div[data-testid='virtuoso-item-list']")
        scroll_step = 300
        max_attempts = 60
        first_index = None
        last_index = None

        for attempt in range(max_attempts):
            # Check if target index is rendered yet
            target_locator = self.page.locator(
                f"div[data-testid='virtuoso-item-list'] > div[data-index='{target_index}']"
            )
            if await target_locator.count() > 0:
                # await target_locator.first.scroll_into_view_if_needed()
                logger.info(f"Target index {target_index} is now visible.")
                return first_index, last_index

            # Get first/last visible indices
            first_child = item_list.locator(":scope > *").first
            last_child = item_list.locator(":scope > *").last

            first_index_str = await first_child.get_attribute("data-index")
            last_index_str = await last_child.get_attribute("data-index")

            if first_index_str is None or last_index_str is None:
                await self.page.wait_for_timeout(100)
                continue

            first_index = int(first_index_str)
            last_index = int(last_index_str)

            # If the target index is the same as first or last, force a small scroll to revalidate
            if target_index == first_index or target_index == last_index:
                logger.debug(f"Target index {target_index} matches first/last. Forcing small scroll.")
                await self.scroll_by(scroll_step)  # Small scroll to refresh the container

            if target_index > last_index:
                direction = "down"
                await self.scroll_by(scroll_step)
            elif target_index < first_index:
                direction = "up"
                await self.scroll_by(-scroll_step)
            else:
                direction = "waiting"

            logger.debug(
                f"Attempt {attempt}: First={first_index}, Last={last_index}, Target={target_index}, Scrolling {direction}"
            )

            await self.page.wait_for_timeout(250)

        raise Exception(f"X Failed to scroll to target index {target_index} after {max_attempts} attempts.")
    def format_time(self, time_str: str) -> str:
        return len(time_str.split(":")[0]) == 1 and f"0{time_str}" or time_str
    async def check_availability(self, start_timeframe: int, number_of_timeframes: int) -> dict:
        availability = {day: {} for day in self.config.days}
        print(f"Checking availability from index {start_timeframe} for {number_of_timeframes} slots")

        for tf_offset in range(number_of_timeframes):
            time_slot_index = start_timeframe + tf_offset
            retries = 0
            first_index, last_index = await self.scroll_to_timeframe_index(time_slot_index)
            # print(f"First index: {first_index}, Last index: {last_index}, target index: {time_slot_index}")

            time_slot_locator = None
            while retries < self.MAX_RETRIES:
                time_slot_locator = await self.page.query_selector(f"div[data-index='{time_slot_index}']")
                if time_slot_locator:
                    break
                await self.scroll_by(200)
                await self.page.wait_for_timeout(self.RETRY_DELAY_MS)
                retries += 1

            if time_slot_locator is None:
                logger.warning(f"Time slot {time_slot_index} not found after scrolling.")
                continue

            for day_name in self.config.days:
                day_index = self.day_position[day_name]
                try:
                    day_locator = await time_slot_locator.query_selector(
                        f"div.css-122qvno.e1ri7uk73:nth-child({day_index}) div.e1ri7uk72.KL-Tile-root:nth-child(1)"
                    )
                    if day_locator:
                        time = await day_locator.text_content()
                        day_locator_available = await time_slot_locator.query_selector(
                            f"div.css-122qvno.e1ri7uk73:nth-child({day_index}) div.e1ri7uk72.KL-Tile-root:not(.KL-Tile-disabled):nth-child(1)"
                        )
                        if day_locator_available:
                            text = await day_locator_available.text_content()
                        else:
                            text = None
                        logger.debug(f"{day_name} @ index {time}: {text}")
                        availability[day_name][self.format_time(time)] = text != None
                    else:
                        text = None
                        logger.warning(f"Time not found")
                except Exception as e:
                    logger.error(f"Error for {day_name} @ index {time_slot_index}: {e}")
                    availability[day_name]["Issue"] = None

        return availability


    async def check_calendar(self) -> dict:
        result = {}
        await self.page.wait_for_timeout(1000)
        # Keep scroll_to_time just to compute indices
        start_timeframe, end_timeframe, number_of_timeframes, _ = await self.scroll_to_time()
        print(f"Checking availability from index {start_timeframe} for {number_of_timeframes} slots")
        for _ in range(self.config.number_of_weeks):
            week = await self.page.query_selector(self.selectors["make-appointment"]["week"])
            result[await week.text_content()] = await self.check_availability(
                start_timeframe=start_timeframe,
                number_of_timeframes=number_of_timeframes
            )
            await self.page.wait_for_timeout(500)
            await self.page.click(self.selectors["make-appointment"]["calender-next"])
        return result

    async def scrapper(self, playwright: Playwright):
        results = {}
        chromium = playwright.chromium
        # Set to True for production
        browser = await chromium.launch(headless=True)
        self.page = await browser.new_page()

        try:
            await self.page.goto(f"{os.getenv('SDS_URL')}login", wait_until="networkidle")

            # Add your logic to scrape results here
            await self.login()

            await self.click_redenvous()

            await self.chose_aviseurs()

            await self.insert_phone_number()

            logger.info(" Moving to car info")
            await self.page.wait_for_selector(self.selectors["make-appointment"]["car-page"], timeout=10000)
            await self.page.click(self.selectors["make-appointment"]["next-step"])

            logger.info(" Add operation to car")
            await self.page.wait_for_selector(self.selectors["make-appointment"]["add-operation-button"], timeout=10000)
            await self.page.click(self.selectors["make-appointment"]["add-operation-button"])

            # Wait for the container to appear
            await self.page.wait_for_selector(self.selectors["make-appointment"]["operation-input"], timeout=10000)
            await self.page.fill(self.selectors["make-appointment"]["operation-input"], "01T4CLC8FZ")
            await self.page.keyboard.press("Enter")
            await self.page.click("body")

            await self.page.wait_for_selector(self.selectors["make-appointment"]["next-step"], timeout=10000)
            await self.page.click(self.selectors["make-appointment"]["next-step"])

            logger.info("Verifying availability")
            await self.page.wait_for_selector(self.selectors["make-appointment"]["calender-next"], timeout=30000)
            results = await self.check_calendar()

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await browser.close()

        return results
