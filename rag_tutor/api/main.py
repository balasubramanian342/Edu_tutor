"""
FastAPI Application — RAG Tutor Adaptive Learning System
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime

from api.routes import students, teaching, assessment, dashboard, knowledge, quiz, materials, department

app = FastAPI(
    title="RAG Tutor — Adaptive Learning System",
    description="Intelligent tutoring with RAG, knowledge graphs and adaptive assessment",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────
app.include_router(students.router,   prefix="/api/students",   tags=["students"])
app.include_router(teaching.router,   prefix="/api/teaching",   tags=["teaching"])
app.include_router(assessment.router, prefix="/api/assessment", tags=["assessment"])
app.include_router(dashboard.router,  prefix="/api/dashboard",  tags=["dashboard"])
app.include_router(knowledge.router,  prefix="/api/knowledge",  tags=["knowledge"])
app.include_router(quiz.router,       prefix="/api/quiz",       tags=["quiz"])
app.include_router(materials.router,  prefix="/api/materials",  tags=["materials"])
app.include_router(department.router, prefix="/api/department", tags=["department"])

# ── Static UI ─────────────────────────────────────────────────
STATIC_DIR = ROOT / "static"

@app.get("/")
async def serve_ui():
    return FileResponse(str(STATIC_DIR / "index.html"))

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.on_event("startup")
async def startup():
    # api.store already creates the (single, correctly-pathed) Database
    # instance and its tables at import time — main.py used to construct
    # a second Database() here with a different default path
    # ("sqlite:///rag_tutor.db", resolved relative to the process's
    # working directory rather than the project root), which could
    # silently create a stray, empty second SQLite file depending on
    # where uvicorn was launched from. Import the real one instead of
    # duplicating it.
    from api.store import DB
    print("\n✅  Database ready   →", DB.engine.url)
    print("✅  API ready        →  http://localhost:8000/docs")
    print("🎓  UI ready         →  http://localhost:8000\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True, app_dir=str(ROOT))
