"""
Explanation Generator
Generates adaptive explanations based on student profile and retrieved content.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional

import sys
sys.path.append('..')

from student_model import StudentProfile, LearningStyle


class ExplanationStyle(Enum):
    """Explanation delivery styles"""
    CONCISE = "concise"                 # Brief, high-level
    DETAILED = "detailed"               # Comprehensive, thorough
    STEP_BY_STEP = "step_by_step"      # Incremental, scaffolded
    EXAMPLE_DRIVEN = "example_driven"  # Concrete examples first
    ANALOGY_BASED = "analogy_based"    # Uses metaphors and analogies
    VISUAL = "visual"                   # Emphasizes diagrams, visual descriptions
    INTERACTIVE = "interactive"         # Questions and prompts


@dataclass
class GeneratedExplanation:
    """Generated explanation with metadata"""
    content: str
    style: ExplanationStyle
    difficulty_level: str
    confidence_score: float  # 0-1, how confident the system is
    sources: List[str]  # Retrieved chunk IDs
    
    # Optional components
    examples: List[str] = None
    analogies: List[str] = None
    practice_suggestions: List[str] = None
    visual_aids_suggestions: List[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'content': self.content,
            'style': self.style.value,
            'difficulty_level': self.difficulty_level,
            'confidence_score': self.confidence_score,
            'sources': self.sources,
            'examples': self.examples or [],
            'analogies': self.analogies or [],
            'practice_suggestions': self.practice_suggestions or [],
            'visual_aids_suggestions': self.visual_aids_suggestions or []
        }


class ExplanationGenerator:
    """
    Generates personalized explanations adapted to student profile.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize with optional LLM client (Gemini, OpenAI, Anthropic, local model).
        If None, uses template-based generation.
        """
        self.llm_client = llm_client
    
    def generate(self, query: str,
                retrieved_chunks: List[Dict],
                student_profile: StudentProfile,
                concept_difficulty: str,
                current_mastery: float = 0.0,
                conversation_history: Optional[str] = None) -> GeneratedExplanation:
        """
        Generate adaptive explanation based on student and context.
        
        Args:
            query: Student's question
            retrieved_chunks: RAG results with 'text', 'metadata', 'score'
            student_profile: Student's profile
            concept_difficulty: easy/medium/hard
            current_mastery: Student's current mastery of this concept (0-1)
            conversation_history: Recent Q&A turns with this student (see
                agent/conversation_memory.py), so follow-up questions like
                "can you give another example" resolve correctly instead
                of being answered in isolation. Only used in the LLM path
                — the template fallback can't reason over prior turns.
        """
        # Determine explanation style
        style = self._select_style(student_profile, current_mastery)
        
        # Adjust difficulty if needed
        adjusted_difficulty = self._adjust_difficulty(
            concept_difficulty,
            student_profile,
            current_mastery
        )
        
        # Build context from retrieved chunks
        context = self._build_context(retrieved_chunks)
        
        # Generate explanation
        if self.llm_client:
            explanation = self._generate_with_llm(
                query, context, style, adjusted_difficulty, student_profile, conversation_history
            )
        else:
            explanation = self._generate_template_based(
                query, context, style, adjusted_difficulty
            )
        
        # Calculate confidence based on retrieval scores
        confidence = self._calculate_confidence(retrieved_chunks)
        
        # Extract sources
        sources = [chunk.get('chunk_id', '') for chunk in retrieved_chunks[:3]]
        
        # Generate supplementary materials
        examples = self._generate_examples(context, style) if student_profile.prefers_examples else None
        analogies = self._generate_analogies(context) if style == ExplanationStyle.ANALOGY_BASED else None
        practice = self._suggest_practice(query, context) if student_profile.prefers_practice else None
        visual = self._suggest_visual_aids(context) if student_profile.primary_learning_style == LearningStyle.VISUAL else None
        
        return GeneratedExplanation(
            content=explanation,
            style=style,
            difficulty_level=adjusted_difficulty,
            confidence_score=confidence,
            sources=sources,
            examples=examples,
            analogies=analogies,
            practice_suggestions=practice,
            visual_aids_suggestions=visual
        )
    
    def _select_style(self, student_profile: StudentProfile,
                     current_mastery: float) -> ExplanationStyle:
        """Select explanation style based on student profile"""
        
        # If struggling, use step-by-step
        if current_mastery < 0.3 or student_profile.should_use_scaffolding():
            return ExplanationStyle.STEP_BY_STEP
        
        # Match to learning style
        style_map = {
            LearningStyle.VISUAL: ExplanationStyle.VISUAL,
            LearningStyle.AUDITORY: ExplanationStyle.DETAILED,
            LearningStyle.READING_WRITING: ExplanationStyle.DETAILED,
            LearningStyle.KINESTHETIC: ExplanationStyle.INTERACTIVE
        }
        
        primary_style = style_map.get(
            student_profile.primary_learning_style,
            ExplanationStyle.DETAILED
        )
        
        # Adjust based on preferences
        if student_profile.prefers_examples:
            return ExplanationStyle.EXAMPLE_DRIVEN
        
        # Adjust based on cognitive profile
        if student_profile.cognitive_profile.abstract_reasoning > 0.7 and current_mastery > 0.5:
            return ExplanationStyle.CONCISE
        
        return primary_style
    
    def _adjust_difficulty(self, concept_difficulty: str,
                          student_profile: StudentProfile,
                          current_mastery: float) -> str:
        """Adjust explanation difficulty to student level"""
        
        # If student is struggling, simplify
        if current_mastery < 0.3:
            return "easy"
        
        # If working memory is low, simplify
        if student_profile.cognitive_profile.working_memory < 0.4:
            difficulty_order = ['easy', 'medium', 'hard']
            idx = difficulty_order.index(concept_difficulty)
            if idx > 0:
                return difficulty_order[idx - 1]
        
        # If advanced and mastering, can increase
        if (student_profile.cognitive_profile.abstract_reasoning > 0.7 and
            current_mastery > 0.7):
            return concept_difficulty
        
        return concept_difficulty
    
    def _build_context(self, retrieved_chunks: List[Dict]) -> str:
        """Build context string from retrieved chunks"""
        if not retrieved_chunks:
            return ""
        
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks[:5], 1):
            text = chunk.get('text', '')
            metadata = chunk.get('metadata', {})
            source = metadata.get('source_file', 'unknown')
            
            context_parts.append(f"[Source {i} - {source}]\n{text}\n")
        
        return "\n".join(context_parts)
    
    def _generate_with_llm(self, query: str, context: str,
                          style: ExplanationStyle, difficulty: str,
                          student_profile: StudentProfile,
                          conversation_history: Optional[str] = None) -> str:
        """Generate explanation using LLM"""
        
        # Build prompt based on style
        style_instructions = {
            ExplanationStyle.CONCISE: "Provide a brief, high-level explanation in 2-3 sentences.",
            ExplanationStyle.DETAILED: "Provide a comprehensive, thorough explanation with all important details.",
            ExplanationStyle.STEP_BY_STEP: "Break down the explanation into clear, numbered steps. Explain each step thoroughly before moving to the next.",
            ExplanationStyle.EXAMPLE_DRIVEN: "Start with 2-3 concrete examples, then explain the general concept.",
            ExplanationStyle.ANALOGY_BASED: "Use analogies and metaphors to explain the concept in terms of familiar experiences.",
            ExplanationStyle.VISUAL: "Describe visual representations, diagrams, or spatial relationships. Use visual language.",
            ExplanationStyle.INTERACTIVE: "Pose questions and guide the student through discovery. Include prompts for reflection."
        }
        
        history_block = ""
        if conversation_history:
            history_block = f"""

