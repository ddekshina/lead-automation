import requests
import re
import json
import logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

REQUEST_TIMEOUT = 15


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_url(url: str) -> str:
    """Ensures URL has http/https scheme."""
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        return f"https://{url}"
    return url


def fetch_page(url: str) -> str | None:
    """Fetches raw HTML. Returns None on any failure."""
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        logger.warning(f"[SCRAPER] Timeout fetching {url}")
    except requests.exceptions.ConnectionError:
        logger.warning(f"[SCRAPER] Connection error for {url}")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"[SCRAPER] HTTP {e.response.status_code} for {url}")
    except Exception as e:
        logger.warning(f"[SCRAPER] Unexpected error fetching {url}: {e}")
    return None


def extract_meta_description(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return clean_text(meta["content"])
    og_meta = soup.find("meta", attrs={"property": "og:description"})
    if og_meta and og_meta.get("content"):
        return clean_text(og_meta["content"])
    return ""


def extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return clean_text(soup.title.string)
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        return clean_text(og_title["content"])
    return ""


def extract_headings(soup: BeautifulSoup) -> list[str]:
    headings = []
    for tag in ["h1", "h2", "h3"]:
        for item in soup.find_all(tag):
            text = clean_text(item.get_text())
            if text and len(text) > 3:
                headings.append(text)
    return headings[:15]


def extract_visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "nav", "footer", "head"]):
        tag.extract()
    text = soup.get_text(separator=" ")
    return clean_text(text)[:5000]


def detect_social_links(soup: BeautifulSoup) -> dict:
    social_links = {
        "linkedin": None,
        "twitter": None,
        "facebook": None,
        "instagram": None
    }
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        if "linkedin.com" in href and not social_links["linkedin"]:
            social_links["linkedin"] = href
        elif ("twitter.com" in href or "x.com" in href) and not social_links["twitter"]:
            social_links["twitter"] = href
        elif "facebook.com" in href and not social_links["facebook"]:
            social_links["facebook"] = href
        elif "instagram.com" in href and not social_links["instagram"]:
            social_links["instagram"] = href
    return social_links


def scrape_company_data(lead_data: dict) -> dict:
    """
    Main enrichment pipeline.
    Accepts a full lead_data dict, scrapes the company website,
    and returns combined lead + research data.

    Always succeeds — falls back gracefully if scraping fails.
    """
    website = normalize_url(lead_data.get("company_website", ""))

    scraped_research = {
        "website": website,
        "page_title": "",
        "meta_description": "",
        "headings": [],
        "social_links": {},
        "homepage_text_preview": "",
        "scrape_status": "failed"
    }

    html = fetch_page(website)

    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            scraped_research.update({
                "page_title": extract_title(soup),
                "meta_description": extract_meta_description(soup),
                "headings": extract_headings(soup),
                "social_links": detect_social_links(soup),
                "homepage_text_preview": extract_visible_text(soup),
                "scrape_status": "success"
            })
            logger.info(f"[SCRAPER] Successfully scraped {website}")
        except Exception as e:
            logger.warning(f"[SCRAPER] Parsing failed for {website}: {e}")
            scraped_research["scrape_status"] = "parse_failed"
    else:
        # Fallback: use company name and industry as minimal context
        scraped_research["meta_description"] = (
            f"{lead_data.get('company_name')} operates in the "
            f"{lead_data.get('industry')} industry."
        )
        scraped_research["headings"] = [lead_data.get("company_name", "")]
        logger.warning(f"[SCRAPER] Falling back to minimal context for {website}")

    return {
        "lead_info": {
            "full_name": lead_data.get("full_name"),
            "work_email": lead_data.get("work_email"),
            "company_name": lead_data.get("company_name"),
            "industry": lead_data.get("industry"),
            "company_size": lead_data.get("company_size"),
            "current_challenge": lead_data.get("current_challenge"),
            "improvement_goal": lead_data.get("improvement_goal"),
        },
        "company_research": scraped_research
    }


# --- Example Usage ---
if __name__ == "__main__":
    sample_lead = {
        "full_name": "Jane Smith",
        "work_email": "jane@example.com",
        "company_name": "OpenAI",
        "company_website": "https://openai.com",
        "industry": "AI / Technology",
        "company_size": "1000+",
        "current_challenge": "We want to improve our customer support automation pipeline.",
        "improvement_goal": "We want faster response times using AI-driven systems."
    }
    result = scrape_company_data(sample_lead)
    print(json.dumps(result, indent=2))
