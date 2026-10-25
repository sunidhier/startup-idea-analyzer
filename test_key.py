import os
import sys

from dotenv import load_dotenv

from app import _friendly_provider_error, analyze_with_gemini

load_dotenv()
key = os.environ.get("GEMINI_API_KEY", "").strip()
if not key:
    print("Gemini API check failed: GEMINI_API_KEY is not configured.")
    sys.exit(1)

try:
    analyze_with_gemini("A simple test idea for a local delivery service.", key)
except Exception as error:
    status = getattr(error, "status", None)
    detail = getattr(error, "detail", None) or getattr(error, "message", None) or str(error)
    message, _ = _friendly_provider_error("Google Gemini", error, status, detail)
    print(f"Gemini API check failed: {message}")
    sys.exit(1)

print("Gemini API connection successful.")
