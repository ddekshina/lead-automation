# ai_generator.py

from google import genai
from prompts import AUDIT_REPORT_PROMPT


def generate_audit_report(context: dict, api_key: str) -> str:
    """
    Generates AI-powered business insight report using Gemini.
    """

    # Create Gemini client
    client = genai.Client(api_key=api_key)

    # Format headings
    headings_text = "\n".join(
        f"- {heading}"
        for heading in context["company_research"]["headings"]
    )

    # Build final prompt
    final_prompt = AUDIT_REPORT_PROMPT.format(
        full_name=context["lead_info"]["full_name"],
        work_email=context["lead_info"]["work_email"],
        company_name=context["lead_info"]["company_name"],
        industry=context["lead_info"]["industry"],
        company_size=context["lead_info"]["company_size"],
        current_challenge=context["lead_info"]["current_challenge"],
        improvement_goal=context["lead_info"]["improvement_goal"],
        website=context["company_research"]["website"],
        meta_description=context["company_research"]["meta_description"],
        headings=headings_text
    )

    # Generate response
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=final_prompt
    )

    return response.text


# ------------------------------------------------
# Example Usage
# ------------------------------------------------
if __name__ == "__main__":

    GEMINI_API_KEY = "..."

    sample_context = {
        "lead_info": {
            "full_name": "John Doe",
            "work_email": "john@company.com",
            "company_name": "OpenAI",
            "industry": "AI",
            "company_size": "1000+",
            "current_challenge": (
                "We want to improve customer support automation."
            ),
            "improvement_goal": (
                "We want faster response times using AI systems."
            )
        },

        "company_research": {
            "website": "https://openai.com",

            "meta_description": (
                "We believe our research will eventually lead "
                "to artificial general intelligence."
            ),

            "headings": [
                "Recent news",
                "Stories",
                "Latest research",
                "OpenAI for business",
                "Get started with ChatGPT"
            ]
        }
    }

    report = generate_audit_report(
        context=sample_context,
        api_key=GEMINI_API_KEY
    )

    print("\n")
    print("=" * 80)
    print("GENERATED REPORT")
    print("=" * 80)
    print("\n")
    print(report)