# RAG Tutor — local `openai-oauth` setup

This version replaces the Gemini API integration with the third-party
`openai-oauth` local OpenAI-compatible proxy.

## Important

`openai-oauth` is **not an official OpenAI API replacement**. It is a
third-party project that exposes a local OpenAI-compatible endpoint backed by
your ChatGPT account. It can be useful for a local/student demo, but it
should not be treated as a production API gateway or as a way to bypass
usage limits. Your ChatGPT account's available models and usage limits still
apply.

The application connects to:

`http://127.0.0.1:10531/v1`

No paid OpenAI API key is required by this local proxy.

## 1. Prerequisites

Install Node.js (LTS) and make sure these work:

```powershell
node --version
npm --version
python --version
```

## 2. Create/activate the Python environment

From the `rag_tutor` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

## 3. Login to the local OAuth proxy

Open **Terminal 1**:

```powershell
npx openai-oauth@latest login
```

Complete the browser login with your ChatGPT account.

Then start the proxy:

```powershell
npx openai-oauth@latest
```

Or run it in the background:

```powershell
npx openai-oauth@latest --detach
```

Check status:

```powershell
npx openai-oauth@latest status
```

## 4. Find the model available to your account

In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:10531/v1/models
```

Look at the returned `id` values.

Set one of those IDs in `.env`:

```env
OPENAI_BASE_URL=http://127.0.0.1:10531/v1
OPENAI_OAUTH_MODEL=<MODEL_ID_FROM_/v1/models>
OPENAI_API_KEY=openai-oauth-local
```

The placeholder model in the supplied `.env` is only a default example.
Use a model actually returned by your account.

## 5. Start the RAG Tutor

Open **Terminal 2** in the project directory:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Start the OAuth proxy **before** starting FastAPI. The application checks the
local proxy during startup and otherwise falls back to deterministic
template responses.

Open:

`http://localhost:8000`

API documentation:

`http://localhost:8000/docs`

## 6. Test the LLM connection

With the proxy running:

```powershell
Invoke-RestMethod http://127.0.0.1:10531/v1/models
```

Then use the RAG Tutor UI's **Ask Tutor**, quiz and assessment features.

The Python application uses the standard OpenAI-compatible client with:

- Base URL: `http://127.0.0.1:10531/v1`
- Authentication: handled by `openai-oauth`
- Model: `OPENAI_OAUTH_MODEL`
- No real `OPENAI_API_KEY` is stored or required

## 7. New feature — college/institution student dataset upload

The **Enroll Student** page now has:

**Upload Institution Student Dataset**

Supported files:

- `.csv`
- `.xlsx`
- `.xls`

Required columns:

```text
student_id
name
email
```

Common optional columns:

```text
institution
department
class_name
grade_level
exam_marks
marks
average_marks
attendance_percentage
attendance
attendance_percent
visual_score
auditory_score
reading_writing_score
kinesthetic_score
pace_preference
```

The importer accepts common aliases such as:

- `student_id`, `studentid`, `roll_no`, `register_no`
- `name`, `full_name`, `student_name`
- `marks`, `average_marks`, `exam_marks`
- `attendance`, `attendance_percentage`, `attendance_pct`
- `year` → grade level
- `section` → class
- `college` / `college_name` → institution

### Example CSV

```csv
student_id,name,email,institution,department,class_name,grade_level,exam_marks,attendance_percentage
STU001,Arun Kumar,arun@example.edu,ABC College,Computer Science,CSE-A,Year 2,78,86
STU002,Divya Raj,divya@example.edu,ABC College,Computer Science,CSE-A,Year 2,64,91
STU003,Kavin S,kavin@example.edu,ABC College,Computer Science,CSE-B,Year 2,42,73
```

### How to upload

1. Open `http://localhost:8000`.
2. Go to **Enroll Student**.
3. Select the institution dataset.
4. Optionally enter default institution/department/class values.
5. Click **Upload & Enroll Dataset**.
6. The system reports:
   - students created
   - existing students skipped
   - invalid rows
7. Refreshing/restarting the server does not remove imported students because
   student data is persisted in SQLite.

## 8. How the complete adaptive flow now works

```text
College Student Dataset
        |
        v
Student Enrollment
        |
        +--> Marks
        +--> Attendance
        +--> Department/Class
        +--> Student profile
        |
        v
Student Classification
        |
        v
RAG Retrieval from Institution Notes
        |
        v
Student-level context + retrieved notes
        |
        v
openai-oauth local endpoint
        |
        v
LLM-generated explanation / question / feedback
        |
        v
Adaptive Tutor
        |
        v
Student interactions update mastery
```

The LLM is still used only after the RAG system retrieves institution
content. The local OAuth proxy changes the LLM transport; it does not replace
your RAG, student model, mastery engine, knowledge graph or assessment logic.

## 9. Stopping the services

Stop FastAPI with `Ctrl+C`.

If the OAuth proxy is detached:

```powershell
npx openai-oauth@latest stop
```

Check logs:

```powershell
npx openai-oauth@latest logs --follow
```

## 10. If the LLM falls back to templates

Check these in order:

```powershell
npx openai-oauth@latest status
Invoke-RestMethod http://127.0.0.1:10531/v1/models
```

Then verify `.env`:

```env
OPENAI_BASE_URL=http://127.0.0.1:10531/v1
OPENAI_OAUTH_MODEL=<an id returned by /v1/models>
OPENAI_API_KEY=openai-oauth-local
```

Restart FastAPI after changing `.env`.

## 11. Production note

Do not expose port `10531` to the internet. The OAuth proxy uses your local
ChatGPT credentials, so binding it to a non-loopback interface can expose
account-backed access to other machines. Keep it on `127.0.0.1` for this
local project.
