from pydantic import BaseModel


class LeadRequest(BaseModel):
    company_name: str