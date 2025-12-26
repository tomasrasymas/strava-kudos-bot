import asyncio
import os
from browser_manager import manager
import logging
from dotenv import load_dotenv

load_dotenv(".env")

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

async def main() -> None:
    # Load configuration from environment variables
    number_of_scrolls = int(os.getenv("NUMBER_OF_SCROLLS_TO_END", "5"))
    athletes_to_skip_str = os.getenv("ATHLETES_TO_SKIP", "")
    athletes_to_skip = [name.strip() for name in athletes_to_skip_str.split(",") if name.strip()]
    save_map_path = os.getenv("SAVE_MAP_PATH", None)
    
    logger.info("Configuration:")
    logger.info(f"  - Number of scrolls: {number_of_scrolls}")
    logger.info(f"  - Athletes to skip: {athletes_to_skip}")
    logger.info(f"  - Save map path: {save_map_path}")
    
    await manager.start_browser()

    try:
        page = await manager.new_page()
        await page.goto("https://www.strava.com/dashboard", wait_until="load")
        await page.accept_cookies()

        await page.do_login()

        await page.execute_kudos_giving(
            number_of_scrolls_to_end=number_of_scrolls,
            athletes_to_skip=athletes_to_skip,
            save_map_path=save_map_path
        )
    finally:
        await manager.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
