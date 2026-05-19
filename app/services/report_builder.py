from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import markdown

if TYPE_CHECKING:
    from reportlab.lib.styles import ParagraphStyle

logger = logging.getLogger(__name__)

# PDF support via reportlab (pure-python, no system dependencies)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        HRFlowable, Table, TableStyle
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning(
        "reportlab not installed — PDF generation disabled. "
        "Run: pip install reportlab"
    )

# Jinja2 for HTML templating
try:
    from jinja2 import Environment, FileSystemLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    logger.warning("jinja2 not installed — HTML templating disabled.")


def _inline_bold(text: str) -> str:
    """Convert **bold** markdown to <b>bold</b> for ReportLab."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def _reportlab_safe_text(text: str) -> str:
    """
    ReportLab Paragraph uses a strict mini-HTML parser. LLM output often includes
    <br> chains or bare '&' which trigger ValueError / paraparser errors.
    """
    if not text:
        return ""
    s = text
    # <br> inside "one line" bullets breaks the parser ("No content allowed in br tag")
    s = re.sub(r"<br\s*/?>", " — ", s, flags=re.IGNORECASE)
    # Strip other common HTML wrappers the model might emit
    s = re.sub(
        r"</?(?:p|div|span|li|ul|ol|a|h[1-6])\b[^>]*>",
        " ",
        s,
        flags=re.IGNORECASE,
    )
    s = _inline_bold(s)
    # Keep only <b>, <i>, <u> tags we trust; escape anything else angle-bracketed
    def _escape_unknown_tag(m: re.Match) -> str:
        tag = m.group(0)
        if re.match(r"</?(?:b|i|u)(?:\s[^>]*)?>", tag, re.IGNORECASE):
            return tag
        return tag.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    s = re.sub(r"<[^>]+>", _escape_unknown_tag, s)
    # Bare ampersands (e.g. "R&D") must be entities for the XML-style parser
    s = re.sub(
        r"&(?!#?[0-9a-zA-Z]+;|(?:amp|lt|gt|quot|apos|nbsp);)",
        "&amp;",
        s,
    )
    return s


class ReportBuilder:

    def __init__(self, company_name: str):
        self.company_name = company_name
        # FIX: correct path — templates/ lives inside app/, not app/services/
        template_dir = Path(__file__).resolve().parent.parent / "templates"
        if JINJA2_AVAILABLE:
            self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------

    def build_html_report(self, markdown_content: str) -> str:
        """Converts markdown AI output into a styled HTML report."""
        html_body = markdown.markdown(
            markdown_content,
            extensions=["tables", "fenced_code"]
        )
        current_date = datetime.now().strftime("%B %d, %Y")

        if JINJA2_AVAILABLE:
            template = self.env.get_template("report_template.html")
            return template.render(
                company_name=self.company_name,
                current_date=current_date,
                html_body=html_body
            )

        # Fallback: minimal HTML wrapper if Jinja2 not available
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{self.company_name} — Business Insight Report</title>
</head><body>
<h1>{self.company_name}</h1>
<p><em>{current_date}</em></p>
{html_body}
</body></html>"""

    def save_html_report(self, html_content: str, filename: str) -> Path:
        """Saves HTML report to generated_reports/. Returns path."""
        reports_dir = self._reports_dir()
        output_path = reports_dir / filename
        output_path.write_text(html_content, encoding="utf-8")
        logger.info(f"HTML report saved: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------

    def build_pdf_report(self, markdown_content: str) -> bytes | None:
        """
        Converts markdown AI output to a PDF using reportlab.
        Returns PDF bytes, or None if reportlab is not available.
        """
        if not REPORTLAB_AVAILABLE:
            logger.warning("Skipping PDF — reportlab not installed.")
            return None

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=1 * inch,
            bottomMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=26,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=18,
        )
        h1_style = ParagraphStyle(
            "H1",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#111827"),
            spaceBefore=18,
            spaceAfter=8,
        )
        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            fontSize=15,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=14,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#374151"),
            leading=16,
            spaceAfter=8,
        )
        bullet_style = ParagraphStyle(
            "Bullet",
            parent=body_style,
            leftIndent=20,
            bulletIndent=10,
        )

        # Cover
        story.append(Paragraph(_reportlab_safe_text(self.company_name), title_style))
        story.append(Paragraph(
            _reportlab_safe_text("Personalized Business Insight Report"), subtitle_style
        ))
        story.append(Paragraph(
            _reportlab_safe_text(
                f"Generated on {datetime.now().strftime('%B %d, %Y')}"
            ),
            subtitle_style,
        ))
        story.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor("#e5e7eb")
        ))
        story.append(Spacer(1, 0.2 * inch))

        # --- Parse markdown table rows into a ReportLab Table ---
        table_rows: list[list[str]] = []
        in_table = False

        lines = markdown_content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                if in_table and table_rows:
                    story.append(_build_rl_table(table_rows, body_style))
                    story.append(Spacer(1, 0.1 * inch))
                    table_rows = []
                    in_table = False
                else:
                    story.append(Spacer(1, 0.08 * inch))
                i += 1
                continue

            # Detect markdown table
            if stripped.startswith("|"):
                # Skip separator rows like |---|---|
                if re.match(r"^\|[\s\-:|]+\|", stripped):
                    i += 1
                    continue
                in_table = True
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                table_rows.append(cells)
                i += 1
                continue

            # Flush table if we exited it
            if in_table and table_rows:
                story.append(_build_rl_table(table_rows, body_style))
                story.append(Spacer(1, 0.1 * inch))
                table_rows = []
                in_table = False

            if stripped.startswith("# "):
                story.append(Paragraph(_reportlab_safe_text(stripped[2:]), h1_style))
            elif stripped.startswith("## "):
                story.append(Paragraph(_reportlab_safe_text(stripped[3:]), h2_style))
            elif stripped.startswith("### "):
                story.append(Paragraph(_reportlab_safe_text(stripped[4:]), h2_style))
            elif stripped.startswith(("- ", "* ")):
                story.append(
                    Paragraph(_reportlab_safe_text(f"• {stripped[2:]}"), bullet_style)
                )
            elif re.match(r"^\d+\.\s", stripped):
                story.append(Paragraph(_reportlab_safe_text(stripped), bullet_style))
            else:
                story.append(Paragraph(_reportlab_safe_text(stripped), body_style))

            i += 1

        # Flush any remaining table
        if in_table and table_rows:
            story.append(_build_rl_table(table_rows, body_style))

        try:
            doc.build(story)
            return buffer.getvalue()
        except Exception as e:
            logger.error(
                "PDF build failed (often bad markup in AI output): %s", e, exc_info=True
            )
            return None
        finally:
            buffer.close()

    def save_pdf_report(self, pdf_bytes: bytes, filename: str) -> Path | None:
        """Saves PDF report to generated_reports/. Returns path."""
        if not pdf_bytes:
            return None
        reports_dir = self._reports_dir()
        output_path = reports_dir / filename
        output_path.write_bytes(pdf_bytes)
        logger.info(f"PDF report saved: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reports_dir(self) -> Path:
        # FIX: walk up from app/services/ → app/ → project root
        project_root = Path(__file__).resolve().parent.parent.parent
        reports_dir = project_root / "generated_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir


def _build_rl_table(rows: list[list[str]], base_style: Any):
    """Converts a list of row lists into a styled ReportLab Table."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

    if not rows:
        return Spacer(1, 0.01 * inch)

    header_style = ParagraphStyle(
        "TableHeader",
        parent=base_style,
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.HexColor("#111827"),
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=base_style,
        fontSize=10,
        textColor=colors.HexColor("#374151"),
    )

    table_data = []
    for row_idx, row in enumerate(rows):
        style = header_style if row_idx == 0 else cell_style
        table_data.append(
            [Paragraph(_reportlab_safe_text(cell), style) for cell in row]
        )

    col_count = max(len(r) for r in table_data)
    col_width = (A4[0] - 1.5 * inch) / col_count

    tbl = Table(table_data, colWidths=[col_width] * col_count)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#fafafa")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl
