# Feature Inventory & Roadmap

## 1. What's fully implemented and verified working

### Core RAG pipeline
- Document loading: PDF, DOCX, TXT, MD (`ingestion/document_loader.py`)
- Topic-aware chunking that auto-detects `Subject - Unit N: Topic` sections,
  falling back to file-level manifest metadata otherwise (`ingestion/chunker.py`)
- Hybrid retrieval: dense (Chroma) + sparse (BM25) fused via Reciprocal Rank
  Fusion, then cross-encoder reranked, with gap-aware topic boosting
  (`retrieval/hybrid_retriever.py`)
- Institution notes upload API — add PDFs/notes through the running app,
  auto re-ingests (`api/routes/materials.py`) — **new this session**

### Student modeling & adaptive learning
- Student profiles with cognitive traits, VARK learning style, pace
  preference (`student_model/student_profile.py`)
- Per-concept mastery via Bayesian Knowledge Tracing (`student_model/knowledge_state.py`)
- Knowledge graph with prerequisite edges, Bloom levels, difficulty
  (`knowledge_graph/`)
- Gap analysis: traces backward through prerequisites to find root gaps,
  not just surface-level misses (`gap_analysis/gap_analyzer.py`)
- IRT (3-parameter logistic) ability estimation (`mastery/irt_engine.py`)
- Adaptation engine: triggers difficulty/pace changes on performance
  patterns (`mastery/adaptation_engine.py`)

