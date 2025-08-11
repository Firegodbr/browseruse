from .scrapper import Scrapper
import logging
import os
import db.database_ops as db
from playwright.async_api import Playwright, Locator
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv
load_dotenv(override=True)

logger = logging.getLogger(__name__)


class GetCarScrapper(Scrapper):
    def __init__(self, telephone: str):
        super().__init__(telephone)

    def get_single_car_page_url_pattern(self) -> str:
        return f"{os.getenv('SDS_URL')}t1/appointments-qab/2"

    async def get_cars(self):
        results = await self.action()

        for car in results:
            if not isinstance(car, dict):
                continue  # Skip non-dict items

            model = car["model"]
            year = car["year"]
            is_hybrid = car["is_hybrid"]
            cylinders = car["cylinders"]
            oil_types = db.get_oil_type(model, year, is_hybrid, cylinders)
            service_array = []
            seen_ids = set()

            for oil, is_suv in oil_types:
                service_info = db.get_service_id(oil, is_suv, cylinders)
                if service_info:
                    service_id, processing_time = service_info
                    if service_id not in seen_ids:
                        service_array.append({
                            "service_id": service_id,
                            "processing_time": processing_time
                        })
                        seen_ids.add(service_id)
        
            if service_array:
                car["service_id"] = [[sid["service_id"], "Oil change", sid["processing_time"]] for sid in service_array]
            else:
                car["service_id"] = ['01T6CLS8FZ']

            # Remove unneeded fields
            car.pop("cylinders", None)
            car.pop("is_hybrid", None)
        return results


    async def determine_post_phone_entry_state(self, timeout_ms: int = 10000):
        """
        Determine the page state after phone entry.

        This function checks for various immediate overlay/error states and navigations to determine the page state.
        It returns a tuple containing a string describing the state and a Locator relevant to the state.

        States:
        - NOT_FOUND: Page not found error on the page.
        - MULTI_ACCOUNT_POPUP: A popup indicating multiple accounts found.
        - MULTIPLE_CARS_POPUP: A popup indicating multiple cars found.
        - ONE_CAR_PAGE_WITH_REVISION_ALERT: On a single car page with a revision alert visible.
        - ONE_CAR_PAGE_BY_URL: On a single car page URL (without revision alert visible).
        - CLICK_FAILED: Failed to click a button to resolve an overlay/error.
        - UNKNOWN: Exhausted all checks, current URL: {page.url}.

        :param page: The Playwright Page object.
        :param selectors_dict: A dictionary of selectors.
        :param timeout_ms: The timeout in milliseconds (default: 10000).

        :return: A tuple of (state, locator) where state is a string describing the state and locator is a Locator relevant to the state.
        """
        await self.page.wait_for_timeout(500)  # Brief pause
        logger.info("Determining page state...")
        # 1. Check for immediate, high-priority overlay/error states
        state, loc = await self.check_not_found()
        if state == "NOT_FOUND":
            return state, loc

        state, loc = await self.check_popup()
        if state != "NO_POPUP":
            return state, loc

        logger.info(
            "DEBUG: State Car not determined. Proceeding to check for immediate, low-priority overlay/error states...")
        # 2. Check for immediate, low-priority overlay/error states
        navigated_to_single_car_url = False
        current_url = self.page.url
        if current_url.startswith(self.get_single_car_page_url_pattern()):
            logger.info(
                f"DEBUG: Already on a single car page URL pattern: {current_url}")
            navigated_to_single_car_url = True
        else:
            try:
                # Wait for navigation to the single car page URL.
                # The main `wait_for_load_state("networkidle")` should have handled most of this.
                # This timeout is an additional safeguard or for client-side routing.
                # Ensure a minimum reasonable timeout
                wait_for_url_timeout = max(3000, timeout_ms * 0.5)
                logger.warning(
                    f"DEBUG: Current URL '{current_url}' does not match. Waiting up to {wait_for_url_timeout/1000}s for navigation to '{self.get_single_car_page_url_pattern()}...'.")
                await self.page.wait_for_url(lambda url: url.startswith(self.get_single_car_page_url_pattern()), timeout=wait_for_url_timeout)
                logger.info(
                    f"DEBUG: Successfully navigated to URL: {self.page.url}")
                navigated_to_single_car_url = True
            except PlaywrightTimeoutError:
                logger.error(
                    f"DEBUG: Timeout waiting for URL to change to '{self.get_single_car_page_url_pattern()}...'. Current URL: {self.page.url}")
                navigated_to_single_car_url = False

        if navigated_to_single_car_url:
            # On the single car page URL. Check for the revision alert.
            try:
                revision_alert_loc = self.page.locator(
                    self.selectors["revisionAlertPopup"])
                # Check for alert on the single car page
                if await revision_alert_loc.is_visible(timeout=2000):
                    logger.info(
                        "DEBUG: State determined: ONE_CAR_PAGE_WITH_REVISION_ALERT (URL matched, alert visible)")
                    return "ONE_CAR_PAGE_WITH_REVISION_ALERT", revision_alert_loc
                else:  # Alert not visible on the single car page
                    logger.info(
                        "DEBUG: State determined: ONE_CAR_PAGE_BY_URL (URL matched, no alert)")
                    return "ONE_CAR_PAGE_BY_URL", self.page
            # Alert not visible (timeout on is_visible)
            except PlaywrightTimeoutError:
                logger.info(
                    "DEBUG: State determined: ONE_CAR_PAGE_BY_URL (URL matched, no alert - alert check timed out)")
                return "ONE_CAR_PAGE_BY_URL", self.page

        # 3. If URL did not match single car page pattern, and no other popups found:
        #    Check for `revisionAlertPopup` on the current (unknown) page.
        #    This implies an alert appeared without navigating to the expected single car URL.
        try:
            revision_alert_loc = self.page.locator(
                self.selectors["revisionAlertPopup"])
            if await revision_alert_loc.is_visible(timeout=1000):
                logger.info(
                    "WARNING: Revision alert popup visible, but NOT on the expected single car page URL.")
                # This could be a general site alert or an unexpected state.
                # Handling it as ONE_CAR_PAGE_WITH_REVISION_ALERT might be okay if the dismissal logic is generic.
                return "ONE_CAR_PAGE_WITH_REVISION_ALERT", revision_alert_loc
        except PlaywrightTimeoutError:
            pass

        logger.info(
            f"DEBUG: State determined: UNKNOWN (Exhausted all checks. Current URL: {self.page.url})")
        return "UNKNOWN", None

    # --- Placeholder functions for actions within states (Updated handle_revision_alert) ---
    async def handle_revision_alert_and_extract_car(self, alert_locator):
        logger.info("Revision alert popup detected.")
        await self.page.keyboard.press("Escape")
        logger.info("Pressed 'Escape' key to dismiss revision alert.")
        await self.page.wait_for_timeout(750)

        try:
            if await alert_locator.is_visible(timeout=1000):
                logger.warning(
                    "Revision alert still visible after pressing Escape.")
            else:
                logger.info(
                    "Revision alert is no longer visible after pressing Escape.")
        except PlaywrightTimeoutError:
            logger.info(
                "Revision alert successfully closed by Escape key (not visible).")
        except Exception as e_check:
            logger.warning(
                f"Error while checking revision alert visibility after Escape: {e_check}")

        logger.info(
            "Proceeding to extract single car details from the page (implementation needed).")
        return ["Single Car (details extraction TBD after attempting to close alert)"]

    async def extract_single_car_from_page(self):
        # logger.info(f"Attempting to extract single car details from page: {page.url} (implementation needed).")
        await self.page.wait_for_selector(self.selectors["singleCarInfo"])
        car = await (await self.page.query_selector_all(self.selectors["singleCarInfo"]))[5].text_content()
        maker, model, year = car.split(" ")
        cylanders = await (await self.page.query_selector(self.selectors["cylanders"])).text_content()
        hybrid = await self.page.query_selector(self.selectors["gas-pump-HV"])
        return [{"maker": maker.strip(), "model": model.strip(), "year": year.strip(), "cylinders": cylanders.strip(), "is_hybrid": True if hybrid is not None else False}]

    async def handle_multi_single_car(self, index: int = 0):
        await self.insert_phone_number()
        await self.page.wait_for_timeout(250)
        await self.page.locator(self.selectors["carButtons"]).nth(index).click()
        await self.page.wait_for_timeout(1000)
        loc = self.page.locator(self.selectors["popupTitle"])
        count = await loc.count()
        if count > 0:
            await self.redez_vous_existances()
            return await self.extract_single_car_from_page()
        else:
            return await self.extract_single_car_from_page()

    async def handle_multi_cars_popup(self, element_or_page: Locator):
        results = []
        popup_cars_locator = element_or_page.locator(
            self.selectors["carButtons"])
        count = await popup_cars_locator.count()

        if count == 0:
            results.append(
                "Multiple Cars Popup detected, but no car data extracted.")
        else:
            await self.page.keyboard.press("Escape")
            for i in range(count):
                results.extend(await self.handle_multi_single_car(i))
                await self.page.locator(self.selectors["previous-step"]).click()

        return results

    async def handle_multi_cars_accounts_popup(self):
        await self.page.wait_for_timeout(500)
        results = []
        popup_cars_locator = self.page.locator(self.selectors["carsContainer"])
        # logger.info(await popup_cars_locator.count())
        car_button_elements = await popup_cars_locator.locator(self.selectors["carButtons"]).all()
        if not car_button_elements:
            results.append(
                "Multiple Cars Popup detected, but no car data extracted.")
        else:
            for i, el_handle in enumerate(car_button_elements):
                try:
                    text = await el_handle.text_content(timeout=500)
                    if text:
                        results.append(text.strip())
                    else:
                        results.append(f"Car Entry {i+1} (no text)")
                except Exception as e_extract:
                    results.append(f"Car Entry {i+1} (error: {e_extract})")
        return results

    async def handle_multi_account_popup(self):
        results = []
        car_button_elements = await self.page.locator(self.selectors["clientButtonsContainerElements"]).all()
        if not car_button_elements:
            results.append(
                "Multiple Cars Popup detected, but no car data extracted.")
        else:
            for i, el_handle in enumerate(car_button_elements):
                try:
                    # Finding a lot of different elements in the same container that's not there
                    if await el_handle.locator(self.selectors["clientsMultipleCarsSvg"]).is_visible():
                        text = await el_handle.locator(self.selectors["clientName"]).text_content()
                        if text:
                            await el_handle.locator(self.selectors["clientName"]).click()
                            client = {"client": text.strip(), "cars": await self.handle_multi_cars_accounts_popup()}
                            await self.page.keyboard.press("Escape")
                            results.append(client)
                        # else: results.append(f"Car Entry {i+1} (no text)")
                except Exception as e_extract:
                    results.append(f"Car Entry {i+1} (error: {e_extract})")
        logger.info(
            "Multi-account page/section detected (implementation needed).")
        # return ["Multi-Account Page Detected (further action TBD)"]
        return results

    async def check_not_found(self):
        """Check if not found is on the page

        Args:
            page (Page): Playwright page
            timeout_ms (int, optional): Time to wait for not found to appear. Defaults to 10000.

        Returns:
            tuple: (str, Locator)
        """
        await self.page.wait_for_timeout(500)  # Brief pause
        # 1. Check for immediate, high-priority overlay/error states
        try:
            not_found_loc = self.page.locator(self.selectors["notFound"])
            if await not_found_loc.is_visible(timeout=1000):
                logger.info("DEBUG: State determined: NOT_FOUND")
                return "NOT_FOUND", not_found_loc
        except PlaywrightTimeoutError:
            pass
        return "NO_NOT_FOUND", None

    async def redez_vous_existances(self) -> None:
        await self.page.wait_for_timeout(150)  # Brief pause
        # 1. Check for immediate, high-priority overlay/error states
        try:
            btn = self.page.locator(
                self.selectors["popupTitle-add-redenvous"]).locator("..").locator("..").locator("..")
            await btn.click(timeout=1000)
            logger.info(
                "DEBUG: Clicked to resolve 'Rendez-vous existants' popup")
            await self.page.wait_for_timeout(150)

        except PlaywrightTimeoutError:
            pass

    async def check_popup(self,  max_attempts: int = 3):
        """Check existence of popup and handle cases like 'Rendez-vous existants'

        Args:
            page (Page): Playwright page
            max_attempts (int): Number of times to re-check title after interaction

        Returns:
            tuple: (str, Locator)
        """
        for attempt in range(max_attempts):
            await self.page.wait_for_timeout(100)
            try:
                loc = self.page.locator(self.selectors["popupTitle"])

                # Wait for visibility quickly; skip long timeouts
                if not await loc.is_visible(timeout=300):
                    return "NO_POPUP", None

                # Now get the title
                title = (await loc.text_content()) or ""
                logger.info(
                    f"DEBUG: Popup title (attempt {attempt + 1}): {title}")

                if "Rendez-vous existants" in title:
                    try:
                        # Click to resolve the popup
                        await self.redez_vous_existances()

                        # Wait briefly before checking again
                        continue  # Loop to re-check the popup title
                    except Exception as e:
                        logger.info(
                            f"ERROR: Failed to click popup button: {e}")
                        return "CLICK_FAILED", None

                elif "Véhicules" in title:
                    return "MULTIPLE_CARS_POPUP", self.page.locator(self.selectors["popupCars"])

                elif "Clients" in title:
                    return "MULTI_ACCOUNT_POPUP", self.page.locator(self.selectors["popupCars"])

                else:
                    logger.info("DEBUG: Unrecognized popup title")
                    return "UNKNOWN_POPUP", loc

            except PlaywrightTimeoutError:
                logger.info("DEBUG: No popup visible")
                return "NO_POPUP", None

        # If we looped without breaking, we couldn't resolve popup
        logger.warning("Max attempts reached in check_popup")
        return "NO_POPUP", None

    async def scrapper(self, playwright: Playwright) -> dict:
        results = []

        chromium = playwright.chromium
        # Set to True for production
        browser = await chromium.launch(headless=True)
        self.page = await browser.new_page()

        try:
            await self.page.goto(f"{os.getenv('SDS_URL')}login", wait_until="networkidle")

            await self.login()

            await self.click_redenvous()

            await self.chose_aviseurs()

            await self.insert_phone_number()

            # Waiting a moment to event to take effect
            await self.page.wait_for_timeout(500)
            # IMPORTANT: Wait for page to potentially navigate/load after "Enter"
            try:
                logger.info(
                    "Waiting for page to stabilize after phone entry (networkidle)...")
                await self.page.wait_for_load_state("networkidle", timeout=7000)
                logger.info(f"Page stabilized. Current URL: {self.page.url}")
            except PlaywrightTimeoutError:
                logger.info(
                    f"Network idle timeout after phone entry. Current URL: {self.page.url}. Proceeding with element checks.")
            except Exception as e:
                logger.info(
                    f"ERROR: during wait_for_load_state: {e}. Current URL: {self.page.url}. Proceeding...")
            state, element_or_page = await self.determine_post_phone_entry_state()
            logger.info(f"Determined state after phone entry: {state}")
            match state:
                case "NOT_FOUND":
                    not_found_message = "Not found message text TBD"
                    if element_or_page:
                        try:
                            not_found_message = await element_or_page.text_content(timeout=500)
                        except Exception as e_text:
                            logger.info(
                                f"WARNING: Could not get text from not_found_loc: {e_text}")
                    results.append(
                        f"Status: Not Found. Message: {not_found_message}")

                case "MULTIPLE_CARS_POPUP":
                    logger.info("Processing multiple cars from popup...")
                    results.extend(await self.handle_multi_cars_popup(element_or_page))

                case "ONE_CAR_PAGE_WITH_REVISION_ALERT":
                    cars_from_page = await self.handle_revision_alert_and_extract_car(element_or_page)
                    results.extend(cars_from_page)

                case "ONE_CAR_PAGE_BY_URL":
                    # `element_or_page` is the page object for BY_URL, or the specific locator for BY_SELECTOR
                    cars_from_page = await self.extract_single_car_from_page()
                    results.extend(cars_from_page)

                case "MULTI_ACCOUNT_POPUP":
                    # ... (same as before)
                    account_info = await self.handle_multi_account_popup(element_or_page)
                    results.extend(account_info)

                case "UNKNOWN":  # Combined all other non-specific outcomes here
                    results.append(
                        f"Status: {state}. No definitive state found. Page URL: {self.page.url}")
                    # screenshot_path = f"debug_screenshot_{state}_{time.strftime('%Y%m%d_%H%M%S')}.png"
                    # await page.screenshot(path=screenshot_path)
                    # logger.info(f"Screenshot saved to {screenshot_path}")
                case _:  # Should ideally not be reached
                    results.append(
                        f"Status: Unhandled state '{state}'. Page URL: {self.page.url}")

        except PlaywrightTimeoutError as e_timeout:
            logger.info(
                f"CRITICAL_ERROR: Playwright Timeout Error during automation: {e_timeout}")
            results.append(
                f"Error: Timeout occurred - {str(e_timeout).splitlines()[0]}")
        except Exception as e_unexpected:
            logger.info(
                f"CRITICAL_ERROR: An unexpected error occurred: {e_unexpected}")
            results.append(
                f"Error: An unexpected error occurred - {str(e_unexpected)}")
        finally:
            await browser.close()
            logger.info(f"Final Results for phone {self.telephone}: {results}")
            return results
