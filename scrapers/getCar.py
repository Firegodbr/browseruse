import os, logging
import time
from playwright.async_api import async_playwright, Playwright, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from .const import selectors, login, insert_phone_number, chose_aviseurs, click_redenvous
logger = logging.getLogger(__name__)
# --- Target URL pattern for a single car page ---
SINGLE_CAR_PAGE_URL_PATTERN = "https://toyosteu.sdswebapp.com:6819/SDSWeb/t1/appointments-qab/2"

# --- Placeholder functions for actions within states (Updated handle_revision_alert) ---
async def handle_revision_alert_and_extract_car(page: Page, alert_locator):
    logger.info("Revision alert popup detected.")
    await page.keyboard.press("Escape")
    logger.info("Pressed 'Escape' key to dismiss revision alert.")
    await page.wait_for_timeout(750)

    try:
        if await alert_locator.is_visible(timeout=1000):
            logger.info("WARNING: Revision alert still visible after pressing Escape.")
        else:
            logger.info("Revision alert is no longer visible after pressing Escape.")
    except PlaywrightTimeoutError:
        logger.info("Revision alert successfully closed by Escape key (not visible).")
    except Exception as e_check:
        logger.info(f"WARNING: Error while checking revision alert visibility after Escape: {e_check}")

    logger.info("Proceeding to extract single car details from the page (implementation needed).")
    return ["Single Car (details extraction TBD after attempting to close alert)"]

async def extract_single_car_from_page(page: Page, selectors_dict: dict):
    # logger.info(f"Attempting to extract single car details from page: {page.url} (implementation needed).")
    await page.wait_for_selector(selectors_dict["singleCarInfo"])
    car = await (await page.query_selector_all(selectors_dict["singleCarInfo"]))[5].text_content()
    return [car.strip()]

async def handle_multi_cars_popup(page: Page, element_or_page):
    results = []
    popup_cars_locator = element_or_page
    car_button_elements = await popup_cars_locator.locator(selectors["carButtons"]).all()
    if not car_button_elements:
        results.append("Multiple Cars Popup detected, but no car data extracted.")
    else:
        for i, el_handle in enumerate(car_button_elements):
            try:
                text = await el_handle.text_content(timeout=500)
                if text: results.append(text.strip())
                else: results.append(f"Car Entry {i+1} (no text)")
            except Exception as e_extract: results.append(f"Car Entry {i+1} (error: {e_extract})")
    return results
async def handle_multi_cars_accounts_popup(page: Page, element_or_page):
    await page.wait_for_timeout(500)
    results = []
    popup_cars_locator = page.locator(selectors["carsContainer"])
    # logger.info(await popup_cars_locator.count())
    car_button_elements = await popup_cars_locator.locator(selectors["carButtons"]).all()
    if not car_button_elements:
        results.append("Multiple Cars Popup detected, but no car data extracted.")
    else:
        for i, el_handle in enumerate(car_button_elements):
            try:
                text = await el_handle.text_content(timeout=500)
                if text: results.append(text.strip())
                else: results.append(f"Car Entry {i+1} (no text)")
            except Exception as e_extract: results.append(f"Car Entry {i+1} (error: {e_extract})")
    return results
async def handle_multi_account_popup(page: Page, multi_account_locator):
    results = []
    car_button_elements = await page.locator(selectors["clientButtonsContainerElements"]).all()
    if not car_button_elements:
        results.append("Multiple Cars Popup detected, but no car data extracted.")
    else:
        for i, el_handle in enumerate(car_button_elements):
            try:
                # Finding a lot of different elements in the same container that's not there
                if await el_handle.locator(selectors["clientsMultipleCarsSvg"]).is_visible():
                    text = await el_handle.locator(selectors["clientName"]).text_content()
                    if text: 
                        await el_handle.locator(selectors["clientName"]).click()
                        client = {"client":text.strip(), "cars": await handle_multi_cars_accounts_popup(page, None, selectors)}
                        await page.keyboard.press("Escape")
                        results.append(client)
                    # else: results.append(f"Car Entry {i+1} (no text)")
            except Exception as e_extract: results.append(f"Car Entry {i+1} (error: {e_extract})")
    logger.info("Multi-account page/section detected (implementation needed).")
    # return ["Multi-Account Page Detected (further action TBD)"]
    return results

async def check_not_found(page: Page):
    """Check if not found is on the page

    Args:
        page (Page): Playwright page
        timeout_ms (int, optional): Time to wait for not found to appear. Defaults to 10000.

    Returns:
        tuple: (str, Locator)
    """
    await page.wait_for_timeout(500) # Brief pause
    # 1. Check for immediate, high-priority overlay/error states
    try:
        not_found_loc = page.locator(selectors["notFound"])
        if await not_found_loc.is_visible(timeout=1000):
            logger.info("DEBUG: State determined: NOT_FOUND")
            return "NOT_FOUND", not_found_loc
    except PlaywrightTimeoutError: pass
    return "NO_NOT_FOUND", None

