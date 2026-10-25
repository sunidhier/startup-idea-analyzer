import os
import sys
import json
import re

import httpx
import requests

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load .env values without replacing variables already set by the environment.
load_dotenv()

app = Flask(__name__)

# System prompt template for startup analysis
STARTUP_ANALYSIS_PROMPT_TEMPLATE = """
You are an expert venture capitalist and startup analyst. Analyze the following startup idea and provide structured feedback.

Return STRICT JSON format with exactly these keys:
{
  "uniqueness": "A detailed analysis of the idea's uniqueness and novelty (2-3 sentences).",
  "competition": "An overview of existing and potential competition, key players, and competitive landscape (2-3 sentences).",
  "goToMarketStrategy": "A basic, actionable go-to-market strategy for this startup idea (2-3 sentences or bullet points).",
  "feasibilityScore": 7,
  "overallAssessment": "A concise summary of your analysis and key takeaways (1-2 sentences)."
}

Note: "feasibilityScore" must be a number from 1 (very low) to 10 (very high).

Startup Idea:
---
{USER_IDEA}
---
"""

def extract_json(text: str) -> dict:
    """Attempts to parse JSON from AI response, with robust fallback extraction."""
    text = text.strip()
    
    # 1. Try direct parsing
    try:
        return json.loads(text)
    except Exception:
        pass
        
    # 2. Extract using regex if enclosed in markdown code fences or raw curly braces
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except Exception:
            pass
            
    # 3. Graceful fallback structure
    return {
        "uniqueness": text,
        "competition": "Could not parse separate competition analysis.",
        "goToMarketStrategy": "Focus on customer discovery and validating core value propositions.",
        "feasibilityScore": 7,
        "overallAssessment": "Analysis provided, but format was unstructured."
    }


class ProviderAPIError(Exception):
    """Represents an unsuccessful response from an AI provider."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _friendly_provider_error(provider: str, error: Exception, status: int | None, detail: str) -> tuple[str, int]:
    """Maps provider and network errors to concise messages suitable for the UI."""
    lowered_detail = detail.lower()
    if status in (401, 403) or "api_key_invalid" in lowered_detail or (
        "invalid" in lowered_detail and "key" in lowered_detail
    ):
        return (
            f"The {provider} API key was rejected. Check your key and account access.",
            502,
        )
    if status == 404 or ("model" in lowered_detail and "not found" in lowered_detail):
        return (
            "The selected AI model is unavailable. Please try again later.",
            503,
        )
    if isinstance(
        error,
        (
            httpx.RequestError,
            requests.exceptions.RequestException,
            TimeoutError,
            ConnectionError,
        ),
    ):
        return (
            "Could not connect to the AI service. Check your connection and try again.",
            503,
        )
    if status == 429:
        return (
            "The AI service is busy or its request limit was reached. Please try again shortly.",
            503,
        )
    if status is not None and status >= 500:
        return ("The AI service is temporarily unavailable. Please try again shortly.", 503)
    return (
        "We couldn't complete the analysis. Please try again in a moment.",
        502,
    )


_GEMINI_MODEL = "gemini-3.8-flash"


def analyze_with_gemini(idea: str, api_key: str) -> dict:
    """Calls Google Gemini API using the official google-genai SDK."""
    from google import genai
    from google.genai import types

    # Temporary diagnostic: log the model ID that will be sent to the API.
    # Safe to keep in production — logs the model name only, never the key.
    app.logger.info("[DIAGNOSTIC] Gemini model: %s | SDK: %s", _GEMINI_MODEL, genai.__version__)

    client = genai.Client(api_key=api_key)
    prompt = STARTUP_ANALYSIS_PROMPT_TEMPLATE.replace("{USER_IDEA}", idea)
    
    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4
        )
    )
    return extract_json(response.text)

def analyze_with_openrouter(idea: str, api_key: str) -> dict:
    """Calls OpenRouter API using requests."""

    prompt = STARTUP_ANALYSIS_PROMPT_TEMPLATE.replace("{USER_IDEA}", idea)
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "mistralai/mixtral-8x7b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5
        },
        timeout=30
    )
    
    if response.status_code != 200:
        raise ProviderAPIError(response.status_code, response.text)
        
    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise ProviderAPIError(response.status_code, "The provider returned an empty response.")
        
    return extract_json(content)

@app.route("/")
def index():
    """Serves the main application page."""
    load_dotenv()
    
    # Check if an API key is configured
    has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    
    return render_template(
        "index.html",
        has_api_key=(has_gemini or has_openrouter),
        active_provider="Google Gemini" if has_gemini else ("OpenRouter" if has_openrouter else None)
    )

@app.route("/api/analyze", methods=["POST"])
def analyze_idea():
    """API endpoint to analyze startup ideas."""
    load_dotenv()
    
    data = request.get_json() or {}
    idea = data.get("idea", "").strip()

    if not idea:
        return jsonify({"success": False, "error": "Please provide your startup idea."}), 400

    if len(idea) < 10:
        return jsonify({
            "success": False, 
            "error": "Please provide a more detailed description of your idea (at least 10 characters)."
        }), 400

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()

    if not gemini_key and not openrouter_key:
        return jsonify({
            "success": False,
            "error": "No AI provider is configured. Add a provider key to your .env file, then try again."
        }), 503

    provider = "Google Gemini" if gemini_key else "OpenRouter"
    api_key = gemini_key or openrouter_key
    try:
        if gemini_key:
            analysis = analyze_with_gemini(idea, gemini_key)
        else:
            analysis = analyze_with_openrouter(idea, openrouter_key)

        # Validate that feasibilityScore is a valid integer between 1 and 10
        try:
            analysis["feasibilityScore"] = max(1, min(10, int(analysis.get("feasibilityScore", 7))))
        except Exception:
            analysis["feasibilityScore"] = 7

        return jsonify({"success": True, "data": analysis})

    except Exception as e:
        status = getattr(e, "status", None)
        detail = getattr(e, "detail", None) or getattr(e, "message", None) or str(e)
        if api_key:
            detail = detail.replace(api_key, "[REDACTED]")
        app.logger.error(
            "%s analysis failed (status=%s, type=%s): %s",
            provider,
            status,
            type(e).__name__,
            detail,
        )
        message, response_status = _friendly_provider_error(provider, e, status, detail)
        return jsonify({"success": False, "error": message}), response_status

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n[READY] Startup Idea Analyzer (Flask) running at http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
