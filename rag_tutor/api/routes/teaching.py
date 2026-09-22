"""
Teaching Routes — wired to the real TeachingAgent (retrieval + gap
analysis + pedagogy + explanation generation), not a hand-rolled
inline template.

Previously this route never touched agent/teaching_agent.py,
agent/explanation_generator.py, or agent/pedagogy_engine.py at all —
it built a simplified answer string directly in the endpoint, so the
adaptive-pedagogy layer described in ARCHITECTURE.md was effectively
dead code from the API's point of view. This version constructs a real
TeachingAgent per app lifetime and calls agent.teach(...).
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from api.store import STUDENTS, KNOWLEDGE, GRAPH, ANALYZER, TRACKER, LLM_CLIENT, DB, persist_student, persist_interaction
from student_model.knowledge_state import KnowledgeState, ConceptMastery
from student_model.interaction_log import InteractionLog, InteractionType
from retrieval.hybrid_retriever import HybridRetriever, NullRetriever
from agent.teaching_agent import TeachingAgent
from agent.explanation_generator import ExplanationGenerator
from agent.conversation_memory import get_recent_context

router = APIRouter()

# Lazy-built agent so import doesn't fail if the vector index isn't
# ready yet (e.g. ingestion hasn't been run, or the embedding model
# can't be downloaded in this environment).
_agent: Optional[TeachingAgent] = None


def _get_agent() -> TeachingAgent:
    global _agent
    if _agent is not None:
        return _agent

    bm25 = ROOT / "data" / "index" / "bm25.pkl"

    # Previously this required BOTH chroma/ AND bm25.pkl to exist before
    # even trying HybridRetriever, and HybridRetriever itself used to abort
    # entirely if the embedding/reranker model download failed for any
    # reason — discarding a perfectly good BM25 index in the process. Now
    # HybridRetriever degrades internally (see retrieval/hybrid_retriever.py),
    # so this only needs BM25 to exist; dense search just won't be used if
    # the vector index/models aren't available.
    retriever = None
    if bm25.exists():
        try:
            retriever = HybridRetriever(index_dir=str(ROOT / "data" / "index"))
        except Exception as e:
            print(f"[teaching] HybridRetriever load failed ({e}); using NullRetriever fallback.")
    if retriever is None:
        retriever = NullRetriever()

    explanation_generator = ExplanationGenerator(llm_client=LLM_CLIENT)

    _agent = TeachingAgent(
        retriever=retriever,
        gap_analyzer=ANALYZER,
        explanation_generator=explanation_generator,
    )
    return _agent


def invalidate_agent_cache():
    """
    Forces the next /ask or /hint call to rebuild the TeachingAgent (and
    therefore its retriever) from scratch. Call this after ingesting new
    materials — otherwise the running server keeps answering from
    whatever index existed when the first request built the cached
    agent, even after new PDFs are uploaded and the index files on disk
    are rebuilt. See api/routes/materials.py.
    """
    global _agent
    _agent = None


class AskRequest(BaseModel):
    student_id: str
    question: str
    concept_id: Optional[str] = None


@router.post("/ask")
async def ask_question(req: AskRequest):
    profile = STUDENTS.get(req.student_id)
    if not profile:
        raise HTTPException(404, "Student not found")

    knowledge = KNOWLEDGE.setdefault(
        req.student_id, KnowledgeState(student_id=req.student_id)
    )

    agent = _get_agent()
    with DB.get_session() as session:
        history = get_recent_context(session, req.student_id)

    response = agent.teach(
        student_query=req.question,
        student_profile=profile,
        student_knowledge=knowledge,
        concept_id=req.concept_id,
        conversation_history=history,
    )

    # Update mastery from this teaching interaction, same as before
    if req.concept_id:
        cm = knowledge.get_concept(req.concept_id)
        if not cm:
            concept = GRAPH.get_concept(req.concept_id)
            if concept:
                cm = ConceptMastery(
                    concept_id=req.concept_id, concept_name=concept.name,
                    subject=concept.subject, unit=concept.unit
                )
                knowledge.add_concept(cm)
        if cm:
            TRACKER.update_from_teaching(knowledge, profile, req.concept_id, response.confidence)

    profile.total_sessions += 1
    profile.last_active = datetime.utcnow()
    profile.overall_mastery = knowledge.get_overall_mastery()

    persist_student(req.student_id)
    persist_interaction(InteractionLog(
        student_id=req.student_id,
        interaction_type=InteractionType.QUESTION_ASKED,
        concept_id=req.concept_id,
        student_input=req.question,
        system_response=response.explanation.content,
        confidence_score=response.confidence,
        retrieved_chunks=response.explanation.sources or None,
    ))

    return {
        "answer": response.explanation.content,
        "explanation_style": response.explanation.style.value,
        "confidence": response.confidence,
        "requires_human_review": response.requires_human_review,
        "pedagogical_strategy": response.pedagogical_strategy.to_dict(),
        "next_steps": response.next_steps,
        "practice_problems": response.practice_problems,
        "related_concepts": response.related_concepts,
        "sources_used": len(response.explanation.sources),
    }


@router.post("/hint")
async def get_hint(student_id: str, concept_id: str, hint_level: int = 1):
    concept = GRAPH.get_concept(concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")

    profile = STUDENTS.get(student_id)
    if not profile:
        raise HTTPException(404, "Student not found")

    agent = _get_agent()
    hint = agent.provide_hint(
        student_query=f"I'm stuck on {concept.name}",
        student_profile=profile,
        concept_id=concept_id,
        hint_level=hint_level,
    )
    return {"hint": hint, "level": hint_level}
