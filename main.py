import logging

from dotenv import load_dotenv

# Must run before any outbound HTTPS (scraper, Gemini, Google APIs).
from app.bootstrap import configure_ssl

configure_ssl()
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.routes.main import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="SimplifIQ Lead Automation API",
    description="Automated lead enrichment, AI report generation, and email delivery.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing():
    """Landing page with lead intake form."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SimplifIQ Lead Automation</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: Inter, system-ui, sans-serif;
                background: linear-gradient(135deg, #0f172a, #1e293b);
                color: #e2e8f0;
                min-height: 100vh;
                padding: 40px 20px;
            }
            .container { max-width: 760px; margin: 0 auto; }
            h1 { font-size: 2.2rem; color: #a5b4fc; margin-bottom: .5rem; }
            .subtitle { color: #94a3b8; margin-bottom: 2rem; }
            .links { margin-bottom: 2rem; }
            .links a {
                color: #818cf8; text-decoration: none; margin-right: 12px;
                border: 1px solid #334155; padding: 8px 16px; border-radius: 8px;
            }
            .info {
                background: #1e293b; border: 1px solid #334155; border-radius: 12px;
                padding: 14px 16px; margin-bottom: 1.5rem; font-size: 14px; color: #94a3b8;
                line-height: 1.55;
            }
            form {
                background: #111827; border: 1px solid #334155;
                border-radius: 16px; padding: 28px;
            }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
            label { display: block; font-size: 13px; color: #94a3b8; margin-bottom: 6px; }
            input, select, textarea {
                width: 100%; padding: 10px 12px; border-radius: 8px;
                border: 1px solid #334155; background: #0f172a; color: #e2e8f0;
                font-size: 14px;
            }
            textarea { min-height: 90px; resize: vertical; }
            .field { margin-bottom: 16px; }
            .full { grid-column: 1 / -1; }
            button {
                background: #6366f1; color: white; border: none; border-radius: 8px;
                padding: 12px 20px; font-size: 15px; font-weight: 600; cursor: pointer;
            }
            button:disabled { opacity: .6; cursor: not-allowed; }
            #status {
                margin-top: 16px; padding: 12px 14px; border-radius: 8px;
                display: none; font-size: 14px; line-height: 1.5;
            }
            .ok { background: #064e3b; color: #a7f3d0; border: 1px solid #059669; }
            .pending { background: #1e3a5f; color: #bfdbfe; border: 1px solid #3b82f6; }
            .err { background: #450a0a; color: #fecaca; border: 1px solid #dc2626; }
            @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>SimplifIQ Lead Automation</h1>
            <p class="subtitle">Submit a lead — you get an instant confirmation while we generate your report and email it.</p>
            <div class="links">
                <a href="/docs">API Docs</a>
                <a href="/api/health">Health Check</a>
            </div>

            <form id="leadForm">
                <div class="grid">
                    <div class="field">
                        <label for="full_name">Full Name</label>
                        <input id="full_name" name="full_name" required placeholder="Jane Smith">
                    </div>
                    <div class="field">
                        <label for="work_email">Work Email</label>
                        <input id="work_email" name="work_email" type="email" required placeholder="jane@company.com">
                    </div>
                    <div class="field">
                        <label for="company_name">Company Name</label>
                        <input id="company_name" name="company_name" required placeholder="Acme Corp">
                    </div>
                    <div class="field">
                        <label for="company_website">Company Website</label>
                        <input id="company_website" name="company_website" required placeholder="https://acme.com">
                    </div>
                    <div class="field">
                        <label for="industry">Industry</label>
                        <input id="industry" name="industry" required placeholder="SaaS">
                    </div>
                    <div class="field">
                        <label for="company_size">Company Size</label>
                        <select id="company_size" name="company_size" required>
                            <option value="1-10">1-10</option>
                            <option value="11-50">11-50</option>
                            <option value="51-200" selected>51-200</option>
                            <option value="201-1000">201-1000</option>
                            <option value="1000+">1000+</option>
                        </select>
                    </div>
                    <div class="field full">
                        <label for="current_challenge">Current Challenge</label>
                        <textarea id="current_challenge" name="current_challenge" required
                            placeholder="Describe the main operational or growth challenge."></textarea>
                    </div>
                    <div class="field full">
                        <label for="improvement_goal">Improvement Goal</label>
                        <textarea id="improvement_goal" name="improvement_goal" required
                            placeholder="What outcome are you trying to achieve?"></textarea>
                    </div>
                </div>
                <button type="submit" id="submitBtn">Submit lead</button>
                <div id="status"></div>
            </form>
        </div>

        <script>
            const form = document.getElementById("leadForm");
            const status = document.getElementById("status");
            const btn = document.getElementById("submitBtn");

            form.addEventListener("submit", async (e) => {
                e.preventDefault();
                btn.disabled = true;
                status.style.display = "none";

                const payload = Object.fromEntries(new FormData(form).entries());

                try {
                    const res = await fetch("/api/submit-lead", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload),
                    });
                    let data = {};
                    try { data = await res.json(); } catch (_) {}

                    status.style.display = "block";

                    if (res.status === 202 && data.accepted) {
                        status.className = "pending";
                        status.innerHTML =
                            "<strong>Request received.</strong><br>" +
                            (data.message || "We will email your report shortly.") +
                            (data.submission_id
                                ? "<br><span style=opacity:.85>Reference: " + data.submission_id + "</span>"
                                : "") +
                            (data.note ? "<br><br><small>" + data.note + "</small>" : "");
                        form.reset();
                    } else if (res.ok && data.company) {
                        status.className = "ok";
                        status.innerHTML =
                            "<strong>Pipeline complete</strong> (sync mode).<br>" +
                            "Company: " + data.company + "<br>" +
                            "Scrape: " + data.scrape_status + " | Email sent: " + data.email_sent +
                            (data.pdf_report ? "<br>PDF: " + data.pdf_report : "");
                    } else {
                        status.className = "err";
                        const d = data.detail;
                        status.textContent =
                            typeof d === "string"
                                ? d
                                : Array.isArray(d)
                                    ? d.map((x) => x.msg || JSON.stringify(x)).join("; ")
                                    : "Submission failed.";
                    }
                } catch (err) {
                    status.style.display = "block";
                    status.className = "err";
                    status.textContent = "Network error: " + err.message;
                } finally {
                    btn.disabled = false;
                }
            });
        </script>
    </body>
    </html>
    """


@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok", "service": "simplify-lead-automation"}
