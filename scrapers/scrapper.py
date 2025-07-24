from helpers.function import normalize_canadian_number
from playwright.async_api import async_playwright, Playwright, Page
from typing import Optional
from .const import selectors, daysWeek
import os, time, logging
from dotenv import load_dotenv
from abc import ABC, abstractmethod


load_dotenv()

logger = logging.getLogger(__name__)

class Scrapper(ABC):
    selectors = selectors
    daysWeek = daysWeek
    transport_types = ["aucun", "courtoisie", "attente", "reconduire", "laisser"]
    username = os.getenv('USERNAME_SDS')
    password = os.getenv('PASSWORD_SDS')

    def __init__(self, telephone: str):
        self.telephone = normalize_canadian_number(telephone)
        self.page: Optional[Page] = None

    async def login(self) -> None:
        if not self.page:
            raise RuntimeError("Page must be set before calling login()")
        await self.page.fill(self.selectors["username"], self.username or "")
        await self.page.fill(self.selectors["password"], self.password or "")
        await self.page.keyboard.press("Enter")
        await self.page.wait_for_selector(self.selectors["redenzvous"], timeout=15000)

    async def insert_phone_number(self) -> None:
        if not self.page:
            raise RuntimeError("Page must be set before calling insert_phone_number()")
        await self.page.wait_for_selector(self.selectors["telephoneInput"], timeout=10000)
        await self.page.fill(self.selectors["telephoneInput"], self.telephone)
        await self.page.keyboard.press("Enter")
        await self.page.wait_for_timeout(1000)

    async def click_redenvous(self) -> None:
        if not self.page:
            raise RuntimeError("Page must be set before calling click_redenvous()")
        await self.page.wait_for_selector(self.selectors["redenzvous"], timeout=15000)
        await self.page.click(self.selectors["redenzvous"])
        await self.page.wait_for_timeout(500)

    async def chose_aviseurs(self) -> None:
        if not self.page:
            raise RuntimeError("Page must be set before calling chose_aviseurs()")
        await self.page.wait_for_selector(self.selectors["popupAvisaur"], timeout=10000)
        await self.page.click(self.selectors["chris"])

    @abstractmethod
    async def scrapper(self, playwright: Playwright) -> str:
        """This must be implemented by subclasses and should set self.page"""
        pass

    async def action(self) -> str:
        start_time = time.time()
        logger.info(f"\n--- Checking cars with number: {self.telephone} ---")

        async with async_playwright() as playwright:
            result = await self.scrapper(playwright)

        end_time = time.time()
        logger.info(f"Total execution time: {end_time - start_time:.2f} seconds")
        return result
