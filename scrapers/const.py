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
        "transport-input": "input.PrivateSwitchBase-input[type='radio']"
    },
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
