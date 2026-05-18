from datetime import datetime
from pathlib import Path

import markdown

from jinja2 import Environment, FileSystemLoader


class ReportBuilder:

    def __init__(self, company_name: str):

        self.company_name = company_name

        template_dir = (
            Path(__file__).resolve()
            .parent.parent / "templates"
        )

        self.env = Environment(
            loader=FileSystemLoader(template_dir)
        )

    def build_html_report(self, markdown_content: str):

        html_body = markdown.markdown(
            markdown_content,
            extensions=["tables", "fenced_code"]
        )

        current_date = datetime.now().strftime("%B %d, %Y")

        template = self.env.get_template(
            "report_template.html"
        )

        rendered_html = template.render(
            company_name=self.company_name,
            current_date=current_date,
            html_body=html_body
        )

        return rendered_html

    def save_html_report(
        self,
        html_content: str,
        filename: str
    ):

        project_root = (
            Path(__file__).resolve()
            .parent.parent.parent
        )

        reports_dir = project_root / "generated_reports"

        reports_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        output_path = reports_dir / filename

        output_path.write_text(
            html_content,
            encoding="utf-8"
        )

        return output_path