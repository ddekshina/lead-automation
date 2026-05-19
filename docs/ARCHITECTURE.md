# Architecture & engineering decisions

This document explains how the lead automation prototype is structured, why certain choices were made, and how the system behaves when things go wrong.

## Goals

- End-to-end flow: validate → enrich → generate report → email → optional Sheets/Drive.
- **Honest personalization**: use form data + public scrape + AI synthesis with guardrails against invented facts.
- **Practical operation**: runs locally with minimal moving parts; clear extension path for production.

## High-level architecture

```
Client (browser or API)
        │
        ▼
POST /api/submit-lead  (Pydantic validation first)
        │
        ├── default: HTTP 202 + BackgroundTasks (non-blocking UX)
        └── optional ?sync=true: full pipeline in request (for scripts / debugging)
        │
        ▼
Pipeline (app/routes/main.py::_run_pipeline)
  1. validate_lead_input (redundant checks + URL rules)
  2. scrape_company_data (HTTP fetch + BeautifulSoup; always returns a dict)
  3. generate_audit_report (Gemini; retries + model fallback)
  4. ReportBuilder → HTML (Jinja2 + Markdown) + PDF (ReportLab)
  5. send_report_email (SMTP; soft-fail if not configured)
  6. log_lead_to_sheet / archive_pdf_to_drive (optional; soft-fail)
```

## Key modules

| Module | Responsibility |
|--------|----------------|
| `app/bootstrap.py` | SSL: `truststore` + `certifi` fallbacks before any HTTPS. |
| `app/schemas/lead_schema.py` | Request shape; normalizes bare domains to `https://`. |
| `app/services/validator.py` | Extra validation for dict-based reuse. |
| `app/services/scraper.py` | Single-page fetch; extracts title, meta, headings, text preview, social hints. |
| `app/services/prompts.py` | Single source of truth for report structure and tone. |
| `app/services/ai_generator.py` | Gemini client; model list + retries on 429/503. |
| `app/services/report_builder.py` | Markdown → HTML template; Markdown → PDF (subset). |
| `app/services/email_sender.py` | SMTP multipart with HTML + attachments. |
| `app/services/google_integrations.py` | Service account (Sheets); OAuth user token (Drive). |

## Asynchronous submission (UX)

**Problem**: Running scrape + LLM + PDF + email inside the HTTP request blocks the client for tens of seconds.

**Decision**: Default path returns **HTTP 202 Accepted** immediately after validation and schedules `BackgroundTasks` to run the pipeline. The landing page shows a clear “check your inbox” message.

**Tradeoff**: The HTTP response no longer carries pipeline success/failure. Failures are logged server-side; the prospect still expects an email — so production should add retries, dead-letter logging, or admin alerts (out of prototype scope).

**Escape hatch**: `POST /api/submit-lead?sync=true` runs the full pipeline inline and returns **200** with paths and flags (useful for `curl`, tests, or internal tools).

## Real-world failure handling

| Scenario | Behavior |
|----------|----------|
| Invalid body / missing fields | **422** before background work; user sees validation errors. |
| Scrape timeout / block / SSL | `scrape_status` ≠ success; **fallback** text from industry + company name; pipeline continues. |
| Gemini rate limit / outage | Retries + alternate models; on total failure, background task logs error (sync mode returns **502**). |
| SMTP missing or wrong | Report files still written; `email_sent: false` and `email_note` in sync response; background path logs warning. |
| Sheets/Drive misconfigured | Logged warning; pipeline continues. |
| Service account Drive upload | Not supported for consumer Gmail storage; OAuth token used instead (see README). |

## Report quality strategy

Reports are **prompt-driven**. The template in `app/services/prompts.py` encodes:

- Explicit **data validation** when form firmographics disagree with public signals.
- **Stakeholder uncertainty** and a suggested discovery step for KPIs.
- **CRM-oriented** integration language without asserting unknown tools.
- **30/60/90** phasing and KPIs including lead decay / speed-to-touch.
- **Outreach** aligned to scraped vocabulary, with a low-friction CTA.

We deliberately avoid fetching proprietary databases in the prototype; depth is bounded by scrape quality and model reasoning.

## Security & secrets (prototype)

- No API authentication on `/api/submit-lead` (acceptable for a demo; **not** for public production).
- `.env` holds secrets; `credentials/` and OAuth token files are gitignored.
- Do not commit API keys or Gmail app passwords.

## Limitations (explicit)

- **No job queue**: `BackgroundTasks` is in-process; if the process dies mid-job, the email may never send. Production would use Celery/RQ/SQS + worker.
- **No idempotency**: duplicate submissions generate duplicate reports and emails.
- **Scraper**: No JS rendering; anti-bot sites may return empty content.
- **PDF**: Markdown subset in ReportLab; complex tables may render differently than HTML.
- **PII**: Logs may contain company names and emails at INFO level — tune logging for compliance.

## Extension ideas

- Webhook or polling job status keyed by `submission_id`.
- CRM webhook outbound (Salesforce, HubSpot) after successful email.
- Rate limiting and CAPTCHA on the public form.

## Appendix: Google APIs (condensed)

**Sheets:** Service account JSON → share the spreadsheet with the service account email → `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SHEET_ID`.

**Drive (personal Gmail):** Service accounts have no consumer Drive quota. Use OAuth:

1. Enable Drive API; create OAuth **Desktop** client → `google_oauth_client.json`.
2. Set `GOOGLE_DRIVE_FOLDER_ID` to a folder you own.
3. Run `python scripts/authorize_google_drive.py` → `google_drive_token.json`.
4. Set `GOOGLE_DRIVE_TOKEN_JSON=google_drive_token.json` in `.env`.

Re-run the authorize script if you change OAuth scopes in code.
