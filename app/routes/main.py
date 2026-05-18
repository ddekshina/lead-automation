from fastapi import APIRouter, HTTPException

from app.schemas.lead_schema import LeadRequest

from app.services.validator import validate_company_input
from app.services.scraper import scrape_company_data
from app.services.ai_generator import generate_company_analysis
from app.services.report_builder import ReportBuilder


router = APIRouter(
    prefix="/api",
    tags=["Lead Automation"]
)


@router.post("/generate-report")
async def generate_report(payload: LeadRequest):

    company_name = payload.company_name

    # -----------------------------
    # 1. VALIDATE
    # -----------------------------
    validation = validate_company_input(company_name)

    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=validation["message"]
        )

    # -----------------------------
    # 2. SCRAPE
    # -----------------------------
    scraped_data = scrape_company_data(company_name)

    # -----------------------------
    # 3. AI ANALYSIS
    # -----------------------------
    ai_analysis = generate_company_analysis(scraped_data)

    # -----------------------------
    # 4. BUILD REPORT
    # -----------------------------
    builder = ReportBuilder(company_name)

    html = builder.build_html_report(ai_analysis)

    output_path = builder.save_html_report(
        html_content=html,
        filename=f"{company_name.lower()}_report.html"
    )

    return {
        "success": True,
        "company": company_name,
        "report_path": str(output_path)
    }