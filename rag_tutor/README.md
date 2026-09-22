# RAG Tutor — Adaptive Learning System (openai-oauth edition)

This package uses a local OpenAI-compatible `openai-oauth` proxy for LLM
generation and includes bulk college/institution student dataset enrollment.

See **OAUTH_SETUP.md** for the complete Windows setup and run procedure.

---

# RAG Tutor — Adaptive Learning System

A comprehensive intelligent tutoring system with RAG-based content retrieval, knowledge graphs, adaptive teaching, formative assessment, and real-time personalization.

## 🎯 System Architecture

```
Student Onboarding & Data Collection
        ↓
Student Modeling (Cognitive + Knowledge State)
        ↓
Gap Analysis (Knowledge Graph + Prerequisite Mapping)  ←──────┐
        ↓                                                      │
RAG-based Content Retrieval (from college materials)           │
        ↓                                                      │
Adaptive Teaching / Explanation Generation                     │
        ↓                                                      │
Formative Assessment (question generation + grading)           │
        ↓                                                      │
Mastery Update (Bayesian Knowledge Tracing / IRT)              │
        ↓                                                      │
Adaptation Engine (difficulty, pace, modality) ─────────────────┘
        ↓
Reporting Dashboard (student + teacher view)
```

## 📦 What's Implemented

### 1. **Student Modeling** (`student_model/`)
- **StudentProfile**: Cognitive traits, learning styles, preferences
- **KnowledgeState**: Bayesian Knowledge Tracing with spaced repetition
- **InteractionLog**: Complete interaction history for analytics

### 2. **Knowledge Graph** (`knowledge_graph/`)
- **ConceptGraph**: NetworkX-based directed graph with relationships
- **PrerequisiteMapper**: Learning path analysis and gap identification
- **DomainLoader**: JSON persistence with sample CS domain

### 3. **Gap Analysis** (`gap_analysis/`)
- **GapAnalyzer**: Identifies 5 gap types with severity scoring
- **RemediationPlanner**: Personalized learning plans with sequenced steps

### 4. **RAG System** (`ingestion/` + `retrieval/`)
- **Document Loader**: PDF, DOCX, TXT, MD with page tracking
- **Chunker**: Sliding-window with manifest-driven metadata
- **HybridRetriever**: Dense (embeddings) + BM25 with RRF fusion
- **Gap-aware retrieval**: Biases results toward diagnosed gaps

### 5. **Adaptive Teaching** (`agent/`)
- **TeachingAgent**: Orchestrates RAG + gap analysis + pedagogy
- **ExplanationGenerator**: 7 explanation styles with LLM integration
- **PedagogyEngine**: Applies Bloom's taxonomy, CLT, ZPD, scaffolding

### 6. **Assessment** (`assessment/`)
- **QuestionGenerator**: 9 question types aligned with Bloom's taxonomy
- **AutoGrader**: Automatic grading with partial credit and rubric support
- **AdaptiveTest**: IRT-based adaptive testing with ability estimation

### 7. **Mastery Tracking** (`mastery/`)
- **MasteryTracker**: BKT updates, decay, trajectory tracking
- **IRTEngine**: 3-parameter logistic model, ability estimation
- **AdaptationEngine**: Real-time difficulty/pace/modality adaptation

### 8. **Dashboards** (`dashboard/`)
- **StudentDashboard**: Progress reports, learning paths, next targets
- **TeacherDashboard**: Class analytics, intervention recommendations
- **ProgressVisualizer**: 8+ chart types for frontend rendering

### 9. **Database** (`database/`)
- SQLAlchemy ORM models for all entities
- Student, ConceptMastery, InteractionLog, TestSession tables

### 10. **API** (`api/`)
- FastAPI REST endpoints
- Student management, teaching, assessment, dashboard routes

## 🚀 Quick Start

### Installation

```bash
# Clone and navigate
cd rag_tutor

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from database import Database; db = Database(); db.init_db()"
```

### 1. Ingest Learning Materials

```bash
# Add PDFs/DOCX/TXT/MD to data/raw/
# Create manifest.json (see example below)
python scripts/run_ingestion.py --input data/raw --manifest manifest.json
```

**manifest.json example:**
```json
{
  "unit3_recursion.pdf": {
    "subject": "Data Structures",
    "unit": "Unit 3",
    "topic": "Recursion",
    "difficulty": "medium"
  }
}
```

### 2. Load Knowledge Graph

```python
from knowledge_graph import DomainLoader

# Use sample CS graph
graph = DomainLoader.create_sample_cs_graph()

# Or load from JSON
graph = DomainLoader.load_from_json("domain.json")
```

### 3. Start API Server

```bash
python api/main.py
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### 4. Use the System

```python
from student_model import create_initial_profile, KnowledgeState
from agent import TeachingAgent
from retrieval import HybridRetriever
from gap_analysis import GapAnalyzer

# Create student
profile = create_initial_profile(
    student_id="student_001",
    name="John Doe",
    email="john@example.com"
)

knowledge = KnowledgeState(student_id="student_001")