async def check_popup(page: Page, max_attempts: int = 3):
    """Check existence of popup and handle cases like 'Rendez-vous existants'

    Args:
        page (Page): Playwright page
        max_attempts (int): Number of times to re-check title after interaction

    Returns:
        tuple: (str, Locator)
    """
    for attempt in range(max_attempts):
        try:
            loc = page.locator(selectors["popupTitle"])

            # Wait for visibility quickly; skip long timeouts
            if not await loc.is_visible(timeout=300):
                return "NO_POPUP", None

            # Now get the title
            title = (await loc.text_content()) or ""
            logger.info(f"DEBUG: Popup title (attempt {attempt + 1}): {title}")

            if "Rendez-vous existants" in title:
                try:
                    # Click to resolve the popup
                    btn = page.locator(selectors["popupTitle-add-redenvous"]).locator("..").locator("..").locator("..")
                    await btn.click(timeout=1000)
                    logger.info("DEBUG: Clicked to resolve 'Rendez-vous existants' popup")

                    # Wait briefly before checking again
                    await page.wait_for_timeout(300)
                    continue  # Loop to re-check the popup title
                except Exception as e:
                    logger.info(f"ERROR: Failed to click popup button: {e}")
                    return "CLICK_FAILED", None

            elif "Véhicules" in title:
                return "MULTIPLE_CARS_POPUP", page.locator(selectors["popupCars"])

            elif "Clients" in title:
                return "MULTI_ACCOUNT_POPUP", page.locator(selectors["popupCars"])

            else:
                logger.info("DEBUG: Unrecognized popup title")
                return "UNKNOWN_POPUP", loc

        except PlaywrightTimeoutError:
            logger.info("DEBUG: No popup visible")
            return "NO_POPUP", None

    # If we looped without breaking, we couldn't resolve popup
    logger.info("WARNING: Max attempts reached in check_popup")
    return "NO_POPUP", None


# --- Updated Function to determine page state ---
async def determine_post_phone_entry_state(page: Page, timeout_ms: int = 10000):
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
    await page.wait_for_timeout(500) # Brief pause
    logger.info("Determining page state...")
    # 1. Check for immediate, high-priority overlay/error states
    state, loc = await check_not_found(page)
    if state == "NOT_FOUND": return state, loc
    
    state, loc =await check_popup(page)
    if state != "NO_POPUP": return state, loc
    
    logger.info("DEBUG: State Car not determined. Proceeding to check for immediate, low-priority overlay/error states...")
    # 2. Check for immediate, low-priority overlay/error states
    navigated_to_single_car_url = False
    current_url = page.url
    
    if current_url.startswith(SINGLE_CAR_PAGE_URL_PATTERN):
        logger.info(f"DEBUG: Already on a single car page URL pattern: {current_url}")
        navigated_to_single_car_url = True
    else:
        try:
            # Wait for navigation to the single car page URL.
            # The main `wait_for_load_state("networkidle")` should have handled most of this.
            # This timeout is an additional safeguard or for client-side routing.
            wait_for_url_timeout = max(3000, timeout_ms * 0.5) # Ensure a minimum reasonable timeout
            logger.info(f"DEBUG: Current URL '{current_url}' does not match. Waiting up to {wait_for_url_timeout/1000}s for navigation to '{SINGLE_CAR_PAGE_URL_PATTERN}...'.")
            await page.wait_for_url(lambda url: url.startswith(SINGLE_CAR_PAGE_URL_PATTERN), timeout=wait_for_url_timeout)
            logger.info(f"DEBUG: Successfully navigated to URL: {page.url}")
            navigated_to_single_car_url = True
        except PlaywrightTimeoutError:
            logger.info(f"DEBUG: Timeout waiting for URL to change to '{SINGLE_CAR_PAGE_URL_PATTERN}...'. Current URL: {page.url}")
            navigated_to_single_car_url = False

    if navigated_to_single_car_url:
        # On the single car page URL. Check for the revision alert.
        try:
            revision_alert_loc = page.locator(selectors["revisionAlertPopup"])
            if await revision_alert_loc.is_visible(timeout=2000): # Check for alert on the single car page
                logger.info("DEBUG: State determined: ONE_CAR_PAGE_WITH_REVISION_ALERT (URL matched, alert visible)")
                return "ONE_CAR_PAGE_WITH_REVISION_ALERT", revision_alert_loc
            else: # Alert not visible on the single car page
                logger.info("DEBUG: State determined: ONE_CAR_PAGE_BY_URL (URL matched, no alert)")
                return "ONE_CAR_PAGE_BY_URL", page
        except PlaywrightTimeoutError: # Alert not visible (timeout on is_visible)
            logger.info("DEBUG: State determined: ONE_CAR_PAGE_BY_URL (URL matched, no alert - alert check timed out)")
            return "ONE_CAR_PAGE_BY_URL", page
        
    # 3. If URL did not match single car page pattern, and no other popups found:
    #    Check for `revisionAlertPopup` on the current (unknown) page.
    #    This implies an alert appeared without navigating to the expected single car URL.
    try:
        revision_alert_loc = page.locator(selectors["revisionAlertPopup"])
        if await revision_alert_loc.is_visible(timeout=1000):
            logger.info("WARNING: Revision alert popup visible, but NOT on the expected single car page URL.")
            # This could be a general site alert or an unexpected state.
            # Handling it as ONE_CAR_PAGE_WITH_REVISION_ALERT might be okay if the dismissal logic is generic.
            return "ONE_CAR_PAGE_WITH_REVISION_ALERT", revision_alert_loc
    except PlaywrightTimeoutError:
        pass

    logger.info(f"DEBUG: State determined: UNKNOWN (Exhausted all checks. Current URL: {page.url})")
    return "UNKNOWN", None


