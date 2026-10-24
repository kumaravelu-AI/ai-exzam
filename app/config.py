from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env without overriding real OS environment variables.
load_dotenv(override=False)

ROOT_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGEBASE_DIR = ROOT_DIR / "knowledgebase"
INDEX_DIR = ROOT_DIR / "index"
STUDENTS_DIR = Path(os.getenv("STUDENTS_DIR", str(ROOT_DIR / "students"))).expanduser()
FRONTEND_DIR = ROOT_DIR / "frontend"

AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").strip().lower()
OPENAI_COMPAT_BASE_URL = os.getenv("OPENAI_COMPAT_BASE_URL", "").strip()
OPENAI_COMPAT_API_KEY = os.getenv("OPENAI_COMPAT_API_KEY", "").strip()
OPENAI_COMPAT_MODEL = os.getenv("OPENAI_COMPAT_MODEL", "gemma-4").strip()
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
GROQ_STREAM = os.getenv("GROQ_STREAM", "").strip().lower() in {"1", "true", "yes", "on"}
TAMIL_NATURALIZER_ENABLED = os.getenv("TAMIL_NATURALIZER_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
ADMIN_ENABLED = os.getenv("ADMIN_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

DEFAULT_SUBJECT = "science"
DEFAULT_LEVEL = "year6"
DEFAULT_TOPIC = "microorganisms"

MAX_RETRIEVED_CHUNKS = 6
TOPIC_MASTERY_THRESHOLD = 75
