from typing import Any, List
import asyncio

from playwright.async_api import async_playwright
from playwright.async_api import Page, Locator

from pathlib import Path

from urllib.parse import urlparse

import logging

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

STORAGE_DIR = Path(__file__).parent / 'playwright-state'


class CustomPage:
    """A wrapper class for Playwright Page with custom utility methods for Strava automation.
    
    This class extends the functionality of a Playwright Page by adding Strava-specific
    helper methods while maintaining access to all original Page methods through delegation.
    """
    
    def __init__(self, page: Page) -> None:
        """Initialize the CustomPage wrapper.
        
        Args:
            page: A Playwright Page instance to wrap.
        """
        self._page = page
    
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying Playwright Page instance.
        
        This allows the CustomPage to act as a proxy for the original Page object,
        providing transparent access to all Page methods and properties.
        
        Args:
            name: The name of the attribute to access.
            
        Returns:
            The attribute value from the underlying Page instance.
        """
        return getattr(self._page, name)
    
    async def is_on_dashboard_page(self) -> bool:
        """Check if the current page is the Strava dashboard.
        
        Returns:
            True if the current URL contains "dashboard", False otherwise.
        """
        if "dashboard" not in self._page.url:
            return False

        return True
    
    async def is_on_login_page(self) -> bool:
        """Check if the current page is the Strava login page.
        
        Returns:
            True if the current URL contains "login", False otherwise.
        """
        if "login" not in self._page.url:
            return False

        return True
    
    async def refresh_page(self) -> None:
        """Refresh current page."""
        await self._page.reload(wait_until="load")

    async def accept_cookies(self) -> None:
        """Automatically accept cookies if the cookie consent banner is present.
        
        This method waits few seconds for the cookie banner to appear, then clicks
        the "Accept All" button if found. If no banner is present - log entry is created.
        """
        try:
            cookie_banner_btns = await self._page.wait_for_selector("//div[@id='CybotCookiebotDialogBodyButtonsWrapper']", strict=True, timeout=3000)
            cookie_banner_accept_btn = await cookie_banner_btns.query_selector("//button[@id='CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll']")
            
            if cookie_banner_accept_btn:
                await cookie_banner_accept_btn.click()
            else:
                raise Exception("Cookie banner found but accept button not found.")
        except Exception as e:
            logger.info(f"No cookie banner found. {e}")
    
    async def do_login(self) -> None:
        """ Checks if on login page and performs login by clicking loging with Google
        and giving time for human to perform login manually.
        """
        if not await self.is_on_login_page():
            await self._page.goto("https://www.strava.com/login", wait_until="load")
            await asyncio.sleep(1)

        login_buttons = await self._page.query_selector_all('//button[@data-testid="google_auth_btn"]')
        logger.debug(f"Found {len(login_buttons)} buttons:")
        
        for btn in login_buttons:
            logger.debug(f"Button: {btn.text_content}")
            if await btn.is_visible():
                await btn.click(timeout=10000)
                logger.info(f"Clicked {btn}")
                break
            
        await asyncio.sleep(2)

        if not await self.is_on_dashboard_page():
            logger.info("Do a manual login.")
            await asyncio.sleep(50)
        else:
            logger.info("On dashboard page.")

    async def execute_kudos_giving(self, 
                                   number_of_scrolls_to_end: int = 5, 
                                   athletes_to_skip: List[str] = [],
                                   save_map_path: str = None) -> None:
        """Performs iterative scrolling, kudos giving and page refresh.
        
        Args:
            number_of_scrolls_to_end: number of scrolls to perform. Single scroll meaning scrolling till the end of a page.
            athletes_to_skip: list of athletes to skip
            save_map_path: path where to store athelete actiivty map image
        """
        try:
            for i in range(number_of_scrolls_to_end):
                logger.info(f"Scrolling to the end {i + 1}/{number_of_scrolls_to_end} time.")
                logger.info(10 * "*")
                await self.scroll_to_bottom_of_page()
            
            await self.give_kudos(athletes_to_skip=athletes_to_skip, save_map_path=save_map_path)
        except asyncio.CancelledError:
            logger.info("execute_kudos_giving cancelled, cleaning up…")
            raise
    
    async def scroll_to_bottom_of_page(self) -> None:
        """Scrolls to the end of page and waits a bit for website to render"""
        await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(3)

        await self._page.evaluate("window.scrollBy(0, -200)")
        await asyncio.sleep(12)
        
    async def is_element_in_viewport(self, element: Locator) -> bool:
        """Checks if element is in browsers viewport.

        Args:
            element: The locator of element.
        
        Returns:
            True if the element is in browsers viewport, False otherwise.
        """
        box = await element.bounding_box()
        if not box:
            return False

        viewport = await self._page.evaluate(
            "() => ({ width: window.innerWidth, height: window.innerHeight })"
        )
        top = box["y"]
        bottom = box["y"] + box["height"]

        return not (bottom < 0 or top > viewport["height"])

    async def save_activity_map(self, feed_entry: Locator, save_map_path: str = None) -> None:
        """
        Save the athlete activity map image from a feed entry into the provided directory.

        Args:
            feed_entry - entry where to look for map
            save_map_path - path where to store the map image
        """
        
        if not save_map_path:
            return

        map_img = feed_entry.locator("//img[@data-testid='map']")
        if await map_img.count() != 1:
            return

        src = await map_img.get_attribute("src")
        if not src:
            return

        resp = await self._page.request.get(src)
        if not resp.ok:
            return

        content_type = resp.headers.get("content-type", "image/png")
        extension = content_type.split("/")[-1].split(";")[0]
        
        url_path = Path(urlparse(src).path)
        filename = url_path.stem if url_path.stem else "map"
        
        data_dir = Path(save_map_path)
        data_dir.mkdir(parents=True, exist_ok=True)
        target_path = data_dir / f"{filename}.{extension}"

        if target_path.exists() and target_path.stat().st_size > 0:
            logger.info(f"Map: already exists {target_path}")
            return

        target_path.write_bytes(await resp.body())

        logger.info(f"Map: saved {target_path}")
    
    async def give_kudos(self, athletes_to_skip: List[str] = [], save_map_path: str = None) -> None:
        """
        Click all visible kudos buttons that have not yet been clicked.
        This method: locates all kudos buttons currently in the viewport, filters out those already clicked, 
        licks each remaining kudos button.

        Args:
            athletes_to_skip: list of atheletes ('in' will be used to check) to skip kudos giving.
        
        Notes:
            Scrolling must be performed **after** calling this method 
            in order to reveal additional buttons outside the current view.
        """
        feed_entries = self._page.locator("div[data-testid='web-feed-entry']")
        feed_entries_count = await feed_entries.count()

        logger.debug(f"Feed entries count {feed_entries_count}")

        for i in range(feed_entries_count):
            feed_entry = feed_entries.nth(i)

            if save_map_path:
                await self.save_activity_map(feed_entry=feed_entry,
                                             save_map_path=save_map_path)

            kudos_buttons = feed_entry.locator("//button[@data-testid='kudos_button']")
            kudos_buttons_count = await kudos_buttons.count()

            logger.info(30 * "-")
            logger.info(f"Kudos buttons count {kudos_buttons_count}")

            for j in range(kudos_buttons_count):
                kudos_button = kudos_buttons.nth(j)

                if kudos_buttons_count == 1:
                    owner_name = feed_entry.locator("//a[@data-testid='owners-name']")
                    owner_name = await owner_name.inner_text()
                elif kudos_buttons_count >= 2:
                    entry_li = kudos_button.locator("xpath=ancestor::li[.//*[@data-testid='entry-header']]")
                    owner_name = entry_li.locator("//a[@data-testid='owners-name']").first
                    owner_name = await owner_name.inner_text()
                    
                logger.info(f"Owner: {owner_name}")

                unfilled_kudos_button = kudos_button.locator("svg[data-testid='unfilled_kudos']")
                is_unfilled = await unfilled_kudos_button.count() > 0

                if not is_unfilled:
                    logger.info("-> Already clicked.")
                    continue

                if athletes_to_skip and any(athlete.lower() in owner_name.lower() for athlete in athletes_to_skip):
                    logger.info("-> Skipping.")
                    continue

                await kudos_button.click()
                logger.info("-> Clicked.")
            
            await asyncio.sleep(3)

    async def do_scroll(self, num_of_scrolls: int = 1, scroll_px: int = 800) -> None:
        """
        Scroll the page a specified number of times.

        Args:
            num_of_scrolls (int, optional):
                The number of scroll actions to perform. Defaults to 1.
            scroll_px (int, optional):
                Number of pixels to scroll down on each scroll action. Defaults to 800.

        Notes:
            Each scroll action should move the viewport enough to reveal
            new kudos buttons for `give_kudos()` to process.
        """
        for _ in range(num_of_scrolls):
            await self._page.mouse.wheel(0, scroll_px)
            await asyncio.sleep(5000)


class BrowserManager:
    """A singleton manager for Playwright browser instances and contexts.
    
    This class implements the Singleton pattern to ensure only one browser instance
    is active throughout the application lifecycle. It manages the browser context
    with persistent state storage for authentication and session management.
    """
    _instance = None

    def __new__(cls):
        """Create or return the singleton instance of BrowserManager.
        
        Returns:
            The singleton BrowserManager instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the BrowserManager with None values for playwright and context."""
        self.playwright = None
        self.context = None

    async def start_browser(self, headless: bool = True) -> None:
        """Start the Playwright browser with a persistent context.
        
        This method initializes Playwright (if not already started) and launches a
        browser with persistent storage.
        
        The persistent context ensures that login sessions and cookies are maintained
        across browser restarts.
        """
        if not self.playwright:
            self.playwright = await async_playwright().start()
        
        if STORAGE_DIR.exists():
            logger.info("Found saved authentication state")
        else:
            logger.info("No saved authentication state found - will save after first login")

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(STORAGE_DIR),
            headless=headless,
            channel="chrome",
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="Europe/Vilnius",
            service_workers="allow",
            permissions=["geolocation"],
            geolocation={"latitude": 54.6872, "longitude": 25.2797},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--mute-audio"
            ],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    
    async def new_page(self) -> CustomPage:
        """Create a new browser page wrapped in CustomPage.
        
        Returns:
            A CustomPage instance wrapping a new Playwright Page.
        """
        page = await self.context.new_page()
        return CustomPage(page)
    
    async def close_browser(self) -> None:
        """Close the browser context and stop Playwright.
        
        This method performs a graceful shutdown by:
        1. Closing the browser context (if it exists)
        2. Stopping the Playwright instance (if it exists)
        """
        if self.context:
            await self.context.close()
        
        if self.playwright:
            await self.playwright.stop()


manager = BrowserManager()
