"""
agent/conversation_memory.py

Gives the teaching agent short-term conversational memory, backed by
the interaction_logs table that was already being written to (via
persist_interaction() in api/store.py) but never read back. Without
this, every question was answered in total isolation — "can you give
another example" or "what about linked lists instead" had no way to
know what "another" or "instead" referred to, because nothing was ever
fed the previous turn.

This is intentionally simple (recency-window, not vector-indexed
long-term memory): it pulls the student's last few Q&A turns from the
database and formats them into a short text block that gets prepended
to the LLM prompt in explanation_generator.py. That's enough for
natural follow-up questions within a session; it is NOT a semantic
memory search over a student's entire history — see
FEATURES_AND_ROADMAP.md if you want to extend it into one (e.g. by
embedding + indexing past interactions the same way course materials
are indexed, and retrieving relevant past turns instead of just the
most recent ones).
"""

from typing import Optional

from database.repository import load_recent_interactions


def get_recent_context(session, student_id: str, limit: int = 4) -> Optional[str]:
    """
    Returns the student's last `limit` question/answer turns formatted
    for a prompt, most-recent-last (chronological order reads more
    naturally to an LLM than reverse-chronological). Returns None if
    there's no history yet (e.g. the student's first question), so
    callers can skip the "recent conversation" section entirely rather
    than showing an empty block.
    """
    rows = load_recent_interactions(session, student_id, limit=limit)
    qa_rows = [
        r for r in rows
        if r.interaction_type == "question_asked" and r.student_input and r.system_response
    ]
    if not qa_rows:
        return None

    qa_rows.reverse()  # DB query is most-recent-first; flip to chronological
    lines = []
    for r in qa_rows:
        # Trim the stored answer — the full explanation isn't needed for
        # context, just enough for the model to know what was already
        # covered and avoid repeating itself verbatim.
        answer_preview = r.system_response[:280]
        if len(r.system_response) > 280:
            answer_preview += "..."
        lines.append(f"Student asked: {r.student_input}\nYou answered: {answer_preview}")

    return "\n\n".join(lines)
