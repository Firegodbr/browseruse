from .scrapper import Scrapper, PageState, StateResult, ElementNotFoundError, NavigationError
import logging
import os
import db.database_ops as db
from playwright.async_api import Playwright, Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv
from typing import List, Dict, Tuple, Optional

load_dotenv(override=True)
logger = logging.getLogger(__name__)


class GetCarScrapper(Scrapper):
    def __init__(self, telephone: str, car: str = None):
        super().__init__(telephone)
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
        cylinders = car.get("cylinders", "")

        service_array = []
        seen_ids = set()

        # --- Service History ---
        next_service = self.get_next_service(car["service_history"])
        service_info = db.get_service_id_service_number(
            model=model,
            number_of_cylinders=cylinders,
            year=int(year),
            service_type=int(next_service.split()[1]),
        )
        
        if service_info:
            for service_id in service_info:
                if service_id not in seen_ids:
                    service_array.append({
                        "service_id": service_id[0],
                        "service_name": "entretien régulier du véhicule",
                        "processing_time": 60
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

    async def determine_page_state(self) -> StateResult:
        """
        Determines the current page state after phone number submission.
        Uses base class state detection with custom checks.
        """
        await self._safe_wait(300)
        logger.info(f"Determining page state for URL: {self.page.url}")

        # Define custom state checks in priority order
        state_checks = {
            PageState.NOT_FOUND: self._check_not_found_state,
            PageState.POPUP_PRESENT: self._check_popup_state,
            PageState.SINGLE_CAR: self._check_single_car_state,
        }

        for state, check_func in state_checks.items():
            try:
                found, data = await check_func()
                if found:
                    logger.info(f"Detected page state: {state.value}")
                    return StateResult(state=state, data=data)
            except Exception as e:
                logger.warning(f"Error checking state {state.value}: {e}")
                continue

        # Unknown state
        logger.warning(f"Unknown page state. Current URL: {self.page.url}")
        return StateResult(
            state=PageState.UNKNOWN,
            data={"url": self.page.url}
        )

    async def _check_not_found_state(self) -> Tuple[bool, Optional[Dict]]:
        """Check for 'not found' error state"""
        try:
            not_found_loc = self.page.locator(self.selectors["notFound"])
            if await not_found_loc.is_visible(timeout=self.timeout.QUICK):
                message = await not_found_loc.text_content() or "Phone number not found"
                logger.info("State: NOT_FOUND")
                return True, {"message": message}
        except PlaywrightTimeoutError:
            pass
        return False, None

    async def _check_popup_state(self) -> Tuple[bool, Optional[Dict]]:
        """Check for popup presence and determine popup type"""
        try:
            popup_title_loc = self.page.locator(self.selectors["popupTitle"])
            if not await popup_title_loc.is_visible(timeout=self.timeout.QUICK):
                return False, None

            title = (await popup_title_loc.text_content() or "").strip()
            logger.info(f"Popup detected: {title}")

            # Check for multiple cars popup
            if "Véhicules" in title or "VÃ©hicules" in title or "VÃƒÂ©hicules" in title:
                return True, {
                    "popup_type": "multiple_cars",
                    "popup_locator": self.page.locator(self.selectors["popupCars"])
                }

            # Check for appointment popup
            if "Rendez-vous existants" in title:
                # Handle it immediately
                await self._handle_appointment_popup()
                # After handling, recheck state
                return False, None

            # Check for revision alert popup
            if "Révision des alertes" in title or "RÃ©vision des alertes" in title or "RÃƒÂ©vision des alertes" in title:
                # Handle it immediately
                await self._handle_revision_popup()
                # After handling, recheck state
                return False, None

            logger.warning(f"Unknown popup type: {title}")
            return True, {"popup_type": "unknown", "title": title}

        except PlaywrightTimeoutError:
            return False, None

    async def _check_single_car_state(self) -> Tuple[bool, Optional[Page]]:
        """Check if we're on a single car page by URL pattern and 'Dernier service' text"""
        current_url = self.page.url

        # First check URL pattern
        if not current_url.startswith(self.get_single_car_page_url_pattern()):
            logger.debug(f"URL doesn't match single car pattern: {current_url}")
            return False, None

        logger.info("URL matches single car pattern, checking for 'Dernier service' text...")

        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=3000)

            # Multiple detection strategies
            search_strategies = [
                lambda: self.page.locator(self.selectors["one-car-detect"]),
                lambda: self.page.locator("text=Dernier service"),
                lambda: self.page.locator(":has-text('Dernier')"),
                lambda: self.page.locator("div, span, p, h1, h2, h3").filter(has_text="Dernier service"),
            ]

            for i, strategy in enumerate(search_strategies, 1):
                try:
                    logger.debug(f"Trying detection strategy {i}/4...")
                    locator = strategy()
                    await locator.first.wait_for(timeout=2000)

                    if await locator.first.is_visible(timeout=self.timeout.QUICK):
                        text_content = await locator.first.text_content()
                        logger.info(f"Strategy {i} found text: '{text_content}'")

                        if text_content and ("Dernier service" in text_content or "Dernier" in text_content):
                            logger.info(f"Successfully detected single car page with strategy {i}")
                            return True, self.page

                except PlaywrightTimeoutError:
                    logger.debug(f"Strategy {i} timed out")
                    continue
                except Exception as e:
                    logger.debug(f"Strategy {i} failed: {e}")
                    continue

            # Fallback: check page content
            page_content = await self.page.content()
            if "Dernier service" in page_content or "Dernier" in page_content:
                logger.info("Found 'Dernier service' in page content - assuming single car page")
                return True, self.page

            logger.info("Could not confirm single car page")
            return False, None

        except Exception as e:
            logger.error(f"Error checking single car page: {e}")
            return False, None

    async def extract_single_car_from_page(self) -> List[Dict]:
        """Extract car information from single car page"""
        try:
            await self.wait_for_selector_safe(
                self.selectors["singleCarInfo"],
                timeout=self.timeout.DEFAULT
            )

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
        Extracts a list of car names from the multiple cars popup.
        """
        logger.info("Multiple cars popup detected. Extracting car names directly.")
        results = []
        
        try:
            car_elements = popup_locator.locator(self.selectors["carButtons"])
            count = await car_elements.count()

            if count == 0:
                logger.warning("Multiple cars popup found, but no car elements inside.")
                return [{"status": "not_found", "message": "Multiple cars popup detected but no cars found"}]

            all_car_texts = await car_elements.all_text_contents()

            for car_text in all_car_texts:
                cleaned_text = " ".join(car_text.strip().split())
                if cleaned_text:
                    results.append({"car": cleaned_text})

            logger.info(f"Successfully extracted {len(results)} car names from popup.")
            return results

        except Exception as e:
            logger.error(f"Error extracting car names from popup: {e}")
            return [{"error": f"Failed to extract car names from popup: {str(e)}"}]

    async def get_service_history(self) -> Dict:
        """Get service history with improved error handling"""
        try:
            # Click service history button
            service_button_selector = self.selectors["denier-service-popup"]["button-activate"]
            if not await self.click_with_retry(service_button_selector):
                return {"error": "Service history button not found"}

            await self._safe_wait(self.timeout.QUICK)

            # Verify popup opened
            title_h2 = self.page.locator(
                self.selectors["denier-service-popup"]["header-title"]
            )
            if not await title_h2.is_visible(timeout=self.timeout.DEFAULT):
                return {"error": "Service history popup did not open"}

            title = await title_h2.text_content()
            if title != "Historique de service":
                return {"error": f"Unexpected popup title: {title}"}

            return await self._extract_service_history()

        except Exception as e:
            logger.error(f"Error getting service history: {e}")
            return {"error": f"Failed to get service history: {str(e)}"}

    def get_next_service(self, data: Dict) -> str:
        """Determine the next service based on service history"""
        if not data:
            return "SERVICE 1"
        
        services_done = []

        for date in data:
            if data[date]['services']:
                service_type = ' '.join(data[date]['services'][0].split()[0:2])
                services_done.append(service_type)
        
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
        """Extract service history data efficiently"""
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
                        result[new_time] = {"services": [], "kilometers": new_km}
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

    async def scrapper(self, playwright: Playwright) -> List:
        """Main scraping method with improved flow"""
        results = []
        browser = None

        try:
            # --- Browser Setup ---
            with self._track_operation("browser_setup"):
                chromium = playwright.chromium
                browser = await chromium.launch(headless=True)
                self.page = await browser.new_page()
                await self.page.set_viewport_size({"width": 1920, "height": 1080})

            # --- Login and Navigation ---
            with self._track_operation("login_and_navigation"):
                await self.page.goto(f"{os.getenv('SDS_URL')}login", wait_until="networkidle")
                await self.login()
                await self.navigate_to_appointments()

            # --- Insert Phone Number ---
            await self.insert_phone_number()

            # --- TARGETED WORKFLOW: Specific car requested ---
            if self.car:
                logger.info(f"Specific car requested: '{self.car}'. Starting targeted flow.")
                
                with self._track_operation("targeted_car_selection"):
                    # Select car from popup
                    await self.select_car_from_popup(self.car)
                    
                    # Clear any intermediate popups
                    await self.clear_intermediate_popups()

                    # Check if URL changed, if not force navigation
                    current_url = self.page.url
                    if not current_url.startswith(self.get_single_car_page_url_pattern()):
                        logger.info("URL has not changed. Clicking 'next-step' to force navigation.")
                        if not await self.click_with_retry(self.selectors["next-step"]):
                            raise NavigationError("Failed to click next-step button")
                        
                        await self.page.wait_for_url(
                            f"{os.getenv('SDS_URL')}t1/appointments-qab/**",
                            timeout=self.timeout.NAVIGATION // 4
                        )
                        logger.info(f"Navigation successful. New URL: {self.page.url}")

                    # Clear final popups on new page
                    await self.clear_intermediate_popups()

                # Extract car details and service history
                with self._track_operation("extract_car_data"):
                    results = await self.extract_single_car_from_page()

                    if results and not any("error" in r for r in results):
                        service_history = await self.get_service_history()
                        if service_history and "error" not in service_history:
                            logger.info(f"Successfully retrieved service history for {self.car}.")
                            for result in results:
                                if isinstance(result, dict):
                                    result["service_history"] = service_history
                        else:
                            logger.warning("Service history extraction failed.")
                            for result in results:
                                if isinstance(result, dict):
                                    result["service_history"] = None

            # --- STANDARD WORKFLOW: Only telephone provided ---
            else:
                logger.info("No specific car requested. Starting standard discovery flow.")

                with self._track_operation("standard_flow"):
                    # Wait for navigation after phone submission
                    try:
                        await self.page.wait_for_url(
                            f"{os.getenv('SDS_URL')}t1/appointments-qab/**",
                            timeout=self.timeout.NAVIGATION // 4
                        )
                        logger.info(f"Navigation successful. New URL: {self.page.url}")
                    except PlaywrightTimeoutError:
                        logger.warning("Page did not navigate as expected.")

                    # Clear intermediate popups
                    popups_cleared = await self.clear_intermediate_popups()
                    logger.info(f"Cleared {popups_cleared} intermediate popups")

                    # Determine page state
                    state_result = await self.determine_page_state()
                    logger.info(f"Final determined state: {state_result.state.value}")

                    # Handle different states
                    if state_result.state == PageState.NOT_FOUND:
                        message = state_result.data.get("message", "Phone number not found")
                        results = [{"status": "not_found", "message": message}]

                    elif state_result.state == PageState.SINGLE_CAR:
                        results = await self.extract_single_car_from_page()
                        
                        # Get service history if extraction successful
                        if results and not any("error" in r for r in results):
                            service_history = await self.get_service_history()
                            if service_history and "error" not in service_history:
                                logger.info("Successfully retrieved service history.")
                                for result in results:
                                    if isinstance(result, dict):
                                        result["service_history"] = service_history
                            else:
                                logger.warning("Service history extraction failed.")
                                for result in results:
                                    if isinstance(result, dict):
                                        result["service_history"] = None

                    elif state_result.state == PageState.POPUP_PRESENT:
                        popup_data = state_result.data
                        if popup_data.get("popup_type") == "multiple_cars":
                            popup_locator = popup_data.get("popup_locator")
                            results = await self.handle_multiple_cars_popup(popup_locator)
                        else:
                            results = [{"error": f"Unexpected popup: {popup_data.get('title', 'unknown')}"}]

                    else:  # UNKNOWN or ERROR
                        results = [{"status": "unknown", "url": self.page.url, "message": "Could not determine page state"}]

        except Exception as e:
            logger.critical(f"Critical error in scrapper: {e}", exc_info=True)
            results.append({"error": f"Critical scrapper error: {str(e)}"})

        finally:
            if browser:
                await browser.close()
            logger.info(f"Final results for phone {self.telephone}: {results}")

        return results