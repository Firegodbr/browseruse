from .scrapper import Scrapper
import logging
import os
import db.database_ops as db
from playwright.async_api import Playwright, Locator, Page, ElementHandle
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv
from typing import List, Dict, Tuple, Optional, Union
import asyncio

load_dotenv(override=True)
logger = logging.getLogger(__name__)


class GetCarScrapper(Scrapper):
    def __init__(self, telephone: str, car: str = None):
        super().__init__(telephone)
        self.max_retries = 3
        self.default_timeout = 5000
        self.quick_timeout = 1000
        self.car = car
        self.service_defaults = {
            "SERVICE 1": {
                "service_id": "01T6C1S16Z",
                "service_name": "Car Regular Maintenance",
                "processing_time": 60
            },
            "SERVICE 2": {
                "service_id": "01T6C2S16Z",
                "service_name": "Car Regular Maintenance",
                "processing_time": 60
            },
            "SERVICE 3": {
                "service_id": "10T6C3S16Z",
                "service_name": "Car Regular Maintenance",
                "processing_time": 60
            }
        }

    async def _handle_immediate_popups(self, timeout: int = 2500) -> None:
        """
        Handles popups that may appear immediately after an action, before a full page navigation.
        This is a quick, targeted check for popups like 'Rendez-vous existants'.
        """
        logger.info(
            "Performing quick check for immediate popups before navigation...")
        try:
            # We specifically look for the "add appointment" button text which is unique to this popup
            popup_locator = self.page.locator(
                self.selectors["popupTitle-add-redenvous"])

            # Wait for the button to be visible with a short timeout
            await popup_locator.wait_for(state="visible", timeout=timeout)

            logger.info("Handling 'Rendez-vous existants' popup immediately.")

            # The locator for the button to click is more complex, traversing up the DOM
            # Note: This selector logic is based on the original _handle_appointment_popup
            btn = self.page.locator(
                self.selectors["popupTitle-add-redenvous"]).locator("..").locator("..").locator("..")
            await btn.click(timeout=self.quick_timeout)

            logger.info("'Rendez-vous existants' popup handled.")
            # Wait a moment for the action to register before the script proceeds to wait for navigation.
            await self.page.wait_for_timeout(500)

        except PlaywrightTimeoutError:
            # This is the expected and normal outcome if no immediate popup appears.
            logger.info(
                "No immediate popups found within the timeout. Proceeding...")
        except Exception as e:
            logger.warning(
                f"An error occurred during the immediate popup check: {e}")

    async def _clear_all_intermediate_popups(self, max_attempts: int = 3) -> None:
        """
        Iteratively checks for and dismisses known intermediate popups until the page is clear
        or max attempts are reached. This runs after page navigation.
        """
        logger.info("Starting iterative popup clearing process on new page...")
        for attempt in range(max_attempts):
            # Wait for potential popups to render
            await self.page.wait_for_timeout(1000)

            try:
                popup_title_loc = self.page.locator(
                    self.selectors["popupTitle"])
                if not await popup_title_loc.is_visible(timeout=self.quick_timeout):
                    logger.info(
                        "No more popups detected. Page should be clear.")
                    return  # Exit the loop and function

                title = (await popup_title_loc.text_content()) or ""
                logger.info(
                    f"Attempt {attempt + 1}: Found popup with title '{title}'")

                # Handle known intermediate popups
                if "Rendez-vous existants" in title:
                    logger.info("Handling 'Rendez-vous existants' popup.")
                    await self._handle_appointment_popup()
                    continue  # Continue to the next loop iteration to check for more popups

                elif "Révision des alertes" in title or "RÃ©vision des alertes" in title:
                    logger.info("Handling 'Révision des alertes' popup.")
                    await self._handle_revision_popup()
                    continue  # Continue to check for more

                # If it's a different popup (e.g., multiple cars), break the loop
                # as it represents a final state to be handled by the main logic.
                else:
                    logger.info(
                        f"Detected a final-state popup ('{title}'). Stopping clearing process.")
                    return

            except PlaywrightTimeoutError:
                logger.info(
                    "No popups found within the timeout. Assuming page is clear.")
                return
            except Exception as e:
                logger.warning(f"An error occurred during popup clearing: {e}")
                # Fallback: try to escape
                await self.page.keyboard.press("Escape")

        logger.warning(
            "Reached max attempts for clearing popups. The page may not be stable.")

    def get_single_car_page_url_pattern(self) -> str:
        """Returns the URL pattern for the single car page on SDSweb."""
        return f"{os.getenv('SDS_URL')}t1/appointments-qab/2"

    async def get_cars(self) -> List[Dict]:
        """Main method to get cars. It enhances full car details with service info
        and passes through other results like vehicle lists or statuses."""
        results = await self.action()

        final_results = []
        for car in results:
            if not isinstance(car, dict):
                final_results.append(car)
                continue

            # Only enhance full car objects, which are expected to have a 'maker' key.
            # Pass through status messages, errors, or vehicle lists.
            if "maker" in car and "model" in car:
                self._enhance_car_with_services(car)
                final_results.append(car)
            else:
                final_results.append(car)

        logging.info(final_results)
        return final_results

    def _enhance_car_with_services(self, car: Dict) -> None:
        """Enhanced service mapping for cars."""
        model = car.get("model", "")
        year = car.get("year", "")
        is_hybrid = car.get("is_hybrid", False)
        cylinders = car.get("cylinders", "")

        oil_types = db.get_oil_type(model, year, is_hybrid, cylinders)
        service_array = []
        seen_ids = set()
        # --- Oil Change Codes ---
        for oil, is_suv in oil_types:
            service_info = db.get_service_id(oil, is_suv, cylinders)
            if service_info:
                service_id, processing_time = service_info
                if service_id not in seen_ids:
                    service_array.append({
                        "service_id": service_id,
                        "service_name": "Oil Change",
                        "processing_time": processing_time
                    })
                    seen_ids.add(service_id)
                    break
        if not service_array:
            service_array = [{"service_id": "01T6CLS8FZ",
                              "service_name": "Oil Change", "processing_time": 30}]
        # print(car)
        # --- Service History ---
        next_service = self.get_next_service(car["service_history"])
        # self.services_for_maintence(car["service_history"])
        # print(f"Next service required: {next_service}")
        service_info = db.get_service_id_service_number(
            model=model,
            number_of_cylinders=cylinders,
            year=int(year),
            service_type=int(next_service.split()[1]),
        )
        # print(f"Service info: {service_info}")
        if service_info:
            for service_id in service_info:
                if service_id not in seen_ids:
                    service_array.append({
                        "service_id": service_id[0],
                        "service_name": "Car Regular Maintenance",
                        "processing_time": 60  # adjust per service type
                    })
                    seen_ids.add(service_id)
                    break
        else:
            service_array.append(self.service_defaults[next_service])
        # Final structure
        car["service_id"] = (
            [[s["service_id"], s["service_name"], s["processing_time"]]
                for s in service_array]
        )

        # Clean up temporary fields
        for field in ["cylinders", "is_hybrid", "service_history"]:
            car.pop(field, None)

    async def _wait_with_retry(self, operation, max_attempts: int = 3, delay: float = 0.5):
        """Utility method to retry operations with exponential backoff."""
        for attempt in range(max_attempts):
            try:
                return await operation()
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise e
                await asyncio.sleep(delay * (2 ** attempt))

    async def _dismiss_popup_safely(self, popup_locator: Locator) -> bool:
        """Safely dismiss popup using multiple strategies."""
        dismiss_strategies = [
            lambda: self.page.keyboard.press("Escape"),
            lambda: popup_locator.locator(
                "button[aria-label*='close']").click(timeout=1000),
            lambda: popup_locator.locator(
                ".close, .dismiss, [data-dismiss]").first.click(timeout=1000),
        ]

        for strategy in dismiss_strategies:
            try:
                await strategy()
                await self.page.wait_for_timeout(300)
                if not await popup_locator.is_visible(timeout=500):
                    return True
            except Exception:
                continue
        return False

    async def determine_page_state(self) -> Tuple[str, Optional[Union[Locator, Page]]]:
        """Streamlined state determination with proper single car page detection."""
        await self.page.wait_for_timeout(300)  # Brief wait for page stabilization
        logger.info(f"Determining page state for URL: {self.page.url}")

        # Quick checks for error states first
        state_checks = [
            ("NOT_FOUND", self._check_not_found_fast()),
            ("POPUP", self._check_popup_fast()),
        ]

        for state_name, check_coro in state_checks:
            try:
                result = await check_coro
                if result[0] != f"NO_{state_name}":
                    return result
            except Exception as e:
                logger.warning(f"Error in {state_name} check: {e}")
                continue

        # Now specifically check for single car page using the "Dernier service" indicator
        try:
            single_car_result = await self._check_single_car_page()
            if single_car_result[0] != "NO_SINGLE_CAR":
                return single_car_result
        except Exception as e:
            logger.warning(f"Error checking single car page: {e}")

        # If we get here, we're in an unknown state
        logger.warning(f"Unknown page state. Current URL: {self.page.url}")
        return "UNKNOWN", None

    async def _check_not_found_fast(self) -> Tuple[str, Optional[Locator]]:
        """Fast check for 404/not found states."""
        try:
            not_found_loc = self.page.locator(self.selectors["notFound"])
            if await not_found_loc.is_visible(timeout=self.quick_timeout):
                logger.info("State: NOT_FOUND")
                return "NOT_FOUND", not_found_loc
        except PlaywrightTimeoutError:
            pass
        return "NO_NOT_FOUND", None

    async def _check_popup_fast(self) -> Tuple[str, Optional[Locator]]:
        """Fast popup detection and handling."""
        try:
            popup_title_loc = self.page.locator(self.selectors["popupTitle"])
            if not await popup_title_loc.is_visible(timeout=300):
                return "NO_POPUP", None

            title = (await popup_title_loc.text_content()) or ""
            logger.info(f"Popup detected: {title}")

            # Handle known popup types
            popup_handlers = {
                "Rendez-vous existants": self._handle_appointment_popup,
                "Révision des alertes": self._handle_revision_popup,
                "RÃ©vision des alertes": self._handle_revision_popup,
                "VÃ©hicules": lambda: ("MULTIPLE_CARS_POPUP", self.page.locator(self.selectors["popupCars"])),
                "Véhicules": lambda: ("MULTIPLE_CARS_POPUP", self.page.locator(self.selectors["popupCars"])),
            }

            for popup_type, handler in popup_handlers.items():
                if popup_type in title:
                    logger.info(f"Handling popup type: {popup_type}")
                    # The handler can be an async method or a lambda returning a tuple.
                    # We must handle both cases to avoid a TypeError.
                    result = handler()
                    if asyncio.iscoroutine(result):
                        return await result  # Await the coroutine if it is one
                    else:
                        return result  # Return the tuple directly if it's not

            logger.warning(f"Unknown popup type detected: {title}")
            return "UNKNOWN_POPUP", popup_title_loc

        except PlaywrightTimeoutError:
            return "NO_POPUP", None

    async def _handle_appointment_popup(self) -> Tuple[str, Optional[Locator]]:
        """Handle 'Rendez-vous existants' popup efficiently."""
        try:
            btn = (self.page.locator(self.selectors["popupTitle-add-redenvous"])
                   .locator("..").locator("..").locator(".."))
            await btn.click(timeout=self.quick_timeout)
            await self.page.wait_for_timeout(500)

            # After handling popup, check if we're now on single car page
            logger.info(
                "Popup handled, checking for single car page transition...")
            single_car_result = await self._check_single_car_page()
            if single_car_result[0] != "NO_SINGLE_CAR":
                return single_car_result

            return "POPUP_HANDLED_NO_TRANSITION", None
        except Exception as e:
            logger.warning(f"Failed to handle appointment popup: {e}")
            return "POPUP_HANDLE_FAILED", None

    async def _handle_revision_popup(self) -> Tuple[str, Optional[Locator]]:
        """Handle revision alerts popup."""
        logger.info("Handling revision alerts popup...")
        try:
            # Try to find the revision alert popup using the specific selector
            revision_loc = self.page.locator(
                self.selectors["revisionAlertPopup"])

            # If not found by specific selector, try using the general popup
            if not await revision_loc.is_visible(timeout=1000):
                logger.info(
                    "Revision alert not found by specific selector, using general popup approach")
                revision_loc = self.page.locator(
                    self.selectors["popupTitle"]).locator("..")

            # Try to dismiss the popup
            if await self._dismiss_popup_safely(revision_loc):
                logger.info("Successfully dismissed revision alert popup")

                # After dismissing, wait a bit longer for the page to fully load
                logger.info(
                    "Waiting for page to stabilize after revision alert dismissal...")
                await self.page.wait_for_timeout(2000)

                # Since we successfully dismissed a revision alert and we know we're on the right URL,
                # we should be on the single car page
                current_url = self.page.url
                if current_url.startswith(self.get_single_car_page_url_pattern()):
                    logger.info(
                        "After dismissing revision alert, confirmed on single car page URL")
                    return "ONE_CAR_PAGE", self.page

                # Still check explicitly for the single car page
                single_car_result = await self._check_single_car_page()
                if single_car_result[0] != "NO_SINGLE_CAR":
                    logger.info(
                        "After dismissing revision alert, found single car page")
                    return single_car_result

                return "REVISION_ALERT_HANDLED", None
            else:
                logger.warning("Failed to dismiss revision alert popup")
                return "ONE_CAR_PAGE_WITH_REVISION_ALERT", revision_loc

        except Exception as e:
            logger.error(f"Error handling revision popup: {e}")
            return "REVISION_ALERT_HANDLE_FAILED", None

    async def _check_single_car_page(self) -> Tuple[str, Optional[Page]]:
        """Check if we're on a single car page by looking for 'Dernier service' text."""
        current_url = self.page.url

        # First check if we're on the right URL pattern
        if not current_url.startswith(self.get_single_car_page_url_pattern()):
            logger.info(
                f"URL doesn't match single car pattern. Current: {current_url}")
            return "NO_SINGLE_CAR", None

        logger.info(
            "URL matches single car pattern, checking for 'Dernier service' text...")

        try:
            # Wait for page to be ready after popup dismissal
            await self.page.wait_for_load_state("domcontentloaded", timeout=3000)

            # Try multiple approaches to find the "Dernier service" text
            search_strategies = [
                # Strategy 1: Use the specific selector
                lambda: self.page.locator(self.selectors["one-car-detect"]),
                # Strategy 2: Search for text anywhere on page
                lambda: self.page.locator("text=Dernier service"),
                # Strategy 3: Search for partial text match
                lambda: self.page.locator(":has-text('Dernier')"),
                # Strategy 4: Search in common container elements
                lambda: self.page.locator("div, span, p, h1, h2, h3").filter(
                    has_text="Dernier service"),
            ]

            for i, strategy in enumerate(search_strategies, 1):
                try:
                    logger.info(f"Trying detection strategy {i}/4...")
                    locator = strategy()

                    # Wait for element to be present
                    await locator.first.wait_for(timeout=2000)

                    # Check if it's visible and get text
                    if await locator.first.is_visible(timeout=1000):
                        text_content = await locator.first.text_content()
                        logger.info(
                            f"Strategy {i} found text: '{text_content}'")

                        if text_content and ("Dernier service" in text_content or "Dernier" in text_content):
                            logger.info(
                                f"Successfully detected single car page with strategy {i}")
                            return "ONE_CAR_PAGE", self.page

                except PlaywrightTimeoutError:
                    logger.info(f"Strategy {i} timed out")
                    continue
                except Exception as e:
                    logger.warning(f"Strategy {i} failed: {e}")
                    continue

            # If all strategies failed but we're on the right URL, do a final check
            logger.info(
                "All detection strategies failed, doing final comprehensive check...")

            # Get all text content from the page and check for our target text
            try:
                page_content = await self.page.content()
                if "Dernier service" in page_content or "Dernier" in page_content:
                    logger.info(
                        "Found 'Dernier service' in page content - assuming single car page")
                    return "ONE_CAR_PAGE", self.page
                else:
                    # Log some page content for debugging
                    body_text = await self.page.locator("body").text_content()
                    logger.warning(
                        f"Page content doesn't contain 'Dernier service'. Sample text: {body_text[:200]}...")
            except Exception as e:
                logger.warning(f"Failed to get page content: {e}")

            # Final fallback: if we're on the right URL and successfully dismissed a revision alert,
            # assume we're on the single car page
            logger.info(
                "Using URL pattern as final fallback - assuming single car page")
            return "ONE_CAR_PAGE", self.page

        except Exception as e:
            logger.error(f"Error checking single car page: {e}")

        logger.info("Could not confirm single car page")
        return "NO_SINGLE_CAR", None

    async def extract_single_car_from_page(self) -> List[Dict]:
        """Extract car information with better error handling."""
        try:
            await self.page.wait_for_selector(self.selectors["singleCarInfo"], timeout=self.default_timeout)

            # Get car info elements
            car_elements = await self.page.query_selector_all(self.selectors["singleCarInfo"])
            if len(car_elements) < 6:
                raise ValueError("Insufficient car info elements found")

            car_text = await car_elements[5].text_content()
            if not car_text:
                raise ValueError("No car text found")

            car_parts = car_text.split()
            if len(car_parts) < 2:
                raise ValueError("Invalid car text format")

            maker = car_parts[0]
            year = car_parts[-1]
            model = car_parts[1:-1][0].replace("-", "")

            # Get cylinders info
            cylinders_element = await self.page.query_selector(self.selectors["cylanders"])
            cylinders = (await cylinders_element.text_content()) if cylinders_element else ""

            # Check if hybrid
            hybrid_element = await self.page.query_selector(self.selectors["gas-pump-HV"])
            is_hybrid = hybrid_element is not None

            return [{
                "maker": maker.strip(),
                "model": model.strip(),
                "year": year.strip(),
                "cylinders": cylinders.strip(),
                "is_hybrid": is_hybrid
            }]

        except Exception as e:
            logger.error(f"Error extracting car info: {e}")
            return [{"error": f"Failed to extract car info: {str(e)}"}]

    async def handle_multiple_cars_popup(self, popup_locator: Locator) -> List[Dict]:
        """
        Extracts a list of car names from the multiple cars popup without further browser interaction.
        """
        logger.info(
            "Multiple cars popup detected. Extracting car names directly.")
        results = []
        try:
            # Locate the buttons or elements containing the car descriptions
            car_elements = popup_locator.locator(self.selectors["carButtons"])
            count = await car_elements.count()

            if count == 0:
                logger.warning(
                    "Multiple cars popup was found, but no car elements were inside.")
                return [{"status": "not_found", "message": "Multiple cars popup detected but no cars found"}]

            # Get the text content from all car elements at once
            all_car_texts = await car_elements.all_text_contents()

            # Format the result list
            for car_text in all_car_texts:
                # Clean up the text if necessary (e.g., remove extra whitespace)
                cleaned_text = " ".join(car_text.strip().split())
                if cleaned_text:
                    results.append({"car": cleaned_text})

            logger.info(
                f"Successfully extracted {len(results)} car names from popup.")
            return results

        except Exception as e:
            logger.error(
                f"Error extracting car names from multiple cars popup: {e}")
            return [{"error": f"Failed to extract car names from popup: {str(e)}"}]

    async def get_service_history(self) -> Dict:
        """Get service history with improved error handling."""
        try:
            # Activate service history popup
            service_button = await self.page.query_selector(
                self.selectors["denier-service-popup"]["button-activate"]
            )
            if not service_button:
                return {"error": "Service history button not found"}

            await service_button.click()
            # mini_pupup = await self.page.locator(self.selectors["denier-service-popup"]["no-history"])
            # if mini_pupup:
            #     return []
            await self.page.wait_for_timeout(1000)

            # Check if history popup opened
            title_h2 = self.page.locator(
                self.selectors["denier-service-popup"]["header-title"])
            if not await title_h2.is_visible(timeout=self.default_timeout):
                return {"error": "Service history popup did not open"}

            title = await title_h2.text_content()
            if title != "Historique de service":
                return {"error": f"Unexpected popup title: {title}"}

            return await self._extract_service_history()

        except Exception as e:
            logger.error(f"Error getting service history: {e}")
            return {"error": f"Failed to get service history: {str(e)}"}

    def get_next_service(self, data):
        """Determine the next service based on the history of services done
            Args:
                data (dict): A dictionary with the following structure:
                    {
                        "date": {
                            "services": [
                                "SERVICE 1",
                                "SERVICE 2"
                            ]
                        }
                    }

            Returns:
                str: The next service that should be done
        """
        if not data:
            return "SERVICE 1"
        services_done = []

        # Loop through the data and collect the services that have been done
        for date in data:
            if data[date]['services']:
                service_type = ' '.join(data[date]['services'][0].split()[0:2])
                services_done.append(service_type)
        # Determine the next service based on the history of services done
        if not services_done:
            return "SERVICE 1"
        if "SERVICE 1" in services_done and "SERVICE 2" not in services_done:
            return "SERVICE 2"
        elif "SERVICE 1" in services_done and "SERVICE 2" in services_done:
            return "SERVICE 3"
        elif "SERVICE 2" in services_done or "SERVICE 3" in services_done:
            return "SERVICE 1"
        else:
            return "SERVICE 1"

    async def _extract_service_history(self) -> Dict:
        """Extract service history data efficiently."""
        try:
            main_el = await self.page.query_selector(
                self.selectors["denier-service-popup"]["top-element"]
            )
            if not main_el:
                return {"error": "Service history main element not found"}

            # Get initial service date and kilometers
            time_el = await main_el.query_selector(".MuiTypography-root")
            km_el = await main_el.query_selector(".MuiTypography-root.MuiTypography-subtitle2")

            if not time_el or not km_el:
                return {"error": "Required service history elements not found"}

            current_time = await time_el.text_content()
            current_km = await km_el.text_content()

            result = {current_time: {"services": [], "kilometers": current_km}}

            # Get wrapper elements
            wrapper = await self.page.query_selector(
                self.selectors["denier-service-popup"]["wrapper-els"]
            )
            if not wrapper:
                return result

            wrapper_els = await wrapper.query_selector_all('div[data-known-size]')

            for el in wrapper_els:
                position = await el.evaluate("element => getComputedStyle(element).position")

                if position == 'sticky':
                    # New date section
                    time_el = await el.query_selector(".MuiTypography-root")
                    km_el = await el.query_selector(".MuiTypography-root.MuiTypography-subtitle2")

                    if time_el and km_el:
                        new_time = (await time_el.text_content()).strip()
                        new_km = await km_el.text_content()
                        result[new_time] = {
                            "services": [], "kilometers": new_km}
                        current_time = new_time
                else:
                    # Service entry
                    text = (await el.text_content()).strip()
                    if text and current_time in result:
                        result[current_time]["services"].append(text)

            return result

        except Exception as e:
            logger.error(f"Error extracting service history: {e}")
            return {"error": f"Failed to extract service history: {str(e)}"}

    async def _select_car_from_popup(self, car_name: str) -> None:
        """
        Waits for the 'Véhicules' popup and clicks on the button corresponding to the specified car.
        """
        logger.info(
            f"Waiting for multiple cars popup to select '{car_name}'...")
        try:
            # Wait for the popup itself to be visible by its title.
            popup_title_selector = f'{self.selectors["popupTitle"]}:has-text("Véhicules"), {self.selectors["popupTitle"]}:has-text("VÃ©hicules")'
            await self.page.locator(popup_title_selector).wait_for(state="visible", timeout=self.default_timeout)
            logger.info("Multiple cars popup is visible.")

            # Find the specific car button within the popup that contains the car_name text.
            car_button_locator = self.page.locator(
                self.selectors["carButtons"]).filter(has_text=car_name)

            count = await car_button_locator.count()
            if count == 0:
                logger.error(f"Car '{car_name}' not found in the popup.")
                raise Exception(
                    f"Car '{car_name}' not found in the list of vehicles.")
            if count > 1:
                logger.warning(
                    f"Multiple matches found for '{car_name}'. Clicking the first one.")

            logger.info(f"Found car '{car_name}'. Clicking it.")
            await car_button_locator.first.click(timeout=self.default_timeout)
            # Short wait for the click to process.
            await self.page.wait_for_timeout(500)
            logger.info(f"Successfully clicked on '{car_name}'.")

        except PlaywrightTimeoutError:
            logger.error("Timed out waiting for the multiple cars popup.")
            raise Exception("Failed to find the multiple cars popup.")
        except Exception as e:
            logger.error(
                f"An error occurred while selecting the car from the popup: {e}")
            raise e

    async def scrapper(self, playwright: Playwright) -> List:
        """Main scraping method with separate flows for targeted car search vs. general phone search."""
        results = []
        browser = None

        try:
            # --- Browser launch and initial login steps ---
            chromium = playwright.chromium
            browser = await chromium.launch(headless=False)
            self.page = await browser.new_page()
            await self.page.set_viewport_size({"width": 1920, "height": 1080})

            await self.page.goto(f"{os.getenv('SDS_URL')}login", wait_until="networkidle")
            await self.login()
            await self.click_redenvous()
            await self.chose_aviseurs()

            # Insert phone number, which is common to both flows
            await self.insert_phone_number()

            if self.car:
                # --- TARGETED WORKFLOW: A specific car is provided ---
                logger.info(
                    f"Specific car requested: '{self.car}'. Starting targeted flow.")

                # 1. Select the specified car from the 'Véhicules' popup
                await self._select_car_from_popup(self.car)

                # 2. Handle any intermediate popups that appear after selection but before navigation
                await self._clear_all_intermediate_popups()

                # 3. Check if URL has changed. If not, force navigation by clicking the next step button.
                current_url = self.page.url
                if not current_url.startswith(self.get_single_car_page_url_pattern()):
                    logger.info(
                        "URL has not changed. Clicking 'next-step' to force navigation.")
                    try:
                        await self.page.locator(self.selectors["next-step"]).click(timeout=self.default_timeout)
                        await self.page.wait_for_url(f"{os.getenv('SDS_URL')}t1/appointments-qab/**", timeout=7000)
                        logger.info(
                            f"Navigation successful after click. New URL: {self.page.url}")
                    except PlaywrightTimeoutError:
                        logger.error(
                            "Failed to navigate to the car page after clicking next step.")
                        raise Exception(
                            "Could not navigate to the car details page.")

                # 4. On the new page, clear any final popups (e.g., 'Révision des alertes')
                logger.info("On new page, clearing any final popups.")
                await self._clear_all_intermediate_popups()

                # 5. Extract car details and service history from the final page
                car_results = await self.extract_single_car_from_page()
                results.extend(car_results)

                if results and not any("error" in r for r in results):
                    service_history = await self.get_service_history()
                    if service_history and "error" not in service_history:
                        logger.info(
                            f"Successfully retrieved service history for {self.car}.")
                        for result in results:
                            if isinstance(result, dict):
                                result["service_history"] = service_history
                    else:
                        logger.error("Service history extraction failed.")
                        for result in results:
                            if isinstance(result, dict):
                                result["service_history"] = None
            else:
                # --- STANDARD WORKFLOW: Only a telephone is provided ---
                logger.info(
                    "No specific car requested. Starting standard discovery flow.")

                # 1. Handle immediate popups that appear on the same page
                await self._handle_immediate_popups()

                # 2. Wait for the primary navigation to the car page to complete
                logger.info(
                    "Waiting for page navigation after phone number submission...")
                try:
                    await self.page.wait_for_url(f"{os.getenv('SDS_URL')}t1/appointments-qab/**", timeout=7000)
                    logger.info(
                        f"Navigation successful. New URL: {self.page.url}")
                except PlaywrightTimeoutError:
                    logger.warning(
                        "Page did not navigate as expected. Proceeding with analysis on the current page.")

                # 3. Handle subsequent popups on the new page
                logger.info(
                    "Page may have loaded. Now clearing any remaining intermediate popups...")
                await self._clear_all_intermediate_popups()

                # 4. Determine final page state (e.g., not found, one car, multiple cars)
                logger.info(
                    "Popup clearing complete. Determining final page state.")
                state, element_or_page = await self.determine_page_state()
                logger.info(f"Final determined state: {state}")

                # 5. Handle the determined state
                state_handlers = {
                    "NOT_FOUND": self._handle_not_found_state,
                    "ONE_CAR_PAGE": self._handle_single_car_state,
                    "MULTIPLE_CARS_POPUP": self._handle_multiple_cars_state,
                }
                handler = state_handlers.get(state, self._handle_unknown_state)
                car_results = await handler(element_or_page)
                results.extend(car_results)

                # 6. Get service history if on a single car page with valid results
                if state == "ONE_CAR_PAGE" and results and not any("error" in r for r in results):
                    service_history = await self.get_service_history()
                    if service_history and "error" not in service_history:
                        logger.info(f"Successfully retrieved service history.")
                        for result in results:
                            if isinstance(result, dict):
                                result["service_history"] = service_history
                    else:
                        logger.error("Service history extraction failed.")
                        for result in results:
                            if isinstance(result, dict):
                                result["service_history"] = None

        except Exception as e:
            logger.critical(f"Critical error in scrapper: {e}", exc_info=True)
            results.append({"error": f"Critical scrapper error: {str(e)}"})

        finally:
            if browser:
                await browser.close()
            logger.info(f"Final results for phone {self.telephone}: {results}")

        return results

    # State handler methods
    async def _handle_not_found_state(self, element: ElementHandle) -> List:
        message = "Phone number not found"
        if element:
            try:
                message = await element.text_content(timeout=500) or message
            except Exception:
                pass
        return [{"status": "not_found", "message": message}]

    async def _handle_single_car_state(self, page) -> List:
        return await self.extract_single_car_from_page()

    async def _handle_single_car_with_alert_state(self, alert_locator) -> List:
        if await self._dismiss_popup_safely(alert_locator):
            logger.info("Successfully dismissed revision alert")
        return await self.extract_single_car_from_page()

    async def _handle_multiple_cars_state(self, popup_locator) -> List:
        return await self.handle_multiple_cars_popup(popup_locator)

    async def _handle_unknown_state(self, element) -> List:
        return [{"status": "unknown", "url": self.page.url, "message": "Could not determine page state"}]
