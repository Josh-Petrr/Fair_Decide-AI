"""Central settings, read from .env (never hard-code secrets)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")   # Windows: harmless HF cache notice

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fairdecide:fairdecide_dev@localhost:5432/fairdecide")

LLM_RUNTIME = os.getenv("FAIRDECIDE_LLM_RUNTIME", "groq").lower()        # "groq" or "none" (rule-based only)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL_SMART = os.getenv("FAIRDECIDE_LLM_MODEL") or os.getenv("GROQ_MODEL_SMART") or "openai/gpt-oss-120b"
GROQ_MODEL_FAST = os.getenv("FAIRDECIDE_LLM_MODEL_FAST") or os.getenv("GROQ_MODEL_FAST") or GROQ_MODEL_SMART

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))      # Mailpit
MAIL_FROM = os.getenv("MAIL_FROM", "FairDecide AI <staffing@nexoratech.example>")

APP_SECRET = os.getenv("APP_SECRET", "dev-only-secret-change-me")

ARTIFACTS = ROOT / "backend" / "ml" / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
_embed = os.getenv("FAIRDECIDE_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBED_MODEL = _embed if "/" in _embed else f"sentence-transformers/{_embed}"   # 384-dim; must match db/schema.sql
