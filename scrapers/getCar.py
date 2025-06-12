import asyncio
import os
import time
from playwright.async_api import async_playwright, Playwright, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .const import selectors

# --- Target URL pattern for a single car page ---
SINGLE_CAR_PAGE_URL_PATTERN = "https://toyosteu.sdswebapp.com:6819/SDSWeb/t1/appointments-qab/2"

# --- Placeholder functions for actions within states (Updated handle_revision_alert) ---
async def handle_revision_alert_and_extract_car(page: Page, alert_locator, selectors_dict: dict):
    print("INFO: Revision alert popup detected.")
    await page.keyboard.press("Escape")
    print("INFO: Pressed 'Escape' key to dismiss revision alert.")
    await page.wait_for_timeout(750)

    try:
        if await alert_locator.is_visible(timeout=1000):
            print("WARNING: Revision alert still visible after pressing Escape.")
        else:
            print("INFO: Revision alert is no longer visible after pressing Escape.")
    except PlaywrightTimeoutError:
        print("INFO: Revision alert successfully closed by Escape key (not visible).")
    except Exception as e_check:
        print(f"WARNING: Error while checking revision alert visibility after Escape: {e_check}")

    print("INFO: Proceeding to extract single car details from the page (implementation needed).")
    return ["Single Car (details extraction TBD after attempting to close alert)"]

async def extract_single_car_from_page(page: Page, selectors_dict: dict):
    # print(f"INFO: Attempting to extract single car details from page: {page.url} (implementation needed).")
    await page.wait_for_selector(selectors_dict["singleCarInfo"])
    car = await (await page.query_selector(selectors_dict["singleCarInfo"])).text_content()
    return [car.strip()]

async def handle_multi_cars_popup(page: Page, element_or_page, selectors_dict: dict):
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
async def handle_multi_cars_accounts_popup(page: Page, element_or_page, selectors_dict: dict):
    await page.wait_for_timeout(500)
    results = []
    popup_cars_locator = page.locator(selectors_dict["carsContainer"])
    # print(await popup_cars_locator.count())
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
async def handle_multi_account_popup(page: Page, multi_account_locator, selectors_dict: dict):
    results = []
    car_button_elements = await page.locator(selectors["clientButtonsContainerElements"]).all()
    if not car_button_elements:
        results.append("Multiple Cars Popup detected, but no car data extracted.")
    else:
        for i, el_handle in enumerate(car_button_elements):
            try:
                # Finding a lot of different elements in the same container that's not there
                if await el_handle.locator(selectors_dict["clientsMultipleCarsSvg"]).is_visible():
                    text = await el_handle.locator(selectors_dict["clientName"]).text_content()
                    if text: 
                        await el_handle.locator(selectors_dict["clientName"]).click()
                        client = {"client":text.strip(), "cars": await handle_multi_cars_accounts_popup(page, None, selectors_dict)}
                        await page.keyboard.press("Escape")
                        results.append(client)
                    # else: results.append(f"Car Entry {i+1} (no text)")
            except Exception as e_extract: results.append(f"Car Entry {i+1} (error: {e_extract})")
    print("INFO: Multi-account page/section detected (implementation needed).")
    # return ["Multi-Account Page Detected (further action TBD)"]
    return results


