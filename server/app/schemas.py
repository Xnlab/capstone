from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth
class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=100)
    name: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    user: "UserOut"


class UserOut(ORM):
    id: int
    email: str
    name: str


# ---------- company
class CompanyIn(BaseModel):
    company_name: str = ""
    representative: str = ""
    business_number: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    manager_name: str = ""


class CompanyOut(CompanyIn, ORM):
    id: int
    updated_at: datetime


# ---------- contract
class ContractIn(BaseModel):
    contract_title: str = Field(min_length=1, max_length=200)
    client_name: str = ""
    amount: int = Field(default=0, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    description: str = ""


class ContractOut(ContractIn, ORM):
    id: int
    created_at: datetime
    document_count: int = 0


# ---------- template
class TemplateField(BaseModel):
    label: str
    field_key: str | None = None
    confidence: float = 0
    method: str = "rule"
    context: str = ""
    location: dict = {}


class TemplateOut(ORM):
    id: int
    kind: str
    name: str
    category: str
    description: str
    aliases: list = []
    fields: list[TemplateField] = []
    field_keys: list[str] = []
    source_type: str | None = None
    status: str
    expires_at: datetime | None = None
    created_at: datetime


class TemplateMappingIn(BaseModel):
    name: str | None = None
    category: str | None = None
    fields: list[TemplateField]


class SearchResult(BaseModel):
    template: TemplateOut
    score: float
    ai: bool = False


# ---------- document
class DocumentCreate(BaseModel):
    template_id: int


class DocumentUpdate(BaseModel):
    values: dict[str, str]


class DocumentOut(ORM):
    id: int
    contract_id: int
    template_id: int
    title: str
    values: dict
    status: str
    created_at: datetime
    updated_at: datetime
    template_kind: str = ""
    field_keys: list[str] = []
    missing: list[str] = []


class MailIn(BaseModel):
    to: str
    subject: str = ""
    body: str = ""
    document_ids: list[int]
    format: str = "pdf"  # pdf | docx


TokenOut.model_rebuild()
