# Startup Idea Analyzer

An AI-powered web application that evaluates startup ideas and returns structured, VC-style feedback covering uniqueness, competitive landscape, go-to-market strategy, and a feasibility score.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square)
![Flask](https://img.shields.io/badge/Flask-3.0-black?style=flat-square)
![Gemini](https://img.shields.io/badge/Google%20Gemini-gemini--3.8--flash-green?style=flat-square)

---

## Overview

You describe your startup idea in plain language. The app sends it to Google Gemini (or OpenRouter as a fallback) with a structured prompt, parses the response, and presents the analysis in a clean, readable report.

API keys are handled server-side only — they are never exposed to the browser.

---

## Features

- **Structured analysis** — uniqueness, competition, go-to-market strategy, and a 1–10 feasibility score
- **Dual provider support** — Google Gemini (primary) or OpenRouter (fallback)
- **Secure key handling** — keys stay on the server; sanitized from all error responses
- **Graceful error handling** — network failures, invalid keys, and model errors surface as clear user messages
- **Responsive UI** — works on desktop, tablet, and mobile
- **No frontend framework** — plain HTML, CSS, and JavaScript

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3 |
| AI / LLM | Google Gemini API (`gemini-3.8-flash`) via `google-genai` SDK |
| Fallback LLM | OpenRouter (`mistralai/mixtral-8x7b-instruct`) via `requests` |
| Frontend | Vanilla HTML / CSS / JavaScript |
| Config | `python-dotenv` |
| Testing | `unittest`, `unittest.mock` |

---

## Project Structure

```
startup_analyser_flask/
├── app.py               # Flask server, AI provider logic, API routes
├── templates/
│   └── index.html       # Frontend — HTML, CSS, and JS (no build step)
├── requirements.txt     # Python dependencies
├── .env                 # Your API keys — never committed
├── .env.example         # Key template for new contributors
├── .gitignore
└── test_app.py          # Unit tests (9 tests, no live API calls required)
```

---

## Getting Started

### Prerequisites

- Python 3.10 or later
- A [Google AI Studio](https://aistudio.google.com/apikey) API key (free tier works)

### 1. Clone the repository

```bash
git clone https://github.com/sunidhier/startup-idea-analyzer.git
cd startup-idea-analyzer
```

### 2. Create and activate a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your API key

Copy the example file and add your key:

```bash
cp .env.example .env
```

Open `.env` and fill in your key:

```env
# Get a free key at https://aistudio.google.com/apikey
GEMINI_API_KEY=your_key_here

# Optional fallback — https://openrouter.ai/keys
OPENROUTER_API_KEY=
```

### 5. Run the app

```bash
python app.py
```

Visit **http://127.0.0.1:5000** in your browser.

> **Important:** Always start the server using the virtual environment's Python (`python` after activating, or `.venv/Scripts/python.exe` directly). Running with the system Python will fail silently if `google-genai` is not installed globally.

---

## Running Tests

The test suite uses only mocks — no live API calls, no API key required.

```bash
python -m pytest test_app.py -v
```

All 9 tests should pass. The suite covers:
- Home page rendering
- Input validation
- Missing API key handling
- Key read from environment
- Correct Gemini model used
- OpenRouter authorization header
- Network error messaging
- Invalid key messaging
- Secret redaction from error responses

---

## How It Works

1. The user submits a startup idea via the form.
2. The Flask backend reads the API key from environment variables.
3. The idea is inserted into a structured prompt asking for JSON output.
4. The response is parsed and validated (with a robust fallback for malformed output).
5. The `feasibilityScore` is clamped to the 1–10 range before being returned.
6. The frontend renders the result as a structured report.

Error handling covers invalid keys, model unavailability, network failures, and rate limits — each returns a plain-language message without exposing provider details.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | One of the two | Google AI Studio API key |
| `OPENROUTER_API_KEY` | One of the two | OpenRouter API key |
| `PORT` | No (default: 5000) | Port the Flask server listens on |

At least one of `GEMINI_API_KEY` or `OPENROUTER_API_KEY` must be set. If both are present, Gemini is used.

---

## Security Notes

- `.env` is listed in `.gitignore` — it will never be committed.
- API keys are read server-side and stripped from all error messages before they reach the client.
- The app does not log, store, or forward user input or analysis results.


