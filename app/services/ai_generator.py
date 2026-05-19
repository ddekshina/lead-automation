import logging
import os
import time

from google import genai

from app.services.prompts import AUDIT_REPORT_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
]

RETRYABLE_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "timeout")


def _model_candidates() -> list[str]:
    """Build ordered model list from env override + defaults."""
    preferred = os.getenv("GEMINI_MODEL", "").strip()
    models: list[str] = []
    if preferred:
        models.append(preferred)
    for model in DEFAULT_MODELS:
        if model not in models:
            models.append(model)
    return models


def _is_retryable(error: Exception) -> bool:
    message = str(error).upper()
    return any(marker in message for marker in RETRYABLE_MARKERS)


def _generate_with_model(client: genai.Client, model: str, prompt: str) -> str:
    response = client.models.generate_content(model=model, contents=prompt)
    text = getattr(response, "text", None)
    if not text or not text.strip():
        raise RuntimeError(f"Gemini model '{model}' returned an empty response.")
    return text.strip()


def generate_audit_report(context: dict) -> str:
    """
    Generates an AI-powered business insight report using Gemini (Google).

    Args:
        context: dict with keys 'lead_info' and 'company_research'

    Returns:
        Markdown-formatted report string.

    Raises:
        EnvironmentError: if GEMINI_API_KEY is not set.
        RuntimeError: if the AI call fails across all models.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Please add it to your .env file."
        )

    lead = context["lead_info"]
    research = context["company_research"]

    headings_text = "\n".join(
        f"- {h}" for h in research.get("headings", [])
    ) or "No headings extracted."

    homepage_text = research.get("homepage_text_preview", "")[:2000] or "Not available."

    final_prompt = AUDIT_REPORT_PROMPT.format(
        full_name=lead["full_name"],
        work_email=lead["work_email"],
        company_name=lead["company_name"],
        industry=lead["industry"],
        company_size=lead["company_size"],
        current_challenge=lead["current_challenge"],
        improvement_goal=lead["improvement_goal"],
        website=research.get("website", ""),
        meta_description=research.get("meta_description", "Not available."),
        headings=headings_text,
        homepage_text=homepage_text,
    )

    client = genai.Client(api_key=api_key)
    errors: list[str] = []

    for model in _model_candidates():
        for attempt in range(1, 4):
            try:
                logger.info(
                    "Generating report with model=%s (attempt %s/3)",
                    model,
                    attempt,
                )
                return _generate_with_model(client, model, final_prompt)
            except Exception as e:
                msg = f"{model} attempt {attempt}: {e}"
                logger.warning(msg)
                if attempt < 3 and _is_retryable(e):
                    time.sleep(attempt * 2)
                    continue
                errors.append(msg)
                break

    raise RuntimeError(
        "Gemini API call failed after trying all models. "
        + " | ".join(errors[-3:])
    )


if __name__ == "__main__":
    from dotenv import load_dotenv

    from app.bootstrap import configure_ssl

    configure_ssl()
    load_dotenv()

    sample_context = {
        "lead_info": {
            "full_name": "Jane Smith",
            "work_email": "jane@acme.com",
            "company_name": "Acme Corp",
            "industry": "SaaS",
            "company_size": "51-200",
            "current_challenge": "We spend too much time manually qualifying leads.",
            "improvement_goal": "We want to automate lead research and follow-up emails.",
        },
        "company_research": {
            "website": "https://acme.com",
            "meta_description": "Acme Corp builds B2B SaaS tools for modern teams.",
            "headings": [
                "Automate your workflows",
                "Trusted by 500+ teams",
                "Get started free",
            ],
            "homepage_text_preview": "Acme Corp helps teams automate repetitive tasks...",
        },
    }

    report = generate_audit_report(sample_context)
    print(report)
