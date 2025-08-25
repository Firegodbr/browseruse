from playwright.async_api import Playwright, Page

# --- Selectors (kept as provided by user, with notes) ---
selectors = {
    "username": "#username",
    "password": "#password",
    "redenzvous": "div[gs-x='3'] button.MuiButtonBase-root",
    "popupAvisaur": "div.KL-Index-List-Virtuoso",
    "chris": "div.KL-Index-List-Virtuoso > div > div > div:nth-child(3) > button > div",
    "telephoneInput": "#CUSTOMER_PHONE",
    "popupCars": "body > div.MuiDialog-root.e7bgrhc8.KL-Dialog-root.e1h4yr2d8.e1de0imv0.MuiModal-root.css-1308mf0.e1de0imv0 > div.MuiDialog-container.MuiDialog-scrollPaper.css-fh1hs4.e1de0imv0",
    "vehiculesOrClients": "h2.MuiTypography-root.MuiTypography-h2.MuiTypography-alignLeft.css-csbyx1.e1de0imv0",
    "carsContainer": "div[data-testid='virtuoso-item-list'] > div",
    "carButtons": "button > div.css-1y9oiq5.egp32mx11 > div.css-1dmiggy.egp32mx7",
    "clientButtonsContainer": "div[data-testid='virtuoso-item-list']",
    "clientButtonsContainerElements": "div[data-testid='virtuoso-item-list'] > div",
    "clientName": "div.MuiTypography-root.MuiTypography-body2.MuiTypography-alignLeft.css-rz7rqr.e1de0imv0",
    "clientsMultipleCarsSvg": "svg.svg-inline--fa.fa-car.css-1on8xt0.e9n5qpy17",
    "clientsFilterBtn": "button.MuiButtonBase-root.MuiIconButton-root.MuiIconButton-sizeMedium.KL-Filter-button.FILTER.e1q00zgk7.e1de0imv0.css-1369qmj.e1de0imv0",
    "notFound": "#snackbar_ERROR > div > div.MuiSnackbarContent-message.KL-SnackButton-CONTENT_MESSAGE.css-1o19295.e1de0imv0 > div > div",
    "revisionAlertPopup": "body > div.MuiDialog-root.e134bnih77.KL-Dialog-root.e1h4yr2d8.e1de0imv0.MuiModal-root.css-1i4r1ts.e1de0imv0 > div.MuiDialog-container.MuiDialog-scrollPaper.css-fh1hs4.e1de0imv0",
    "singleCarInfo": "div.MuiTypography-root.MuiTypography-body2.MuiTypography-alignLeft.css-rz7rqr.e1de0imv0",
    "popupTitle": ".MuiPaper-root div.KL-Dialog-headerTitle h2",
    "carsList": "button.MuiButtonBase-root div.MuiTypography-root",
    "popupTitle-add-redenvous": ".MuiPaper-root span.KL-Tooltip-anchor button.MuiButtonBase-root div div svg.fa-plus",
    "previous-step": "div[cy='previous-step']",
    "cylanders": "div[cy='appointments-step2'] div.css-x0x8yu.e6a24jq34 h6.MuiTypography-root.MuiTypography-subtitle2.MuiTypography-alignLeft.e6a24jq20.css-1hph34g.e1de0imv0",
    "gas-pump-HV": "svg.svg-inline--fa.fa-gas-pump.css-18ga6n6.e73aqgv3[data-icon='gas-pump']",
    "one-car-detect":"#root > div.css-pxu7mn.evwjw926 > div > div > div.css-48tder.evwjw922 > div.css-1bppemt.e1p817c0 > div.css-1qvekf5.e12pldzn0 > div > div > div > div > div > div > div > div.css-yien0c.e1iianp710 > div > div:nth-child(4) > div > div.e1iianp73.css-olii74.e1bwztlu14 > div > div.css-3ye0ev.e1bwztlu9 > div.css-bkt2fw.e1bwztlu2 > h2",
    # Make an appointment
    "make-appointment": {
        "car-page": "span.css-1nys5gm.euo2vaf14 svg.svg-inline--fa.fa-car.superChip-XLarge.KL-SuperChip-superChipIcon.css-19btgxe.euo2vaf17",
        "next-step": "div[cy='next-step']",
        "add-operation-button": "button[cy='add-operation-button']",
        "container-operations": "body > div.MuiDialog-root.eujvbsz18.KL-Dialog-root.e1h4yr2d8.e1de0imv0.MuiModal-root.css-1gx1cd8.e1de0imv0 > div.MuiDialog-container.MuiDialog-scrollPaper.css-fh1hs4.e1de0imv0 > div",
        "operation-input": "input#maintenanceKey",
        "calender-next": "div.css-1g8uxsn.e1wi0epg2 span.KL-Tooltip-anchor.css-1wrwbnl.e1di1sx80:nth-of-type(3) button.MuiButtonBase-root",
        "dialog-close": "button[cy='dialog-close']",
        "taken-by": "input[id='takenBy.userKey']",
        "finalize-qppointment": "div[cy='finalize-default-step']",
        "time-table": "div[data-testid='virtuoso-item-list']",
        "time-scrooler": "div.KL-Card-cardContentNoScroll.css-ccyqm.e1bwztlu12 div div[data-testid='virtuoso-scroller']",
        "transport-input": "input.PrivateSwitchBase-input[type='radio']",
        "time-availability": "div.css-122qvno.e1ri7uk73 div.e1ri7uk72.KL-Tile-root.css-fif1n0.e1d32nym9",
        "not-available": "div.css-122qvno.e1ri7uk73 div.e1ri7uk72.KL-Tile-root.KL-Tile-disabled.css-4b2f9a.e1d32nym9",
        "time": "div.css-122qvno.e1ri7uk73",
        "week": "div.MuiTypography-root.MuiTypography-body2.MuiTypography-alignLeft.e1wi0epg0.css-8gqjsk.e1de0imv0"
    },
    "denier-service-popup": {
        "button-activate": "button.MuiButtonBase-root.MuiIconButton-root.MuiIconButton-sizeMedium.KL-IconButton-root.e-size-medium.e-type-primary.ef1u7kc6.e1de0imv0.css-qmac4w.e1de0imv0 .KL-IconButton-container.css-1cr8hl2.ef1u7kc4 svg[data-icon='clock-rotate-left']",
        "header-title": ".MuiDialog-container .MuiPaper-root .KL-Dialog-headerTitle h2.MuiTypography-root",
        "top-element": "div[data-testid='virtuoso-top-item-list']",
        "wrapper-els": "div[data-testid='virtuoso-item-list']"
    }
}
transport_types = ["aucun", "courtoisie", "attente", "reconduire", "laisser"]
daysWeek = {
    "Sunday": 1,
    "Monday": 2,
    "Tuesday": 3,
    "Wednesday": 4,
    "Thursday": 5,
    "Friday": 6,
    "Saturday": 7,
}


