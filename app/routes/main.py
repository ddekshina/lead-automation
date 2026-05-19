import logging
import re
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse

from app.schemas.lead_schema import LeadRequest
from app.services.validator import validate_lead_input
from app.services.scraper import scrape_company_data
from app.services.ai_generator import generate_audit_report
from app.services.report_builder import ReportBuilder
from app.services.email_sender import send_report_email
from app.services.google_integrations import log_lead_to_sheet, archive_pdf_to_drive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Lead Automation"])


def _slugify(text: str) -> str:
    """Converts a company name to a safe filename slug."""
    return re.sub(r"[^\w]", "_", text.strip().lower())


def _run_pipeline(lead_data: dict) -> dict:
    """
    Executes the full lead automation pipeline:
      1. Validate
      2. Scrape / Enrich
      3. AI Report Generation
      4. HTML + PDF Report Building
      5. Email Delivery
      6. (Bonus) Google Sheets logging + Drive archiving

    Returns a summary dict.
    """
    company_name = lead_data["company_name"]
    slug = _slugify(company_name)

    # 1. Validate
    validation = validate_lead_input(lead_data)
    if not validation["valid"]:
        raise ValueError(validation["message"])

    # 2. Scrape + Enrich
    logger.info(f"[Pipeline] Scraping: {lead_data.get('company_website')}")
    enriched = scrape_company_data(lead_data)

    scrape_status = enriched["company_research"].get("scrape_status", "failed")
    if scrape_status != "success":
        logger.warning(
            f"[Pipeline] Website scraping status '{scrape_status}' for {company_name}. "
            "Proceeding with fallback context."
        )

    # 3. AI Analysis
    logger.info(f"[Pipeline] Generating AI report for {company_name}")
    try:
        markdown_report = generate_audit_report(enriched)
    except (EnvironmentError, RuntimeError) as e:
        logger.error(f"[Pipeline] AI generation failed: {e}")
        raise

    # 4. Build Reports
    builder = ReportBuilder(company_name)

    html_content = builder.build_html_report(markdown_report)
    html_path = builder.save_html_report(
        html_content,
        filename=f"{slug}_report.html"
    )

    pdf_bytes = builder.build_pdf_report(markdown_report)
    pdf_path = builder.save_pdf_report(
        pdf_bytes,
        filename=f"{slug}_report.pdf"
    ) if pdf_bytes else None

    # 5. Send Email
    logger.info(f"[Pipeline] Sending email to {lead_data['work_email']}")
    email_result = send_report_email(
        recipient_email=lead_data["work_email"],
        recipient_name=lead_data["full_name"],
        company_name=company_name,
        html_report_path=html_path,
        pdf_report_path=pdf_path,
    )

    result = {
        "success": True,
        "company": company_name,
        "scrape_status": scrape_status,
        "html_report": str(html_path),
        "pdf_report": str(pdf_path) if pdf_path else None,
        "email_sent": email_result.get("success", False),
        "email_note": email_result.get("error") if not email_result.get("success") else None,
        "sheets_logged": False,
        "drive_link": None,
    }

    # 6. BONUS — Google Sheets logging
    sheets_ok = log_lead_to_sheet(lead_data, result)
    result["sheets_logged"] = sheets_ok

    # 7. BONUS — Google Drive PDF archiving
    if pdf_path:
        drive_link = archive_pdf_to_drive(pdf_path, company_name)
        result["drive_link"] = drive_link

    return result


def _run_pipeline_safe(lead_data: dict, submission_id: str) -> None:
    """Background entrypoint: log failures instead of losing them silently."""
    company = lead_data.get("company_name", "?")
    logger.info("[Pipeline] Background job %s started for %s", submission_id, company)
    try:
        _run_pipeline(lead_data)
        logger.info("[Pipeline] Background job %s completed for %s", submission_id, company)
    except ValueError as e:
        logger.error("[Pipeline] Job %s validation error: %s", submission_id, e)
    except EnvironmentError as e:
        logger.error("[Pipeline] Job %s config error: %s", submission_id, e)
    except RuntimeError as e:
        logger.error("[Pipeline] Job %s runtime error: %s", submission_id, e)
    except Exception:
        logger.exception("[Pipeline] Job %s failed for %s", submission_id, company)


@router.post("/submit-lead", summary="Submit a lead and trigger the full automation pipeline")
async def submit_lead(
    payload: LeadRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(
        False,
        description=(
            "If false (default), return 202 immediately and process in the background. "
            "If true, run the full pipeline inline and return 200 with detailed results."
        ),
    ),
):
    """
    Main lead intake endpoint.

    Default (**sync=false**): HTTP **202 Accepted** right after validation; scrape, AI,
    PDF, email, and Google integrations run in a background task so the client is not blocked.

    **sync=true**: full pipeline in the request/response (for scripts and debugging).
    """
    lead_data = payload.model_dump()
    # Pydantic EmailStr serialises to an EmailStr object; force to plain str
    lead_data["work_email"] = str(lead_data["work_email"])

    if not sync:
        submission_id = str(uuid.uuid4())
        background_tasks.add_task(_run_pipeline_safe, lead_data, submission_id)
        return JSONResponse(
            status_code=202,
            content={
                "accepted": True,
                "async_processing": True,
                "submission_id": submission_id,
                "company": lead_data["company_name"],
                "message": (
                    "Your request was received. We are generating your personalized report and "
                    "will email it to the address you provided shortly — usually within a few minutes."
                ),
                "note": (
                    "Check spam or promotions folders if you do not see the message. "
                    "Developers can call the same endpoint with ?sync=true for a blocking response "
                    "that includes file paths and delivery flags."
                ),
            },
        )

    try:
        result = _run_pipeline(lead_data)
        result["async_processing"] = False
        return JSONResponse(content=result, status_code=200)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    except Exception as e:
        logger.exception(f"Unexpected pipeline error: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again.",
        )


@router.get("/health", summary="Health check")
async def health():
    return {"status": "ok", "service": "lead-automation"}
