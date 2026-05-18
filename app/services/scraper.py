import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import json
import re


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def clean_text(text: str) -> str:
    """
    Cleans extracted webpage text.
    """

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_url(url: str) -> str:
    """
    Ensures URL has a valid scheme.
    """

    parsed = urlparse(url)

    if not parsed.scheme:
        return f"https://{url}"

    return url


def fetch_page(url: str) -> str | None:
    """
    Fetches raw HTML from a webpage.
    """

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        return response.text

    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None


def extract_meta_description(soup: BeautifulSoup) -> str:
    """
    Extracts meta description from webpage.
    """

    meta = soup.find("meta", attrs={"name": "description"})

    if meta and meta.get("content"):
        return clean_text(meta["content"])

    return ""


def extract_title(soup: BeautifulSoup) -> str:
    """
    Extracts page title.
    """

    if soup.title and soup.title.string:
        return clean_text(soup.title.string)

    return ""


def extract_headings(soup: BeautifulSoup) -> list:
    """
    Extracts important headings from homepage.
    """

    headings = []

    for tag in ["h1", "h2", "h3"]:
        for item in soup.find_all(tag):

            text = clean_text(item.get_text())

            if text and len(text) > 3:
                headings.append(text)

    return headings[:15]


def extract_visible_text(soup: BeautifulSoup) -> str:
    """
    Extracts visible text from page.
    """

    for script in soup(["script", "style", "noscript"]):
        script.extract()

    text = soup.get_text(separator=" ")

    return clean_text(text)[:5000]


def detect_social_links(soup: BeautifulSoup) -> dict:
    """
    Finds social media links.
    """

    social_links = {
        "linkedin": None,
        "twitter": None,
        "facebook": None,
        "instagram": None
    }

    for link in soup.find_all("a", href=True):

        href = link["href"].lower()

        if "linkedin.com" in href:
            social_links["linkedin"] = href

        elif "twitter.com" in href or "x.com" in href:
            social_links["twitter"] = href

        elif "facebook.com" in href:
            social_links["facebook"] = href

        elif "instagram.com" in href:
            social_links["instagram"] = href

    return social_links


def scrape_company_info(lead_data: dict) -> dict:
    """
    Main research pipeline.
    Uses lead form data to scrape company information.
    """

    website = normalize_url(lead_data["company_website"])

    html = fetch_page(website)

    if not html:
        return {
            "success": False,
            "error": "Failed to fetch company website."
        }

    soup = BeautifulSoup(html, "html.parser")

    result = {
        "success": True,

        # Original Lead Data
        "lead_info": {
            "full_name": lead_data.get("full_name"),
            "work_email": lead_data.get("work_email"),
            "company_name": lead_data.get("company_name"),
            "industry": lead_data.get("industry"),
            "company_size": lead_data.get("company_size"),
            "current_challenge": lead_data.get("current_challenge"),
            "improvement_goal": lead_data.get("improvement_goal")
        },

        # Scraped Company Intelligence
        "company_research": {
            "website": website,
            "page_title": extract_title(soup),
            "meta_description": extract_meta_description(soup),
            "headings": extract_headings(soup),
            "social_links": detect_social_links(soup),
            "homepage_text_preview": extract_visible_text(soup)
        }
    }

    return result


# -----------------------------
# Example Usage
# -----------------------------
if __name__ == "__main__":

    sample_lead = {
        "full_name": "John Doe",
        "work_email": "john@company.com",
        "company_name": "OpenAI",
        "company_website": "https://openai.com",
        "industry": "AI",
        "company_size": "1000+",
        "current_challenge": (
            "We want to improve customer support automation."
        ),
        "improvement_goal": (
            "We want faster response times using AI systems."
        )
    }

    research_result = scrape_company_info(sample_lead)

    print(json.dumps(research_result, indent=4))