# --- Updated Function to determine page state ---
async def determine_post_phone_entry_state(page: Page, selectors_dict: dict, timeout_ms: int = 10000):
    await page.wait_for_timeout(500) # Brief pause

    # 1. Check for immediate, high-priority overlay/error states
    try:
        not_found_loc = page.locator(selectors_dict["notFound"])
        if await not_found_loc.is_visible(timeout=max(1000, timeout_ms * 0.15)):
            print("DEBUG: State determined: NOT_FOUND")
            return "NOT_FOUND", not_found_loc
    except PlaywrightTimeoutError: pass
    try:
        loc = page.locator(selectors_dict["vehiculesOrClients"])
        if await loc.is_visible(timeout=1500):
            h2 = await loc.text_content()
            if "Clients" in h2:
                return "MULTI_ACCOUNT_POPUP", page.locator(selectors_dict["popupCars"])
            if "Véhicules" in h2:
                return "MULTIPLE_CARS_POPUP", page.locator(selectors_dict["popupCars"])
    except PlaywrightTimeoutError: pass
    
    # try:
    #     popup_cars_loc = page.locator(selectors_dict["popupCars"])
    #     if await popup_cars_loc.is_visible(timeout=max(1000, timeout_ms * 0.25)):
    #         if await popup_cars_loc.locator(selectors_dict["carButtons"]).first.is_visible(timeout=1500):
    #             print("DEBUG: State determined: MULTIPLE_CARS_POPUP")
    #             return "MULTIPLE_CARS_POPUP", popup_cars_loc
    #         else:
    #             print(f"WARNING: Popup '{selectors_dict['popupCars']}' visible, but no car buttons. Might be a different dialog.")
    # except PlaywrightTimeoutError: pass

    # 2. Check if we are on or navigate to the single car page URL
    navigated_to_single_car_url = False
    current_url = page.url
    
    if current_url.startswith(SINGLE_CAR_PAGE_URL_PATTERN):
        print(f"DEBUG: Already on a single car page URL pattern: {current_url}")
        navigated_to_single_car_url = True
    else:
        try:
            # Wait for navigation to the single car page URL.
            # The main `wait_for_load_state("networkidle")` should have handled most of this.
            # This timeout is an additional safeguard or for client-side routing.
            wait_for_url_timeout = max(3000, timeout_ms * 0.5) # Ensure a minimum reasonable timeout
            print(f"DEBUG: Current URL '{current_url}' does not match. Waiting up to {wait_for_url_timeout/1000}s for navigation to '{SINGLE_CAR_PAGE_URL_PATTERN}...'.")
            await page.wait_for_url(lambda url: url.startswith(SINGLE_CAR_PAGE_URL_PATTERN), timeout=wait_for_url_timeout)
            print(f"DEBUG: Successfully navigated to URL: {page.url}")
            navigated_to_single_car_url = True
        except PlaywrightTimeoutError:
            print(f"DEBUG: Timeout waiting for URL to change to '{SINGLE_CAR_PAGE_URL_PATTERN}...'. Current URL: {page.url}")
            navigated_to_single_car_url = False

    if navigated_to_single_car_url:
        # On the single car page URL. Check for the revision alert.
        try:
            revision_alert_loc = page.locator(selectors_dict["revisionAlertPopup"])
            if await revision_alert_loc.is_visible(timeout=2000): # Check for alert on the single car page
                print("DEBUG: State determined: ONE_CAR_PAGE_WITH_REVISION_ALERT (URL matched, alert visible)")
                return "ONE_CAR_PAGE_WITH_REVISION_ALERT", revision_alert_loc
            else: # Alert not visible on the single car page
                print("DEBUG: State determined: ONE_CAR_PAGE_BY_URL (URL matched, no alert)")
                return "ONE_CAR_PAGE_BY_URL", page
        except PlaywrightTimeoutError: # Alert not visible (timeout on is_visible)
            print("DEBUG: State determined: ONE_CAR_PAGE_BY_URL (URL matched, no alert - alert check timed out)")
            return "ONE_CAR_PAGE_BY_URL", page
        
    # 3. If URL did not match single car page pattern, and no other popups found:
    #    Check for `revisionAlertPopup` on the current (unknown) page.
    #    This implies an alert appeared without navigating to the expected single car URL.
    try:
        revision_alert_loc = page.locator(selectors_dict["revisionAlertPopup"])
        if await revision_alert_loc.is_visible(timeout=1000):
            print("WARNING: Revision alert popup visible, but NOT on the expected single car page URL.")
            # This could be a general site alert or an unexpected state.
            # Handling it as ONE_CAR_PAGE_WITH_REVISION_ALERT might be okay if the dismissal logic is generic.
            return "ONE_CAR_PAGE_WITH_REVISION_ALERT", revision_alert_loc
    except PlaywrightTimeoutError:
        pass

    print(f"DEBUG: State determined: UNKNOWN (Exhausted all checks. Current URL: {page.url})")
    return "UNKNOWN", None