async def login(page: Page, username: str, password: str) -> None:
    await page.fill(selectors["username"], username or "")
    await page.fill(selectors["password"], password or "")
    await page.keyboard.press("Enter")
    await page.wait_for_selector(selectors["redenzvous"], timeout=15000)


async def insert_phone_number(page: Page, telephone_number: int) -> None:
    await page.wait_for_selector(selectors["telephoneInput"], timeout=10000)
    await page.fill(selectors["telephoneInput"], str(telephone_number))
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(1000)


async def click_redenvous(page: Page) -> None:
    await page.wait_for_selector(selectors["redenzvous"], timeout=15000)
    await page.click(selectors["redenzvous"])


async def chose_aviseurs(page: Page) -> None:
    await page.wait_for_selector(selectors["popupAvisaur"], timeout=10000)
    await page.click(selectors["chris"])

import json

def get_service_info(model: str, year: int, engine_type: str, service_type: str) -> dict | None:
    """
    Returns the service name and service ID(s) from the JSON file.
    
    Parameters:
        model (str): Car model (e.g., "CAMRY")
        year (int): Production year (e.g., 2020)
        engine_type (str): Engine type (e.g., "V6", "L4", "HV")
        service_type (str): One of "oil", "service1", "service2", "service3"
        json_file (str): Path to the JSON file
    
    Returns:
        dict | None: { "service_name": str, "service_ids": list[str] } or None if not found
    """
    
    # Map input service_type to JSON field
    service_map = {
        "oil": ("Oil Change", "Oil Change Codes"),
        "service1": ("Service 1", "Service 1 Change Codes"),
        "service2": ("Service 2", "Service 2 Change Codes"),
        "service3": ("Service 3", "Service 3 Change Codes"),
    }
    
    if service_type not in service_map:
        raise ValueError(f"Invalid service_type. Choose from {list(service_map.keys())}")
    
    service_name, json_field = service_map[service_type]
    
    # Load JSON data
    with open("./Toyota Code Service et Oil.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Search for matching entry
    for entry in data:
        if (entry["Model"].upper() == model.upper() and
            entry["Engine Type"].upper() == engine_type.upper() and
            year in entry["Years"]):
            
            return {
                "service_name": service_name,
                "service_ids": entry.get(json_field, [])
            }
    
    return None
