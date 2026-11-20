import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


def enabled(key: str, default: str = "true") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes"}


STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
LOCAL_DB_PATH = Path(__file__).resolve().parent / os.getenv("LOCAL_DB_PATH", "data/pole.sqlite3")
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "6198b3bc")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "") if enabled("OPENROUTER_ENABLED") else ""
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODELS = tuple(dict.fromkeys((
    os.getenv("PRIMARY_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
    os.getenv("FALLBACK_LLM_MODEL_1", "google/gemini-2.0-flash-exp:free"),
    os.getenv("FALLBACK_LLM_MODEL_2", "qwen/qwen-2.5-72b-instruct:free"),
    os.getenv("FALLBACK_LLM_MODEL_3", "deepseek/deepseek-chat:free"),
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "openrouter/free",
)))
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
SEED_DEMO = enabled("SEED_DEMO", "false")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024
FRONTEND_ORIGINS = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
).split(",")
