from pydantic import BaseModel, EmailStr, field_validator
from urllib.parse import urlparse


class LeadRequest(BaseModel):
    full_name: str
    work_email: EmailStr
    company_name: str
    company_website: str
    industry: str
    company_size: str
    current_challenge: str
    improvement_goal: str

    @field_validator("full_name")
    @classmethod
    def name_must_be_valid(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return v.strip()

    @field_validator("company_name")
    @classmethod
    def company_name_must_be_valid(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Company name must be at least 2 characters.")
        return v.strip()

    @field_validator("industry")
    @classmethod
    def industry_must_be_valid(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Industry must be at least 2 characters.")
        return v.strip()

    @field_validator("company_size")
    @classmethod
    def size_must_be_valid(cls, v: str) -> str:
        allowed = ["1-10", "11-50", "51-200", "201-1000", "1000+"]
        if v not in allowed:
            raise ValueError(f"Company size must be one of: {allowed}")
        return v

    @field_validator("current_challenge")
    @classmethod
    def challenge_must_be_detailed(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Please provide more detail about the current challenge.")
        return v.strip()

    @field_validator("improvement_goal")
    @classmethod
    def goal_must_be_detailed(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Please provide more detail about the improvement goal.")
        return v.strip()

    @field_validator("company_website")
    @classmethod
    def website_must_be_valid(cls, v: str) -> str:
        url = v.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                "Invalid website URL. Use a full URL like https://example.com"
            )
        return url