# Initialize components
retriever = HybridRetriever(
    chroma_path="data/index/chroma",
    bm25_path="data/index/bm25.pkl"
)

gap_analyzer = GapAnalyzer(knowledge_graph, prerequisite_mapper)
teaching_agent = TeachingAgent(retriever, gap_analyzer, explanation_generator)

# Teach
response = teaching_agent.teach(
    student_query="What is recursion?",
    student_profile=profile,
    student_knowledge=knowledge,
    concept_id="ds_recursion"
)

print(response.explanation.content)
```

## 🧪 Testing Retrieval

```bash
python scripts/test_retrieval.py "What is a base case in recursion?"
python scripts/test_retrieval.py "Explain merge sort" --gap-topic Sorting
```

## 📊 Key Features

### Educational Theory Integration
- **Bloom's Taxonomy**: 6-level progression from remember to create
- **Cognitive Load Theory**: Adjusts chunk size based on working memory
- **Zone of Proximal Development**: Optimal difficulty targeting
- **Bayesian Knowledge Tracing**: Probabilistic mastery modeling
- **Item Response Theory**: 3PL model for ability estimation
- **Spaced Repetition**: SM-2 algorithm for review scheduling

### Adaptive Mechanisms
- **7 Explanation Styles**: Concise, detailed, step-by-step, example-driven, analogy-based, visual, interactive
- **Real-time Adaptation**: Adjusts difficulty, pace, scaffolding, modality
- **Gap-aware Retrieval**: RAG biased toward prerequisite gaps
- **5 Gap Types**: Missing prerequisite, weak foundation, skill decay, comprehension gap, misconception

### Assessment Features
- **9 Question Types**: Multiple choice, true/false, fill-in-blank, short answer, code completion, debugging, problem-solving, essay, code-from-scratch
- **Automatic Grading**: Partial credit, fuzzy matching, keyword-based, LLM-rubric
- **Adaptive Testing**: IRT-based difficulty adjustment during test

## 📁 Project Structure

```
rag_tutor/
├── student_model/       # Student profiles and knowledge state
├── knowledge_graph/     # Domain ontology and prerequisites
├── gap_analysis/        # Gap identification and remediation
├── ingestion/          # Document loading and chunking
├── retrieval/          # Hybrid RAG retrieval
├── agent/              # Adaptive teaching agent
├── assessment/         # Question generation and grading
├── mastery/            # BKT, IRT, adaptation engine
├── dashboard/          # Student and teacher dashboards
├── database/           # SQLAlchemy models
├── api/                # FastAPI endpoints
├── data/
│   ├── raw/           # Input materials
│   ├── processed/     # Processed chunks
│   └── index/         # Vector and BM25 indices
└── scripts/           # Utility scripts
```

## 🔬 For Academic Evaluation

### Novel Contributions
1. **Gap-aware RAG**: Retrieval biased by prerequisite analysis, not just semantic similarity
2. **Closed-loop adaptation**: Mastery updates feed back into difficulty, pace, and content selection
3. **Multi-theory integration**: BKT + IRT + Bloom's + CLT working together
4. **Pedagogical grounding**: Not just QA - applies established educational psychology

### Citable Design Decisions
- **Hybrid retrieval (dense + BM25)**: Combines semantic and lexical matching
- **Cross-encoder reranking**: Improves precision over bi-encoder similarity
- **Bayesian Knowledge Tracing**: Principled probabilistic mastery estimation
- **Item Response Theory**: Standard psychometric model for ability
- **Bloom's taxonomy alignment**: All questions and scaffolding levels mapped

## 📝 API Endpoints

- `POST /api/students/` - Create student
- `GET /api/students/{id}` - Get student profile
- `POST /api/teaching/ask` - Ask question, get adaptive explanation
- `POST /api/assessment/start-test` - Start adaptive test
- `GET /api/dashboard/student/{id}` - Get student dashboard
- `GET /api/knowledge/concepts` - List concepts

Full API docs at `/docs` when server is running.

## 🎓 Dependencies

- **Core**: sentence-transformers, chromadb, rank-bm25, networkx
- **Database**: sqlalchemy, alembic
- **API**: fastapi, uvicorn, pydantic
- **Optional**: google-genai (for LLM integration)

See `requirements.txt` for complete list.

## 📄 License

Educational use - adapt for your needs.

## 🤝 Contributing

This is an academic prototype. Extend and improve!

## Gemini LLM setup

The tutor uses the RAG retriever for institution-provided course content and
a Gemini LLM to rewrite and teach that retrieved context according to the
student's profile and mastery. The API client lives in `llm/client.py` and is
shared through `api/store.py`.

1. Copy `.env.example` to `.env`.
2. Get a free API key at https://aistudio.google.com/apikey and set
   `GEMINI_API_KEY` in `.env`.
3. Optionally change `GEMINI_MODEL` (default: `gemini-flash-latest`).
4. Install dependencies with `pip install -r requirements.txt`.
5. Start the API and use `POST /teaching/ask` as before.
6. Optional sanity check before running the full app: `python test_gemini.py`
   confirms your key works with a single standalone API call.

Do not commit `.env` or expose the API key in frontend code.
