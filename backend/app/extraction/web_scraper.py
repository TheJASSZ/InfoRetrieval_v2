import trafilatura
from playwright.async_api import async_playwright
from app.utils.logger import get_logger

logger = get_logger("web_scraper")


def scrape_with_trafilatura(url: str) -> str | None:
    """Fast static HTML extraction using Trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            logger.warning(f"Trafilatura fetch failed for {url}")
            return None
        text = trafilatura.extract(
            downloaded,
            include_tables=True,
            include_comments=False,
            favor_precision=True,
        )
        if text and len(text.strip()) > 50:
            logger.info(f"Trafilatura extracted {len(text)} chars from {url}")
            return text.strip()
        return None
    except Exception as e:
        logger.error(f"Trafilatura error for {url}: {e}")
        return None


async def scrape_with_playwright(url: str) -> str | None:
    """Dynamic JS rendering via Playwright for JS-heavy SPAs."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            # Wait for body content to render
            await page.wait_for_selector("body", timeout=10000)
            content = await page.inner_text("body")
            await browser.close()

            if content and len(content.strip()) > 50:
                logger.info(f"Playwright extracted {len(content)} chars from {url}")
                return content.strip()
            return None
    except Exception as e:
        logger.error(f"Playwright error for {url}: {e}")
        return None


async def extract_from_url(url: str) -> str:
    """Try Trafilatura first (fast), fall back to Playwright (thorough)."""
    text = scrape_with_trafilatura(url)
    if text:
        return text

    logger.info(f"Falling back to Playwright for {url}")
    text = await scrape_with_playwright(url)
    if text:
        return text

    raise ValueError(f"Failed to extract content from URL: {url}")
