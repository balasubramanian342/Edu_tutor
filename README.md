# RAG Tutor — Adaptive Learning System

An adaptive tutoring application that combines retrieval-augmented generation (RAG), student profiles, course materials, assessments, and progress tracking. This version can connect to a local OpenAI-compatible endpoint provided by the third-party `openai-oauth` proxy.

> **Note:** `openai-oauth` is not an official OpenAI service. It uses your ChatGPT account, so its available models and usage limits apply. Keep the proxy bound to `127.0.0.1`; do not expose it to the internet.

## Features

- Ask questions about uploaded course materials.
- Retrieve relevant content using the project's RAG system.
- Enroll students individually or import a CSV/Excel student dataset.
- Create quizzes and assessments and track student progress.
- View student and teacher dashboards, knowledge gaps, and department analytics.
- Explore the REST API through FastAPI's interactive documentation.

## Requirements

- Python
- Node.js and npm, for running the local OAuth proxy
- A ChatGPT account supported by the proxy
- Course materials to upload (optional)

## Quick start on Windows

Run commands from the `rag_tutor` project directory.

### 1. Create an environment and install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks environment activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2. Configure the local OAuth proxy

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

In Terminal 1, sign in and start the proxy:

```powershell
npx openai-oauth@latest login
npx openai-oauth@latest
```

In another terminal, check which models are available:

```powershell
Invoke-RestMethod http://127.0.0.1:10531/v1/models
```

Set `OPENAI_OAUTH_MODEL` in `.env` to a model ID returned by that command. The example model in `.env.example` may not be available to your account.

```env
OPENAI_BASE_URL=http://127.0.0.1:10531/v1
OPENAI_OAUTH_MODEL=<MODEL_ID_FROM_MODELS_ENDPOINT>
OPENAI_API_KEY=openai-oauth-local
```

The local proxy does not require a real OpenAI API key. Do not commit `.env` or put credentials in frontend code.

### 3. Start the application

In Terminal 2, from the project directory:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Start the OAuth proxy before starting the application. If the proxy is unavailable, the application may use its template responses instead of LLM-generated responses.

Open the application at:

- **Tutor UI:** http://localhost:8000
- **API documentation:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

For detailed setup, troubleshooting, and proxy instructions, see [OAUTH_SETUP.md](OAUTH_SETUP.md).

## Add course materials

Use the application's **Course Materials** page to upload materials, or follow the ingestion scripts and manifest format in the project. Supported document formats include PDF, DOCX, TXT, and Markdown.

The RAG system retrieves relevant material to provide context for tutor responses.

## Import a student dataset

The **Enroll Student** page accepts `.csv`, `.xlsx`, and `.xls` files. Include these required columns:

```text
student_id,name,email
```

Optional columns can include institution, department, class, grade level, marks, attendance, and learning preferences.

Example:

```csv
student_id,name,email,institution,department,class_name,grade_level,exam_marks,attendance_percentage
STU001,Arun Kumar,arun@example.edu,ABC College,Computer Science,CSE-A,Year 2,78,86
STU002,Divya Raj,divya@example.edu,ABC College,Computer Science,CSE-A,Year 2,64,91
```

The importer reports created students, skipped existing students, and invalid rows.

## API overview

The API is documented interactively at `/docs`. Main route groups include:

- `/api/students` — student enrollment, lookup, and dataset import
- `/api/teaching` — tutor questions and hints
- `/api/assessment` — assessments and answers
- `/api/quiz` — quiz sessions and answers
- `/api/dashboard` — student and teacher dashboards
- `/api/knowledge` — concepts, subjects, and learning paths
- `/api/materials` — course material upload and listing
- `/api/department` — department analytics

## Project structure

```text
rag_tutor/
├── agent/              # Adaptive teaching
├── api/                # FastAPI application and routes
├── assessment/         # Assessment generation and grading
├── dashboard/          # Student and teacher dashboards
├── database/           # Database models and persistence
├── gap_analysis/       # Knowledge-gap analysis
├── ingestion/          # Document loading and indexing
├── knowledge_graph/    # Concepts and prerequisite relationships
├── llm/                # LLM client configuration
├── mastery/             # Mastery tracking and adaptation
├── retrieval/           # RAG retrieval
├── static/              # Web application UI
├── student_model/       # Student profiles and knowledge state
├── tests/               # Tests
├── data/                # Course materials and retrieval indexes
├── .env.example         # Example local configuration
├── OAUTH_SETUP.md       # Detailed OAuth proxy setup
└── requirements.txt     # Python dependencies
```

## Stopping the services

Stop the FastAPI server with `Ctrl+C`. Stop the OAuth proxy in its terminal with `Ctrl+C`. If you started the proxy detached, use:

```powershell
npx openai-oauth@latest stop
```

## Security

- Keep `.env` and account credentials private.
- Keep the OAuth proxy on `127.0.0.1`; do not expose its port to other machines or the internet.
- Treat this project and the third-party proxy as a local demo unless you have independently reviewed their security and deployment requirements.