Recent conversation with this student (for context and continuity —
use it to resolve follow-up references like "that", "another one", or
"instead", and avoid repeating what you already covered unless the
student is asking you to review it):
{conversation_history}"""

        system_prompt = f"""You are an adaptive tutoring system explaining concepts to a student.

Student Profile:
- Learning Style: {student_profile.primary_learning_style.value}
- Prefers Examples: {student_profile.prefers_examples}
- Needs Step-by-Step: {student_profile.prefers_step_by_step}
- Working Memory: {student_profile.cognitive_profile.working_memory:.1f}/1.0
- Abstract Reasoning: {student_profile.cognitive_profile.abstract_reasoning:.1f}/1.0

Explanation Style: {style.value}
Difficulty Level: {difficulty}

Style Instruction: {style_instructions[style]}

Use the provided context from course materials to ground your explanation. Cite sources when appropriate.
If the context doesn't contain enough information, acknowledge the limitation and provide what you can.
Do not just copy sentences from the context verbatim — rewrite and explain the idea in your own words,
at the difficulty level given above, the way a good tutor would (not a search engine).{history_block}"""

        user_prompt = f"""Question: {query}

Context from course materials:
{context}

Please provide an explanation adapted to the student's profile."""

        if self.llm_client:
            try:
                response = self.llm_client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=800,
                    temperature=0.7
                )
                return response
            except Exception as e:
                # Previously this swallowed the error completely — if a real
                # GEMINI_API_KEY was set but the call failed for any reason
                # (bad key, wrong model name, quota exceeded, network issue),
                # the system silently fell back to the template extraction
                # with NO indication anywhere of what went wrong, making
                # "why am I getting raw extracted text instead of a real
                # answer" impossible to debug. Now it's logged.
                print(f"[explanation_generator] LLM generation failed ({type(e).__name__}: {e}) — falling back to template extraction.")
                return self._generate_template_based(query, context, style, difficulty, reason="call_failed")
        
        return self._generate_template_based(query, context, style, difficulty, reason="no_key")
    
    def _generate_template_based(self, query: str, context: str,
                                style: ExplanationStyle, difficulty: str,
                                reason: str = "no_key") -> str:
        """
        Generate explanation using templates (fallback, no LLM available).

        This is a HARD ceiling on quality: without a language model there
        is no real paraphrasing, simplification, or reasoning happening —
        just picking and lightly framing the most query-relevant sentences
        already present in the retrieved chunks. It will never produce the
        kind of properly synthesized, level-adapted explanation
        _generate_with_llm() does; that's expected, not a bug. Set
        GEMINI_API_KEY to get real generation (see llm/client.py).

        Previously this just did context[:500] — a blind character-count
        truncation that often cut mid-sentence and had no relationship to
        the actual question asked. This version at least scores sentences
        by relevance to the query and difficulty, so the extract is more
        targeted even though it's still extraction, not generation.

        `reason` distinguishes "no client was ever configured" from "a
        client exists but the call just failed" — these used to show the
        exact same "no LLM API key is configured" message even when a key
        genuinely was set and something else went wrong (wrong model name,
        quota, network), which was actively misleading when debugging.
        """
        if not context:
            return (f"I don't have sufficient information in the course materials "
                   f"to answer '{query}'. Please consult your textbook or instructor.")

        relevant = self._extract_relevant_sentences(context, query, max_chars=600)
        if reason == "call_failed":
            note = ("\n\n*(This is extracted directly from your course notes — a Gemini "
                    "API call was attempted but failed, so it fell back to extraction "
                    "instead of a real answer. Check the server console for the exact "
                    "error, e.g. '[explanation_generator] LLM generation failed (...)'.)*")
        else:
            note = ("\n\n*(This is extracted directly from your course notes — no LLM API "
                    "key is configured, so it can't be rewritten or simplified further. "
                    "Set GEMINI_API_KEY for a fully synthesized, level-adapted explanation.)*")

        if style == ExplanationStyle.STEP_BY_STEP:
            explanation = (
                f"Let's break this down ({difficulty} level). From your course materials:\n\n"
                f"{relevant}{note}"
            )
        elif style == ExplanationStyle.CONCISE:
            short = self._extract_relevant_sentences(context, query, max_chars=250)
            explanation = f"In brief:\n\n{short}{note}"
        else:
            explanation = (
                f"Regarding your question — \"{query}\":\n\n{relevant}{note}"
            )

        return explanation

    @staticmethod
    def _extract_relevant_sentences(context: str, query: str, max_chars: int = 600) -> str:
        """
        Splits the retrieved context into sentences and greedily keeps the
        ones with the most word overlap with the query, in their original
        order (so the extract still reads coherently), until max_chars is
        reached. Falls back to the start of the context if nothing scores
        above zero (e.g. the query is very short/generic).
        """
        import re
        sentences = re.split(r'(?<=[.!?])\s+', context.replace('\n', ' '))
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return context[:max_chars]

        query_words = set(w.lower() for w in re.findall(r'\w+', query) if len(w) > 2)
        scored = []
        for i, s in enumerate(sentences):
            s_words = set(w.lower() for w in re.findall(r'\w+', s))
            overlap = len(query_words & s_words)
            scored.append((overlap, i, s))

        if max(sc for sc, _, _ in scored) == 0:
            # Nothing scored — just take from the top of the context
            selected = sentences
        else:
            # Keep sentences with any overlap, best first, but re-sort by
            # original position afterward so the final text still flows
            top = sorted(scored, key=lambda t: t[0], reverse=True)
            keep_indices = set()
            for _, i, _ in top:
                keep_indices.add(i)
                if sum(len(sentences[j]) for j in keep_indices) > max_chars * 1.5:
                    break
            selected = [sentences[i] for i in sorted(keep_indices)]

        out = " ".join(selected)
        return out[:max_chars] + ("..." if len(out) > max_chars else "")
    
    def _calculate_confidence(self, retrieved_chunks: List[Dict]) -> float:
        """Calculate confidence score based on retrieval quality"""
        if not retrieved_chunks:
            return 0.0
        
        # Use top retrieval scores
        top_scores = [chunk.get('score', 0.0) for chunk in retrieved_chunks[:3]]
        
        if not top_scores:
            return 0.5
        
        # Average of top scores, with threshold
        avg_score = sum(top_scores) / len(top_scores)
        
        # Map to confidence: >0.7 = high, 0.5-0.7 = medium, <0.5 = low
        if avg_score > 0.7:
            return min(1.0, avg_score)
        elif avg_score > 0.5:
            return 0.6
        else:
            return 0.4
    
    def _generate_examples(self, context: str, style: ExplanationStyle) -> List[str]:
        """Extract or generate examples from context"""
        # Simple heuristic: look for "example", "for instance", "e.g."
        examples = []
        
        for line in context.split('\n'):
            if any(keyword in line.lower() for keyword in ['example', 'for instance', 'e.g.', 'such as']):
                examples.append(line.strip())
                if len(examples) >= 3:
                    break
        
        if not examples:
            examples = ["Try creating your own example to test your understanding."]
        
        return examples
    
    def _generate_analogies(self, context: str) -> List[str]:
        """Generate analogies to explain concepts"""
        # Placeholder - would use LLM for better analogies
        analogies = [
            "Think of this concept like organizing books on a shelf - similar items go together.",
            "This is similar to following a recipe - each step builds on the previous one."
        ]
        return analogies[:1]
    
    def _suggest_practice(self, query: str, context: str) -> List[str]:
        """Suggest practice activities"""
        suggestions = [
            "Try explaining this concept to someone else in your own words.",
            "Create a simple example that demonstrates this concept.",
            "Practice with similar problems to reinforce your understanding."
        ]
        return suggestions
    
    def _suggest_visual_aids(self, context: str) -> List[str]:
        """Suggest visual representations"""
        suggestions = [
            "Draw a diagram showing the relationships between components.",
            "Create a flowchart to visualize the process.",
            "Use color coding to highlight different parts of the concept."
        ]
        return suggestions[:2]