# --- Main function to get car information (adjust state handling) ---
async def get_cars_with_state_logic(playwright: Playwright, telephone_number: int):
    start_time = time.time()
    results = []

    chromium = playwright.chromium
    browser = await chromium.launch(headless=True) # Set to True for production
    page = await browser.new_page()

    try:
        await page.goto("https://toyosteu.sdswebapp.com:6819/SDSWeb/login", wait_until="networkidle")
        
        username = os.getenv('USERNAME_SDS')
        password = os.getenv('PASSWORD_SDS')
        if not username or not password:
            print("WARNING: USERNAME_SDS or PASSWORD_SDS environment variables not set.")
        
        await page.fill(selectors["username"], username or "")
        await page.fill(selectors["password"], password or "")
        await page.keyboard.press("Enter")

        await page.wait_for_selector(selectors["redenzvous"], timeout=15000)
        await page.click(selectors["redenzvous"])

        await page.wait_for_selector(selectors["popupAvisaur"], timeout=10000)
        await page.click(selectors["chris"])

        await page.wait_for_selector(selectors["telephoneInput"], timeout=10000)
        await page.fill(selectors["telephoneInput"], str(telephone_number))
        await page.keyboard.press("Enter")

        # IMPORTANT: Wait for page to potentially navigate/load after "Enter"
        try:
            print("INFO: Waiting for page to stabilize after phone entry (networkidle)...")
            await page.wait_for_load_state("networkidle", timeout=7000)
            print(f"INFO: Page stabilized. Current URL: {page.url}")
        except PlaywrightTimeoutError:
            print(f"INFO: Network idle timeout after phone entry. Current URL: {page.url}. Proceeding with element checks.")
        except Exception as e:
            print(f"ERROR: during wait_for_load_state: {e}. Current URL: {page.url}. Proceeding...")

        state, element_or_page = await determine_post_phone_entry_state(page, selectors)
        print(f"INFO: Determined state after phone entry: {state}")

        if state == "NOT_FOUND":
            not_found_message = "Not found message text TBD"
            if element_or_page:
                 try:
                    not_found_message = await element_or_page.text_content(timeout=500)
                 except Exception as e_text:
                    print(f"WARNING: Could not get text from not_found_loc: {e_text}")
            results.append(f"Status: Not Found. Message: {not_found_message}")

        elif state == "MULTIPLE_CARS_POPUP":
            print("INFO: Processing multiple cars from popup...")
            results.extend(await handle_multi_cars_popup(page, element_or_page, selectors))


        elif state == "ONE_CAR_PAGE_WITH_REVISION_ALERT":
            cars_from_page = await handle_revision_alert_and_extract_car(page, element_or_page, selectors)
            results.extend(cars_from_page)

        elif state == "ONE_CAR_PAGE_BY_URL":
            # `element_or_page` is the page object for BY_URL, or the specific locator for BY_SELECTOR
            cars_from_page = await extract_single_car_from_page(page, selectors)
            results.extend(cars_from_page)

        elif state == "MULTI_ACCOUNT_POPUP":
            # ... (same as before)
            account_info = await handle_multi_account_popup(page, element_or_page, selectors)
            results.extend(account_info)
        
        elif state == "UNKNOWN": # Combined all other non-specific outcomes here
            results.append(f"Status: {state}. No definitive state found. Page URL: {page.url}")
            # screenshot_path = f"debug_screenshot_{state}_{time.strftime('%Y%m%d_%H%M%S')}.png"
            # await page.screenshot(path=screenshot_path)
            # print(f"INFO: Screenshot saved to {screenshot_path}")
        else: # Should ideally not be reached
            results.append(f"Status: Unhandled state '{state}'. Page URL: {page.url}")

    except PlaywrightTimeoutError as e_timeout:
        print(f"CRITICAL_ERROR: Playwright Timeout Error during automation: {e_timeout}")
        results.append(f"Error: Timeout occurred - {str(e_timeout).splitlines()[0]}")
    except Exception as e_unexpected:
        print(f"CRITICAL_ERROR: An unexpected error occurred: {e_unexpected}")
        results.append(f"Error: An unexpected error occurred - {str(e_unexpected)}")
    finally:
        await browser.close()
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"INFO: Total execution time: {execution_time:.2f} seconds")
        print(f"INFO: Final Results for phone {telephone_number}: {results}")
        return results

# --- Main execution block ---
async def get_cars(phone_from_user):
    # phone_from_user = 4509745747 # Multi account
    # phone_from_user = 5142944458 # Single car
    # phone_from_user = 5145856444 # Multi cars
    # phone_from_user = 5145856444 # Not found

    print(f"\n--- Testing with number: {phone_from_user} ---")
    result = None
    async with async_playwright() as playwright:
        result = await get_cars_with_state_logic(playwright, phone_from_user)
        # You can add further processing for returned_data here
    return result