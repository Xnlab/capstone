import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]  # server/
load_dotenv(BASE_DIR / ".env")


class Settings:
    CLOUD_MODE = os.getenv("CLOUD_MODE", "0") == "1"
    DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA") or None
    LIBRARY_ADMIN_EMAILS = {s.strip().lower() for s in os.getenv("LIBRARY_ADMIN_EMAILS", "").split(",") if s.strip()}
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-secret-key-change-me-in-production")
    ACCESS_TOKEN_HOURS: int = int(os.getenv("ACCESS_TOKEN_HOURS", "24"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'storage' / 'app.db').as_posix()}")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", "/tmp/capstone" if CLOUD_MODE else str(BASE_DIR / "storage")))
    UPLOAD_DIR: Path = STORAGE_DIR / "uploads"
    OUTPUT_DIR: Path = STORAGE_DIR / "outputs"
    UPLOAD_RETENTION_DAYS: int = int(os.getenv("UPLOAD_RETENTION_DAYS", "30"))
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "3" if CLOUD_MODE else "10"))

    PDF_FONT_PATH: str = os.getenv("PDF_FONT_PATH", str(BASE_DIR / "fonts" / "NanumGothic-Regular.ttf") if CLOUD_MODE else "C:/Windows/Fonts/malgun.ttf")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")

    CORS_ORIGINS: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.OPENAI_API_KEY)


settings = Settings()
if settings.CLOUD_MODE and (not os.getenv("SECRET_KEY") or not os.getenv("DATABASE_URL") or not settings.DATABASE_SCHEMA):
    raise RuntimeError("Cloud deployment requires SECRET_KEY, DATABASE_URL and DATABASE_SCHEMA.")
if settings.CLOUD_MODE and len(settings.SECRET_KEY.encode()) < 32:
    raise RuntimeError("Cloud SECRET_KEY must be a unique random secret of at least 32 bytes.")
for d in (settings.STORAGE_DIR, settings.UPLOAD_DIR, settings.OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)