# --- Main function to get car information (adjust state handling) ---
async def get_cars_with_state_logic(playwright: Playwright, telephone_number: int):
    start_time = time.time()
    results = []

    chromium = playwright.chromium
    browser = await chromium.launch(headless=False) # Set to True for production
    page = await browser.new_page()

    try:
        await page.goto("https://toyosteu.sdswebapp.com:6819/SDSWeb/login", wait_until="networkidle")
        
        username = os.getenv('USERNAME_SDS')
        password = os.getenv('PASSWORD_SDS')
        if not username or not password:
            logger.warning("WARNING: USERNAME_SDS or PASSWORD_SDS environment variables not set.")
        await login(page, username, password)
        
        await click_redenvous(page)

        await chose_aviseurs(page)
        
        await insert_phone_number(page, telephone_number)
        
        # Waiting a moment to event to take effect
        await page.wait_for_timeout(500)
        # IMPORTANT: Wait for page to potentially navigate/load after "Enter"
        try:
            logger.info("Waiting for page to stabilize after phone entry (networkidle)...")
            await page.wait_for_load_state("networkidle", timeout=7000)
            logger.info(f"Page stabilized. Current URL: {page.url}")
        except PlaywrightTimeoutError:
            logger.info(f"Network idle timeout after phone entry. Current URL: {page.url}. Proceeding with element checks.")
        except Exception as e:
            logger.info(f"ERROR: during wait_for_load_state: {e}. Current URL: {page.url}. Proceeding...")
        state, element_or_page = await determine_post_phone_entry_state(page, selectors)
        logger.info(f"Determined state after phone entry: {state}")
        match state:
            case "NOT_FOUND":
                not_found_message = "Not found message text TBD"
                if element_or_page:
                    try:
                        not_found_message = await element_or_page.text_content(timeout=500)
                    except Exception as e_text:
                        logger.info(f"WARNING: Could not get text from not_found_loc: {e_text}")
                results.append(f"Status: Not Found. Message: {not_found_message}")

            case "MULTIPLE_CARS_POPUP":
                logger.info("Processing multiple cars from popup...")
                results.extend(await handle_multi_cars_popup(page, element_or_page, selectors))


            case "ONE_CAR_PAGE_WITH_REVISION_ALERT":
                cars_from_page = await handle_revision_alert_and_extract_car(page, element_or_page, selectors)
                results.extend(cars_from_page)

            case "ONE_CAR_PAGE_BY_URL":
                # `element_or_page` is the page object for BY_URL, or the specific locator for BY_SELECTOR
                cars_from_page = await extract_single_car_from_page(page, selectors)
                results.extend(cars_from_page)

            case "MULTI_ACCOUNT_POPUP":
                # ... (same as before)
                account_info = await handle_multi_account_popup(page, element_or_page, selectors)
                results.extend(account_info)
            
            case "UNKNOWN": # Combined all other non-specific outcomes here
                results.append(f"Status: {state}. No definitive state found. Page URL: {page.url}")
                # screenshot_path = f"debug_screenshot_{state}_{time.strftime('%Y%m%d_%H%M%S')}.png"
                # await page.screenshot(path=screenshot_path)
                # logger.info(f"Screenshot saved to {screenshot_path}")
            case _: # Should ideally not be reached
                results.append(f"Status: Unhandled state '{state}'. Page URL: {page.url}")

    except PlaywrightTimeoutError as e_timeout:
        logger.info(f"CRITICAL_ERROR: Playwright Timeout Error during automation: {e_timeout}")
        results.append(f"Error: Timeout occurred - {str(e_timeout).splitlines()[0]}")
    except Exception as e_unexpected:
        logger.info(f"CRITICAL_ERROR: An unexpected error occurred: {e_unexpected}")
        results.append(f"Error: An unexpected error occurred - {str(e_unexpected)}")
    finally:
        await browser.close()
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"Total execution time: {execution_time:.2f} seconds")
        logger.info(f"Final Results for phone {telephone_number}: {results}")
        return results

# --- Main execution block ---
async def get_cars(phone_from_user):
    # phone_from_user = 4509745747 # Multi account
    # phone_from_user = 5142944458 # Single car
    # phone_from_user = 5145856444 # Multi cars
    # phone_from_user = 5145856444 # Not found

    logger.info(f"\n--- Checking cars with number: {phone_from_user} ---")
    result = None
    async with async_playwright() as playwright:
        result = await get_cars_with_state_logic(playwright, phone_from_user)
        # You can add further processing for returned_data here
    return result