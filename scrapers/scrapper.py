from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Callable, TypeVar, Generic
import logging
import os
import time
from playwright.async_api import Page, Playwright, async_playwright, Locator
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from helpers.function import normalize_canadian_number
from .const import selectors, daysWeek

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TimeoutConfig:
    """Centralized timeout configuration"""
    QUICK = 1000
    DEFAULT = 5000
    MEDIUM = 10000
    LONG = 15000
    NAVIGATION = 30000


class ScraperError(Exception):
    """Base exception for scraper errors"""
    pass


class NavigationError(ScraperError):
    """Raised when navigation fails"""
    pass


class ElementNotFoundError(ScraperError):
    """Raised when required element is not found"""
    pass


class PopupHandlingError(ScraperError):
    """Raised when popup handling fails"""
    pass


@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_attempts: int = 3
    base_delay: float = 0.5
    exponential_backoff: bool = True

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt"""
        if self.exponential_backoff:
            return self.base_delay * (2 ** attempt)
        return self.base_delay


class PageState(Enum):
    """Enumeration of possible page states"""
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"
    SINGLE_CAR = "single_car"
    MULTIPLE_CARS = "multiple_cars"
    POPUP_PRESENT = "popup_present"
    ERROR = "error"


@dataclass
class StateResult(Generic[T]):
    """Result of state detection"""
    state: PageState
    data: Optional[T] = None
    error: Optional[str] = None
    element: Optional[Locator] = None


class Scrapper(ABC):
    """
    Base scraper class with improved error handling, retry logic, and state management.
    """

    selectors = selectors
    daysWeek = daysWeek

    def __init__(self, telephone: str):
        self.telephone = normalize_canadian_number(telephone)
        self.page: Optional[Page] = None
        self.timeout = TimeoutConfig()
        self._username = os.getenv('USERNAME_SDS')
        self._password = os.getenv('PASSWORD_SDS')
        self._base_url = os.getenv('SDS_URL')

        # Performance tracking
        self._operation_times: Dict[str, float] = {}

    # ==================== Utility Methods ====================

    def _track_operation(self, operation_name: str):
        """Context manager for tracking operation duration"""
        class OperationTracker:
            def __init__(self, scraper, name):
                self.scraper = scraper
                self.name = name
                self.start_time = None

            def __enter__(self):
                self.start_time = time.time()
                logger.info(f"Starting: {self.name}")
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                self.scraper._operation_times[self.name] = duration
                logger.info(f"Completed: {self.name} ({duration:.2f}s)")
                if exc_type:
                    logger.error(f"Failed: {self.name} - {exc_val}")

        return OperationTracker(self, operation_name)

    async def retry_operation(
        self,
        operation: Callable,
        operation_name: str,
        retry_config: Optional[RetryConfig] = None
    ) -> Any:
        """
        Retry an operation with configurable backoff.

        Args:
            operation: Async callable to retry
            operation_name: Name for logging
            retry_config: Retry configuration (uses default if None)

        Returns:
            Result of successful operation

        Raises:
            Last exception if all retries fail
        """
        config = retry_config or RetryConfig()
        last_exception = None

        for attempt in range(config.max_attempts):
            try:
                logger.debug(
                    f"{operation_name}: Attempt {attempt + 1}/{config.max_attempts}")
                result = await operation()
                if attempt > 0:
                    logger.info(
                        f"{operation_name}: Succeeded on attempt {attempt + 1}")
                return result
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"{operation_name}: Attempt {attempt + 1} failed - {str(e)}"
                )

                if attempt < config.max_attempts - 1:
                    delay = config.get_delay(attempt)
                    logger.debug(f"Waiting {delay}s before retry...")
                    await self._safe_wait(delay * 1000)

        logger.error(
            f"{operation_name}: All {config.max_attempts} attempts failed")
        raise last_exception

    async def _safe_wait(self, timeout_ms: int) -> None:
        """Safe wrapper for page.wait_for_timeout"""
        if self.page:
            await self.page.wait_for_timeout(timeout_ms)

    async def clear_intermediate_popups(self) -> None:
        await self.page.locator('div[role="dialog"]').click()

    async def wait_for_selector_safe(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: str = "visible"
    ) -> Optional[Locator]:
        """
        Safely wait for selector with better error messages.

        Returns:
            Locator if found, None if timeout
        """
        if not self.page:
            raise RuntimeError("Page not initialized")

        timeout = timeout or self.timeout.DEFAULT

        try:
            locator = self.page.locator(selector)
            await locator.wait_for(state=state, timeout=timeout)
            return locator
        except PlaywrightTimeoutError:
            logger.warning(
                f"Selector not found: {selector} (timeout: {timeout}ms)")
            return None
        except Exception as e:
            logger.error(f"Error waiting for selector {selector}: {e}")
            return None

    async def click_with_retry(
        self,
        selector: str,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Click element with automatic retry on failure.

        Returns:
            True if successful, False otherwise
        """
        async def click_operation():
            locator = await self.wait_for_selector_safe(selector, timeout)
            if not locator:
                raise ElementNotFoundError(f"Element not found: {selector}")
            await locator.click()

        try:
            await self.retry_operation(
                click_operation,
                f"Click: {selector}",
                RetryConfig(max_attempts=2)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to click {selector}: {e}")
            return False

    # ==================== Popup Handling ====================

    async def handle_popup_by_title(
        self,
        expected_titles: list[str],
        handler: Callable,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Generic popup handler that checks title and applies handler.

        Args:
            expected_titles: List of possible popup titles
            handler: Async function to handle the popup
            timeout: Timeout in ms

        Returns:
            True if popup was found and handled
        """
        if not self.page:
            return False

        timeout = timeout or self.timeout.QUICK

        try:
            popup_title = self.page.locator(self.selectors["popupTitle"])
            await popup_title.wait_for(state="visible", timeout=timeout)

            title_text = (await popup_title.text_content() or "").strip()
            logger.info(f"Found popup: {title_text}")

            for expected in expected_titles:
                if expected in title_text:
                    logger.info(f"Handling popup: {expected}")
                    await handler()
                    await self._safe_wait(500)
                    return True

            logger.warning(f"Unexpected popup title: {title_text}")
            return False

        except PlaywrightTimeoutError:
            return False
        except Exception as e:
            logger.error(f"Error handling popup: {e}")
            return False

    async def dismiss_popup_strategies(self, popup_locator: Locator) -> bool:
        """
        Try multiple strategies to dismiss a popup.

        Returns:
            True if successfully dismissed
        """
        strategies = [
            ("Escape key", lambda: self.page.keyboard.press("Escape")),
            ("Close button (aria)", lambda: popup_locator.locator(
                "button[aria-label*='close']").first.click(timeout=1000)),
            ("Close button (class)", lambda: popup_locator.locator(
                ".close, .dismiss, [data-dismiss]").first.click(timeout=1000)),
            ("Outside click", lambda: self.page.mouse.click(10, 10)),
        ]

        for strategy_name, strategy in strategies:
            try:
                logger.debug(f"Trying dismiss strategy: {strategy_name}")
                await strategy()
                await self._safe_wait(300)

                if not await popup_locator.is_visible(timeout=500):
                    logger.info(
                        f"Successfully dismissed popup with: {strategy_name}")
                    return True
            except Exception as e:
                logger.debug(f"Strategy {strategy_name} failed: {e}")
                continue

        logger.warning("All dismiss strategies failed")
        return False

    # ==================== Navigation & Login ====================

    async def login(self) -> None:
        """Login with improved error handling"""
        if not self.page:
            raise RuntimeError("Page must be initialized before login")

        with self._track_operation("login"):
            try:
                await self.page.fill(self.selectors["username"], self._username or "")
                await self.page.fill(self.selectors["password"], self._password or "")
                await self.page.keyboard.press("Enter")

                # Wait for successful login indicator
                await self.page.wait_for_selector(
                    self.selectors["redenzvous"],
                    timeout=self.timeout.LONG
                )
                logger.info("Login successful")

            except PlaywrightTimeoutError:
                raise NavigationError(
                    "Login failed - timeout waiting for dashboard")
            except Exception as e:
                raise NavigationError(f"Login failed: {str(e)}")

    async def navigate_to_appointments(self) -> None:
        """Navigate to appointments section"""
        with self._track_operation("navigate_to_appointments"):
            await self.click_redenvous()
            await self.chose_aviseurs()

    async def click_redenvous(self) -> None:
        """Click appointments button"""
        if not self.page:
            raise RuntimeError("Page not initialized")

        await self.wait_for_selector_safe(
            self.selectors["redenzvous"],
            timeout=self.timeout.LONG
        )
        await self.page.click(self.selectors["redenzvous"])
        await self._safe_wait(500)

    async def chose_aviseurs(self) -> None:
        """Select advisors popup"""
        if not self.page:
            raise RuntimeError("Page not initialized")

        await self.wait_for_selector_safe(
            self.selectors["popupAvisaur"],
            timeout=self.timeout.DEFAULT
        )
        await self.page.click(self.selectors["chris"])

    async def insert_phone_number(self) -> None:
        """Insert phone number with validation"""
        if not self.page:
            raise RuntimeError("Page not initialized")

        with self._track_operation("insert_phone_number"):
            await self.wait_for_selector_safe(
                self.selectors["telephoneInput"],
                timeout=self.timeout.DEFAULT
            )
            await self.page.fill(self.selectors["telephoneInput"], self.telephone)
            await self.page.keyboard.press("Enter")
            await self._safe_wait(1000)
            logger.info(f"Inserted phone number: {self.telephone}")

    # ==================== Abstract Methods ====================

    @abstractmethod
    async def scrapper(self, playwright: Playwright) -> Any:
        """
        Main scraping logic - must be implemented by subclasses.
        Should initialize self.page and perform scraping operations.
        """
        pass

    async def action(self) -> Any:
        """
        Execute the scraping action with performance tracking.
        """
        start_time = time.time()
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting scraper for: {self.telephone}")
        logger.info(f"{'='*60}")

        try:
            async with async_playwright() as playwright:
                result = await self.scrapper(playwright)

            duration = time.time() - start_time
            logger.info(f"\n{'='*60}")
            logger.info(f"Scraper completed successfully")
            logger.info(f"Total duration: {duration:.2f}s")
            logger.info(f"Operation breakdown:")
            for op_name, op_time in self._operation_times.items():
                logger.info(f"  - {op_name}: {op_time:.2f}s")
            logger.info(f"{'='*60}\n")

            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"\n{'='*60}")
            logger.error(f"Scraper failed after {duration:.2f}s")
            logger.error(f"Error: {str(e)}")
            logger.error(f"{'='*60}\n")
            raise

    def get_performance_report(self) -> Dict[str, float]:
        """Get performance metrics for the scraper run"""
        return self._operation_times.copy()
