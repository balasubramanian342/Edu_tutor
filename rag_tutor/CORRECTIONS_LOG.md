# Corrections Log — implementation review pass

This documents everything found while auditing the uploaded project and
getting it to actually run end-to-end. Organized by severity.

## Bugs that broke execution (would crash or silently fail)

1. **`retrieval/__init__.py` was empty.**
   `agent/teaching_agent.py` does `from retrieval import HybridRetriever`,
   which would `ImportError` immediately. Fixed by exporting
   `HybridRetriever`, `format_context_for_llm`, `NullRetriever`, `tokenize`.

2. **Retriever ↔ consumer schema mismatch.**
   `hybrid_retriever.py` returned flat chunk dicts with a `_score` key.
   Everything that consumes retrieval results
   (`agent/teaching_agent.py`, `agent/explanation_generator.py`,
   `api/routes/teaching.py`) expected `{'text', 'score', 'metadata': {...}}`.
   Fixed by changing `HybridRetriever.retrieve()` to return the schema
   its own consumers already agreed on. Also stopped it from mutating the
   shared cached chunk objects between calls (a latent state-leak bug —
   scores from one query could bleed into the next).

3. **Wrong constructor call.**
   `api/routes/teaching.py` called
   `HybridRetriever(chroma_path=..., bm25_path=...)`, but the real
   constructor only accepts `index_dir`. Fixed to pass `index_dir`.

## Design gap that made the "RAG-based agent" degrade to templates

4. **No LLM client ever existed.**
   `explanation_generator.py`, `question_generator.py`, and `grader.py`
   all call `self.llm_client.generate(system_prompt=..., user_prompt=...,
   temperature=..., max_tokens=...)`, but no class implementing that
   interface existed anywhere in the codebase, and nothing ever
   constructed one. `llm_client` was always `None` everywhere, so the
   system *always* used the template-based fallback — including the
   comment left in the code: `# Call LLM (placeholder - would use
   actual API)`.

   **Fixed**: added `llm/client.py` with `AnthropicLLMClient`
   (using the `anthropic` package already in requirements.txt) and a
   `build_llm_client()` factory that returns a real client if
   `ANTHROPIC_API_KEY` is set, else `None` — so every consumer's
   existing `if self.llm_client:` check now actually does something,
   and the system behaves exactly as before if you don't set a key.
   Wired into `api/store.py` (`LLM_CLIENT`) and passed into
   `ExplanationGenerator`, `QuestionGenerator`, `AutoGrader`.

5. **The API never actually called the teaching agent.**
   `api/routes/teaching.py`'s `/ask` endpoint had its own hand-rolled
   answer logic (a plain f-string), completely bypassing
   `agent/teaching_agent.py`, `agent/explanation_generator.py`, and
   `agent/pedagogy_engine.py` — the actual "advanced" pedagogy layer
   described in `ARCHITECTURE.md` was never reachable from the live API.

   **Fixed**: rewrote the route to build a real `TeachingAgent` and call
   `agent.teach(...)`. Added `retrieval/NullRetriever`, a no-op stand-in
   used when the vector index isn't available, so `TeachingAgent` can run
   unconditionally without every caller needing an `if retriever:` branch
   — it now degrades honestly ("I don't have sufficient information...")
   instead of crashing or faking an answer.

   The `/ask` response shape changed as a result (see below), so
   `static/index.html`'s JS was updated to match — it now surfaces
   `next_steps`, `requires_human_review`, and `explanation_style` instead
   of the old `gaps_found`/`gap_topic` fields, which no longer exist.

## Retrieval quality bugs

6. **Topic tagging collapsed for multi-topic files.**
   Your `sample_data_structures.txt` has clean `Subject - Unit N: Topic`
   sections separated by `---`, but the chunker only tagged metadata per
   *file* (one manifest entry), so all 6 original chunks — spanning
   Arrays, Stack, Queue, Recursion, Sorting, Trees — got the exact same
   topic string. This silently broke gap-aware retrieval (the boost logic
   that's supposed to prioritize chunks matching a diagnosed gap can't
   distinguish between topics if every chunk shares one).

   **Fixed**: `ingestion/chunker.py` now auto-detects section headers and
   delimiters, producing 9 correctly-tagged chunks (one per topic) instead
   of 6 mistagged ones. Falls back to file-level manifest metadata
   unchanged for files that don't use this convention, so it's additive,
   not a breaking change to your manifest format.

7. **Naive BM25 tokenization.**
   `text.lower().split()` at both index-build and query time meant
   punctuation stayed attached to words (`"recursion:"` ≠ `"recursion"`),
   silently breaking exact-match retrieval on real prose.

   **Fixed**: added `retrieval/text_utils.py` with a shared regex
   tokenizer, used identically in `ingestion/build_index.py` and
   `retrieval/hybrid_retriever.py` (a mismatch between these two would
   have been just as bad as no fix at all — worth remembering if you
   touch tokenization again).

## What's verified working (actually run, not just read)

- Full ingestion pipeline on your real sample file (topic-aware chunking, BM25 build)
- BM25 retrieval ranking sanity-checked against real queries
- The complete non-RAG system: student modeling (BKT), knowledge graph
  traversal, gap analysis, IRT adaptive testing, mastery tracking,
  dashboards — 23/23 on `scripts/smoke_test.py`, before and after every fix
- FastAPI server boots clean; every route exercised live: student
  creation, knowledge graph, dashboards, assessment start/question,
  **and the rewired `/ask` endpoint through the real `TeachingAgent`**
  for both an existing student with history and a brand-new cold-start
  student
- Confirmed `ANTHROPIC_API_KEY`-absent behavior end-to-end: clean
  fallback message on startup, template-based generation throughout,
  no crashes

## Still can't be tested in this sandbox

Dense/vector retrieval (Chroma + the `sentence-transformers` embedding
model + the cross-encoder reranker) requires downloading models from
Hugging Face, which this sandbox has no network access to. The code path
is fixed and consistent with everything else, but **you need to re-run
`python scripts/run_ingestion.py` on your own machine** to rebuild
`data/index/chroma/` (deleted from this package since it referenced
stale chunk IDs from before the chunker fix) before dense retrieval will
work. BM25 alone still works right now without that step.

## To get real LLM-backed generation (optional but recommended)

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Do this before starting the server (`python -m uvicorn api.main:app`) and
`explanation_generator.py`, `question_generator.py`, and `grader.py` will
all switch from templates to real generation automatically — no other
code changes needed. Worth demoing both modes (with and without the key)
in your viva to show the graceful-degradation design explicitly.
