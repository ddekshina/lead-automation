import re
from urllib.parse import urlparse


ALLOWED_COMPANY_SIZES = [
    "1-10",
    "11-50",
    "51-200",
    "201-1000",
    "1000+"
]


def is_valid_email(email: str) -> bool:
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)

        return all([
            parsed.scheme in ["http", "https"],
            parsed.netloc
        ])

    except Exception:
        return False


def validate_lead_form(data: dict) -> dict:
    errors = {}

    required_fields = [
        "full_name",
        "work_email",
        "company_name",
        "company_website",
        "industry",
        "company_size",
        "current_challenge",
        "improvement_goal"
    ]

    # Check missing fields
    for field in required_fields:
        if field not in data or not str(data[field]).strip():
            errors[field] = "This field is required."

    if errors:
        return {
            "success": False,
            "errors": errors
        }

    # Full Name validation
    if len(data["full_name"].strip()) < 2:
        errors["full_name"] = "Full name must be at least 2 characters."

    # Email validation
    if not is_valid_email(data["work_email"]):
        errors["work_email"] = "Invalid email format."

    # Website validation
    if not is_valid_url(data["company_website"]):
        errors["company_website"] = "Invalid website URL."

    # Industry validation
    if len(data["industry"].strip()) < 2:
        errors["industry"] = "Industry name is too short."

    # Company Size validation
    if data["company_size"] not in ALLOWED_COMPANY_SIZES:
        errors["company_size"] = (
            f"Company size must be one of: {ALLOWED_COMPANY_SIZES}"
        )

    # Challenge validation
    if len(data["current_challenge"].strip()) < 10:
        errors["current_challenge"] = (
            "Please provide more details about the current challenge."
        )

    # Improvement goal validation
    if len(data["improvement_goal"].strip()) < 10:
        errors["improvement_goal"] = (
            "Please provide more details about the improvement goal."
        )

    if errors:
        return {
            "success": False,
            "errors": errors
        }

    return {
        "success": True,
        "message": "Validation passed successfully."
    }


# Example Usage
if __name__ == "__main__":

    sample_payload = {
        "full_name": "John Doe",
        "work_email": "john@company.com",
        "company_name": "Acme Inc",
        "company_website": "https://acme.com",
        "industry": "SaaS",
        "company_size": "11-50",
        "current_challenge": "We spend too much time manually qualifying leads.",
        "improvement_goal": "We want to automate lead research and follow-ups."
    }

    result = validate_lead_form(sample_payload)

    print(result)