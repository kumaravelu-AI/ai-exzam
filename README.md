# AI EXZAM MVP

A folder-driven, topic-based student learning and exam app.

## What this MVP includes

- FastAPI backend
- Simple HTML/CSS/JS frontend
- Folder-based knowledge ingestion from:
  - PDF
  - DOCX
  - XLSX
  - TXT
- Local JSON storage for:
  - student profile
  - progress
  - session
  - learning history
  - exam history
- Adaptive learning flow
- Exam mode
- Pluggable AI provider
- Mock AI provider included
- OpenAI-compatible HTTP provider included

## Important note about Gemma

This project includes a **provider interface** and a working **mock provider**.
It also includes a **Gemma-ready OpenAI-compatible path** for cases where your Gemma runtime exposes a compatible `/v1/chat/completions` endpoint.

Because Gemma can be served in different ways depending on your chosen runtime, deployment, or adapter,
you may need to adjust the provider wiring in `app/ai_provider.py`.

That means:
- the app is runnable immediately with mock mode
- the Gemma connector point is already prepared
- final Gemma endpoint details depend on how you host or expose Gemma
- Gemma requires a running local model server that supports `/v1/chat/completions`

## Quick start

```bash
cd ai_exzam_mvp
python -m venv .venv
# Windows PowerShell
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

The app also loads a local `.env` file automatically if present, without overriding existing OS environment variables.

Optional Tamil naturalizer:

```powershell
$env:TAMIL_NATURALIZER_ENABLED = "true"
```

When enabled, the tutor model still decides the English response, intent, score, and next action. A separate isolated step rewrites only the Tamil response and Tamil follow-up so the Tamil can sound more natural without changing lesson logic.

Open:

- http://127.0.0.1:8010/

## Run in mock mode

Windows PowerShell:

```powershell
$env:AI_PROVIDER = "mock"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

This is the simplest way to run the app locally with no external model server.

## Run with Gemma local endpoint

Gemma mode expects a running local model server that exposes an OpenAI-compatible:

```text
/v1/chat/completions
```

Windows PowerShell:

```powershell
$env:AI_PROVIDER = "gemma"
$env:GEMMA_BASE_URL = "http://127.0.0.1:11434/v1"
$env:GEMMA_MODEL = "gemma-3-12b-it"
$env:GEMMA_API_KEY = ""
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

If your Gemma server uses a different port, model name, or requires a bearer token, adjust those values.

## Run with openai_compat

Windows PowerShell:

```powershell
$env:AI_PROVIDER = "openai_compat"
$env:OPENAI_COMPAT_BASE_URL = "http://127.0.0.1:1234/v1"
$env:OPENAI_COMPAT_MODEL = "gemma-4"
$env:OPENAI_COMPAT_API_KEY = ""
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

## Environment variables

Optional:

```bash
set AI_PROVIDER=mock
set GEMMA_BASE_URL=http://127.0.0.1:11434/v1
set GEMMA_MODEL=gemma-3-12b-it
set GEMMA_API_KEY=
set OPENAI_COMPAT_BASE_URL=http://127.0.0.1:1234/v1
set OPENAI_COMPAT_API_KEY=your_key_if_needed
set OPENAI_COMPAT_MODEL=gemma-4
```

Linux/macOS style:

```bash
export AI_PROVIDER=mock
export GEMMA_BASE_URL=http://127.0.0.1:11434/v1
export GEMMA_MODEL=gemma-3-12b-it
export GEMMA_API_KEY=
export OPENAI_COMPAT_BASE_URL=http://127.0.0.1:1234/v1
export OPENAI_COMPAT_API_KEY=your_key_if_needed
export OPENAI_COMPAT_MODEL=gemma-4
```

You can copy `.env.example` to `.env` and set these values there for local development.

## Folder structure for content

```text
knowledgebase/
└── science/
    └── year6/
        └── microorganisms/
            ├── notes/
            ├── examples/
            ├── questions/
            ├── answers/
            └── media/
```

This MVP already ships with one sample topic and question bank.

## Rebuild index

Use the UI button or call:

```bash
POST /api/admin/rebuild-index
```

## Sample student

- student id: `student_demo`
- name: `Demo Student`

It is auto-created on first use.
