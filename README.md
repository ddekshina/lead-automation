# SimplifIQ Lead Automation

Automated lead intake pipeline that validates form submissions, enriches company data via web scraping, generates a personalized AI audit report (HTML + PDF), emails it to the prospect, and optionally logs leads to Google Sheets and archives PDFs to Google Drive.

## Features

- **Lead validation** — Pydantic schema + server-side checks for required fields, email format, URL, and company size
- **Company enrichment** — Scrapes public website metadata, headings, and homepage text with graceful fallbacks
- **AI report generation** — Gemini-powered personalized business insight report in markdown
- **Report delivery** — Styled HTML template + PDF export via ReportLab
- **Email automation** — SMTP delivery with HTML + PDF attachments
- **Bonus: Google Sheets** — Append lead rows to a live tracker
- **Bonus: Google Drive** — Archive generated PDFs to a folder

## Architecture

```
Lead Form (POST /api/submit-lead)
        │
        ▼
   Validate Input
        │
        ▼
   Scrape Website ──► fallback context if scrape fails
        │
        ▼
   Gemini AI Report
        │
        ├──► HTML Report (Jinja2 template)
        └──► PDF Report (ReportLab)
        │
        ▼
   Send Email (SMTP)
        │
        ├──► Google Sheets log (optional)
        └──► Google Drive archive (optional)
```

## Quick Start

### 1. Clone and install

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

**Windows SSL error during `pip install`?** Use:

```bash
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

The app uses `truststore` so HTTPS works for scraping and Gemini on Windows. Always run the server with the **venv activated**:

```bash
venv\Scripts\activate
python -m uvicorn main:app --reload
```

### 2. Configure environment

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Edit `.env` and set at minimum:

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `SMTP_HOST` | For email | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | For email | e.g. `587` |
| `SMTP_USER` | For email | SMTP username |
| `SMTP_PASS` | For email | App password (Gmail) |
| `SENDER_EMAIL` | For email | From address |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Bonus | Path to service account JSON |
| `GOOGLE_SHEET_ID` | Bonus | Spreadsheet ID |
| `GOOGLE_DRIVE_FOLDER_ID` | Bonus | Drive folder ID |

**Minimum to run:** `GEMINI_API_KEY` + SMTP vars. Google vars are optional (Sheets/Drive bonus only).

### 3. Run the server

```bash
python -m uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) for the lead form, or [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the API.

### 4. Submit a lead

**Via the web form:** Fill out the form at `/`

**Via API:**

```bash
curl -X POST http://127.0.0.1:8000/api/submit-lead \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Jane Smith",
    "work_email": "jane@example.com",
    "company_name": "Stripe",
    "company_website": "https://stripe.com",
    "industry": "Fintech",
    "company_size": "1000+",
    "current_challenge": "We need to improve enterprise lead qualification.",
    "improvement_goal": "Automate personalized outreach and reduce manual research."
  }'
```

Generated reports are saved to `generated_reports/`.

## Assumptions & Tradeoffs

- **Public data only** — The AI report uses form inputs + publicly scraped website content. No internal CRM or proprietary data sources.
- **Scraping limits** — Some sites block bots or require JavaScript. The pipeline continues with fallback context when scraping fails.
- **Synchronous pipeline** — The API runs the full workflow inline for simplicity. For high volume, switch to background tasks in `app/routes/main.py`.
- **Windows SSL** — `truststore` is used to trust the OS certificate store, fixing common HTTPS failures on Windows.
- **Email optional in dev** — If SMTP is not configured, reports are still generated locally; email is skipped with a clear status flag.

## Google Setup (Bonus)

### Google Sheets (service account)

1. Create a Google Cloud project and enable **Google Sheets API**
2. Create a **service account** and download the JSON key
3. Share your Google Sheet with the service account email (Editor access)
4. Set `GOOGLE_SERVICE_ACCOUNT_JSON` and `GOOGLE_SHEET_ID` in `.env`

### Google Drive (personal Gmail)

Service accounts **cannot** store files on personal Gmail Drive (no storage quota). Use OAuth:

1. Enable **Google Drive API** in the same Cloud project
2. Create an **OAuth client ID** (Desktop app) → download as `google_oauth_client.json` in the project root
3. Create a folder in **your** Gmail Drive → copy its ID from the URL
4. Run:

```bash
pip install google-auth-oauthlib
python scripts/authorize_google_drive.py
```

5. Add to `.env`:

```env
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
GOOGLE_DRIVE_TOKEN_JSON=google_drive_token.json
```

PDFs upload into your folder using your account's storage.

## Project Structure

```
lead-automation/
├── main.py                      # FastAPI entry point
├── app/
│   ├── bootstrap.py             # SSL / truststore setup
│   ├── routes/main.py           # API endpoints + pipeline orchestration
│   ├── schemas/lead_schema.py   # Pydantic request model
│   ├── services/
│   │   ├── validator.py         # Input validation
│   │   ├── scraper.py           # Website enrichment
│   │   ├── ai_generator.py      # Gemini report generation
│   │   ├── prompts.py           # AI prompt template
│   │   ├── report_builder.py    # HTML + PDF rendering
│   │   ├── email_sender.py      # SMTP delivery
│   │   └── google_integrations.py  # Sheets + Drive (bonus)
│   └── templates/report_template.html
├── generated_reports/           # Output HTML/PDF files
├── requirements.txt
└── .env.example
```

## Limitations

- No authentication on the API (prototype scope)
- No persistent database — leads are logged to Google Sheets if configured
- PDF styling is functional but simpler than the HTML template
- AI quality depends on scrape success and Gemini availability