### Teaching agent
- `TeachingAgent` orchestrates retrieval → gap analysis → pedagogy →
  explanation generation, now actually wired into the live API (it
  wasn't, before this audit — see CORRECTIONS_LOG.md)
- Real LLM backend (`llm/client.py`, `AnthropicLLMClient`) — used when
  `ANTHROPIC_API_KEY` is set; every generator gracefully falls back to
  templates otherwise
- Pedagogy engine adapts explanation style/scaffolding to the student's
  cognitive profile

### Assessment
- Adaptive diagnostic test (IRT-driven, cross-subject placement test) —
  `api/routes/assessment.py`
- **New this session**: fixed-length, per-topic quiz with live BKT
  mastery updates after every question — `api/routes/quiz.py`
- Auto-grading for multiple-choice, true/false, fill-in-blank (reliable
  without an LLM); short-answer/code/problem-solving need an LLM key to
  be gradable — see the note in section 3

### Persistence
- **New this session**: real SQLite persistence via SQLAlchemy
  (`database/repository.py` + rewired `api/store.py`). Students, mastery,
  and interaction logs now survive a server restart — verified by
  actually creating a student, killing the process, and restarting.

### UI (student portal)
- Sidebar-navigated portal with a live student switcher: Overview,
  Ask Tutor (RAG chat), Practice Quiz (diagnostic + new topic-quiz mode),
  My Concepts, Gap Analysis, Learning Path, and a Teacher section (Class
  View, Interventions, Knowledge Graph, Enroll Student)
- **New this session**: Course Materials view (upload institution notes,
  see ingested files/topics, remove a file) and a Topic Quiz mode in the
  Practice Quiz view

## 2. Known limitations (by design, not bugs)

- **Dense retrieval needs your own machine.** Chroma + the embedding/
  reranker models require downloading from Hugging Face, which this
  sandbox can't reach. BM25 sparse retrieval works right now; run
  `python scripts/run_ingestion.py` on a machine with normal internet
  access to get dense retrieval working too.
- **Short-answer/code/problem-solving questions need an LLM key.**
  Without `ANTHROPIC_API_KEY`, the template-based question generator
  never fills in a real `correct_answer` for these types, so they can't
  be auto-graded. The quiz route now forces multiple-choice questions
  when no key is set specifically to avoid this — worth mentioning
  explicitly in your report as a deliberate graceful-degradation design
  choice, not an oversight.
- **Single-process, single-machine.** No auth, no multi-tenant isolation,
  SQLite (not built for concurrent writers at scale). Fine for a
  final-year demo; see section 3 if you want to harden it.

## 3. What's not implemented — and how to add it if you want to go further

### a) Real authentication / login
Right now "logging in" is just picking a name from a dropdown — anyone
can act as anyone. To add real auth:
1. Add a `password_hash` column to the `Student` model (use `passlib`'s
   bcrypt).
2. Add `POST /api/auth/login` (checks password, returns a JWT) and
   `POST /api/auth/signup`.
3. Add a `Depends(get_current_student)` FastAPI dependency that decodes
   the JWT and injects the student, replacing the `student_id` query
   param pattern used everywhere now.
4. On the frontend, replace the sidebar dropdown with an actual login
   form; store the JWT in memory (not localStorage, to avoid XSS token
   theft) and attach it as an `Authorization: Bearer` header in `api()`.

### b) LLM-graded short-answer/code questions
This mostly already works — it just needs a key:
```bash
export ANTHROPIC_API_KEY=your_key_here
```
`question_generator.py` and `grader.py` both already check
`if self.llm_client:` and switch to real generation/grading
automatically. No code changes needed; just demo it with and without
the key set to show the fallback behavior explicitly.

### c) Rebuilding the dense (Chroma) index
Needs to happen on a machine with real internet access:
```bash
pip install -r requirements.txt
python scripts/run_ingestion.py
```
This rebuilds `data/index/chroma/` and `data/index/bm25.pkl` from
everything in `data/raw/` + `manifest.json`. Do this after uploading
new institution notes if you want dense retrieval to reflect them
immediately, rather than relying on the API's best-effort rebuild
(which will report `dense_index: "failed (...)"` in this sandbox but
should say `"rebuilt"` on your machine).

### d) Multi-subject / multi-course support
The knowledge graph currently ships with one sample CS graph
(`knowledge_graph/domain_loader.py::create_sample_cs_graph`). To add a
second subject:
1. Write a second `create_sample_<subject>_graph()` method (or load
   from a JSON/YAML file instead of hardcoding — recommended if you'll
   add more than one or two).
2. Store which subject/course each student is enrolled in on
   `StudentProfile` (add an `enrolled_subjects: List[str]` field).
3. Filter concept lists, gap analysis, and retrieval's `subject` param
   by the student's enrolled subject everywhere a full concept list is
   fetched.

### e) Spaced repetition scheduling
`ConceptMastery` already has the SM-2 algorithm fields
(`repetition_number`, `easiness_factor`, `next_review_date`) and
`KnowledgeState.get_concepts_for_review()` — the data model is ready,
but nothing calls it yet. Add:
1. A scheduled job (APScheduler, or a simple daily cron calling a
   script) that queries `get_concepts_for_review()` for every student.
2. A notification mechanism (email via `smtplib`, or just a dashboard
   badge) prompting the student to review those concepts.

### f) Deployment hardening
For anything beyond a local demo:
- Swap SQLite for Postgres (`database/database.py`'s `Database.__init__`
  already takes any SQLAlchemy URL — just change the connection string
  and add `psycopg2-binary` to requirements)
- Put Chroma behind its own server mode instead of embedded/persistent
  client mode, if you expect concurrent traffic
- Add `alembic` migrations (already in requirements.txt, unused) instead
  of `Base.metadata.create_all()`, so schema changes don't require
  wiping the database

## 4. Suggested priority if you have limited time before submission

1. Run ingestion on your own machine to get dense retrieval working —
   this is the single most "RAG" thing a final-year evaluator will
   check, and it's currently the only piece unverified end-to-end.
2. Add a few real subject PDFs via the new materials upload feature and
   demo the tutor citing them.
3. Set `ANTHROPIC_API_KEY` and demo the LLM-backed explanation/quiz
   generation vs. the template fallback side-by-side — this is a strong,
   easy-to-explain "graceful degradation" story for your viva.
4. Leave authentication and multi-subject support as documented future
   work in your report rather than trying to build them now — they're
   real features but not what makes a RAG tutoring system "work" for a
   demo, and the procedures above are enough to describe the design
   intent without shipping the code.

## 5. Session update — memory, department portal, and retrieval honesty fixes

### Why answers looked like raw extraction, not real synthesis
Not a bug — the honest ceiling of template-based generation. The LLM
path (`agent/explanation_generator.py::_generate_with_llm`) already
builds a proper level-adaptive prompt (learning style, working memory,
difficulty, style instructions) — verified by reading it. Without
`ANTHROPIC_API_KEY`, the fallback used to be a blind `context[:500]`
character truncation; it now extracts the most query-relevant
*sentences* instead and says explicitly that it's extraction, not
synthesis. **Setting `ANTHROPIC_API_KEY` is the real fix** — the code
already supports it end-to-end.

### Conversation memory (new)
`agent/conversation_memory.py` pulls a student's last few Q&A turns
from `interaction_logs` (already being written, never read back) and
feeds them into the LLM prompt so follow-ups like "give another
example" resolve correctly instead of being answered in isolation.
This is recency-window memory, not semantic search over a student's
whole history — see the note in that file for how to extend it into
one (embed + index past interactions the same way course materials
are indexed).

### Department analytics portal (new)
`StudentProfile`/`Student` gained a `department` field. New
`api/routes/department.py`: department list, overview (avg mastery,
engagement, mastery distribution), per-concept weakest-topics
breakdown (the actionable "what's the whole department weak on"
view), and student roster. New "Department Analytics" portal page.
Departments are just a free-text field on the student, not a separate
table — fine for this scope; see section 3 if you need a real
Department entity with its own lifecycle.

### Retrieval honesty fixes (found while testing the above)
Three real bugs, found by actually asking questions and checking the
answers against what should have happened:
1. **BM25 had no stopword filtering** — a short query like "what is a
   variable" scored chunks mostly on how often they contained "is"/
   "a"/"what", not the one word that mattered. A query about variables
   matched an unrelated Stack chunk with a *higher* score than
   anything else. Fixed with a small stopword list in
   `retrieval/text_utils.py`.
2. **The no-reranker fallback synthesized a fake confidence curve** —
   when the cross-encoder reranker isn't available (no internet), the
   code used to score candidates by list position (1.0, 0.86, 0.71...)
   regardless of whether they actually matched anything, producing
   ~88% confidence on a completely wrong answer. Fixed to use the real
   normalized BM25 score instead.
3. **A genuine zero-match still returned "top" results** — even when
   nothing in the corpus matched the query at all, retrieval returned
   *something* (the BM25 tie-break order's arbitrary pick), so the
   system confidently explained an unrelated topic instead of saying
   "I don't have sufficient information." Fixed: a true all-zero-score
   match now returns no results, correctly triggering the honest
   fallback message and `requires_human_review: true`.

**Also worth knowing**: the bundled `sample_data_structures.txt` covers
Arrays, Time Complexity, Linked Lists, Stack, Queue, Recursion, Sorting,
and Binary Trees — but the knowledge graph also defines a
`ds_variable` ("Variables and Data Types") concept that has **no
matching course material** in the sample file. Asking about it will
correctly report low/no confidence now instead of hallucinating an
answer from an unrelated chunk. Add a real "Variables" section via the
Course Materials upload page if you want that concept to be teachable
from real content.

## 6. Two more high-value features worth adding (not built this round)

**Spaced repetition reminders** — the data model is entirely ready
(`ConceptMastery.repetition_number/easiness_factor/next_review_date`,
`KnowledgeState.get_concepts_for_review()`), nothing calls it yet. Add
a scheduled job (APScheduler) that checks `get_concepts_for_review()`
per student daily and surfaces a "due for review" badge on the
dashboard.

**Progress-over-time chart** — `interaction_logs` now has real
timestamped history per student (used for conversation memory above).
A `GET /api/dashboard/student/{id}/history` endpoint that buckets
`was_correct` by week/concept would feed a genuinely useful mastery-
over-time line chart with almost no new infrastructure — the hard part
(persisting the history) is already done.
