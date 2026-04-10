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
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            # Wait for JS rendering and potential Cloudflare challenge
            await page.wait_for_timeout(3000)
            content = await page.inner_text("body")

            # Check if we hit a Cloudflare/bot check page
            if content and "security" in content.lower() and "verification" in content.lower():
                logger.info(f"Cloudflare challenge detected for {url}, waiting...")
                await page.wait_for_timeout(5000)
                content = await page.inner_text("body")

            await browser.close()

            if content and len(content.strip()) > 50:
                # Filter out security/bot check pages
                lower = content.lower()
                if "performing security verification" in lower and len(content) < 200:
                    logger.warning(f"Only got security page for {url}")
                    return None
                logger.info(f"Playwright extracted {len(content)} chars from {url}")
                return content.strip()
            return None
    except Exception as e:
        logger.error(f"Playwright error for {url}: {e}")
        return None


def _is_garbage_content(text: str) -> bool:
    """Detect scraped content that is garbage (blocked pages, JSON blobs, etc.)."""
    lower = text.lower().strip()

    # Cloudflare / bot protection pages
    garbage_markers = [
        "performing security verification",
        "this website is using a security service",
        "enable javascript and cookies to continue",
        "please verify you are a human",
        "access denied",
        "403 forbidden",
        "you have been banned",
        "attention required! | cloudflare",
        "just a moment...",
        "checking your browser before accessing",
        "ray id:",
    ]
    if any(marker in lower for marker in garbage_markers):
        logger.warning(f"Garbage detected: matched security/block marker")
        return True

    # Raw JSON / structured data (not actual article content)
    stripped = text.strip()
    if (stripped.startswith("{") or stripped.startswith("[")) and len(stripped) > 100:
        # Check if it looks like JSON
        brace_count = stripped.count("{") + stripped.count("[")
        if brace_count > 5:
            logger.warning("Garbage detected: looks like raw JSON")
            return True

    # Mostly non-alphabetic (encoded data, URLs, etc.)
    alpha_chars = sum(1 for c in text if c.isalpha())
    if len(text) > 100 and alpha_chars / len(text) < 0.4:
        logger.warning("Garbage detected: low alphabetic ratio")
        return True

    return False


async def extract_from_url(url: str) -> str:
    """Try Trafilatura first (fast), fall back to Playwright (thorough)."""
    # Skip URLs that are unlikely to have useful content
    skip_domains = ["outlook.office.com", "mail.google.com", "accounts.google.com",
                    "login.", "signin.", "auth."]
    if any(d in url.lower() for d in skip_domains):
        raise ValueError(f"Skipping login/mail URL: {url}")

    text = scrape_with_trafilatura(url)
    if text:
        if _is_garbage_content(text):
            logger.warning(f"Trafilatura returned garbage for {url}, trying Playwright")
        else:
            return text

    logger.info(f"Falling back to Playwright for {url}")
    text = await scrape_with_playwright(url)
    if text:
        if _is_garbage_content(text):
            raise ValueError(f"Only garbage content extracted from URL: {url}")
        return text

    raise ValueError(f"Failed to extract content from URL: {url}")
