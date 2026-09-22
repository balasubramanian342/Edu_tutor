"""
Teaching Agent
Main agent that orchestrates adaptive teaching using RAG and pedagogy.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

import sys
sys.path.append('..')

from retrieval import HybridRetriever
from student_model import StudentProfile, KnowledgeState, InteractionLog, InteractionType
from gap_analysis import GapAnalyzer
from .explanation_generator import ExplanationGenerator, GeneratedExplanation
from .pedagogy_engine import PedagogyEngine, PedagogicalStrategy


@dataclass
class TeachingResponse:
    """Complete teaching response to student query"""
    explanation: GeneratedExplanation
    pedagogical_strategy: PedagogicalStrategy
    
    # Follow-up guidance
    next_steps: List[str]
    practice_problems: List[str]
    related_concepts: List[str]
    
    # Metadata
    confidence: float
    requires_human_review: bool  # Flag low-confidence responses
    interaction_log: InteractionLog
    
    def to_dict(self) -> Dict:
        return {
            'explanation': self.explanation.to_dict(),
            'pedagogical_strategy': self.pedagogical_strategy.to_dict(),
            'next_steps': self.next_steps,
            'practice_problems': self.practice_problems,
            'related_concepts': self.related_concepts,
            'confidence': self.confidence,
            'requires_human_review': self.requires_human_review,
            'timestamp': self.interaction_log.timestamp.isoformat()
        }


class TeachingAgent:
    """
    Main adaptive teaching agent.
    Orchestrates RAG retrieval, gap analysis, explanation generation, and pedagogy.
    """
    
    def __init__(self,
                 retriever: HybridRetriever,
                 gap_analyzer: GapAnalyzer,
                 explanation_generator: ExplanationGenerator,
                 interaction_logger=None):
        """
        Initialize teaching agent.
        
        Args:
            retriever: Hybrid retrieval system
            gap_analyzer: Gap analysis engine
            explanation_generator: Explanation generator
            interaction_logger: Optional logger for interactions
        """
        self.retriever = retriever
        self.gap_analyzer = gap_analyzer
        self.explanation_generator = explanation_generator
        self.interaction_logger = interaction_logger
    
    def teach(self,
             student_query: str,
             student_profile: StudentProfile,
             student_knowledge: KnowledgeState,
             concept_id: Optional[str] = None,
             session_id: Optional[str] = None,
             conversation_history: Optional[str] = None) -> TeachingResponse:
        """
        Main teaching method. Handles a student query with full adaptation.
        
        Args:
            student_query: Student's question
            student_profile: Student profile
            student_knowledge: Student's knowledge state
            concept_id: Optional target concept ID
            session_id: Optional session identifier
            conversation_history: Recent Q&A turns with this student,
                formatted by agent/conversation_memory.py, so follow-up
                questions are answered with continuity instead of in
                isolation.
        
        Returns:
            Complete teaching response with explanation and guidance
        """
        start_time = datetime.utcnow()
        
        # Step 1: Identify target concept if not provided
        if not concept_id:
            concept_id = self._identify_concept(student_query)
        
        # Step 2: Analyze knowledge gaps
        gaps = self.gap_analyzer.analyze_for_concept(
            concept_id,
            student_knowledge,
            student_profile
        ) if concept_id else []
        
        # Determine gap-aware retrieval topic
        gap_topic = None
        if gaps:
            # Focus retrieval on the most critical gap
            gap_topic = gaps[0].concept.name
        
        # Step 3: Retrieve relevant content
        retrieved_chunks = self.retriever.retrieve(
            student_query,
            top_k=5,
            gap_topic=gap_topic
        )
        
        # Step 4: Get current mastery
        concept_mastery = student_knowledge.get_concept(concept_id) if concept_id else None
        current_mastery = concept_mastery.mastery_probability if concept_mastery else 0.0
        mastery_level = concept_mastery.mastery_level if concept_mastery else None
        recent_performance = concept_mastery.recent_success_rate if concept_mastery else 0.5
        
        # Step 5: Determine pedagogical strategy
        concept_node = self.gap_analyzer.graph.get_concept(concept_id) if concept_id else None
        concept_difficulty = concept_node.difficulty if concept_node else "medium"
        
        pedagogy = PedagogyEngine.determine_strategy(
            student_profile,
            mastery_level or 0,
            concept_difficulty,
            recent_performance
        )
        
        # Step 6: Generate adaptive explanation
        explanation = self.explanation_generator.generate(
            query=student_query,
            retrieved_chunks=retrieved_chunks,
            student_profile=student_profile,
            concept_difficulty=concept_difficulty,
            current_mastery=current_mastery,
            conversation_history=conversation_history
        )
        
        # Step 7: Generate follow-up guidance
        next_steps = self._generate_next_steps(
            gaps,
            student_knowledge,
            student_profile,
            concept_id
        )
        
        practice_problems = self._suggest_practice(
            concept_id,
            pedagogy,
            current_mastery
        )
        
        related_concepts = self._suggest_related_concepts(
            concept_id,
            student_knowledge
        ) if concept_id else []
        
        # Step 8: Quality control
        confidence = explanation.confidence_score
        requires_review = confidence < 0.5 or not retrieved_chunks
        
        # Step 9: Log interaction
        response_time = (datetime.utcnow() - start_time).total_seconds()
        
        interaction = InteractionLog(
            student_id=student_profile.student_id,
            interaction_type=InteractionType.QUESTION_ASKED,
            concept_id=concept_id,
            concept_name=concept_node.name if concept_node else None,
            student_input=student_query,
            system_response=explanation.content[:500],  # Truncate for storage
            confidence_score=confidence,
            response_time_seconds=response_time,
            retrieved_chunks=[c.get('chunk_id', '') for c in retrieved_chunks[:3]],
            retrieval_scores=[c.get('score', 0.0) for c in retrieved_chunks[:3]],
            session_id=session_id
        )
        
        if self.interaction_logger:
            self.interaction_logger.log(interaction)
        
        return TeachingResponse(
            explanation=explanation,
            pedagogical_strategy=pedagogy,
            next_steps=next_steps,
            practice_problems=practice_problems,
            related_concepts=related_concepts,
            confidence=confidence,
            requires_human_review=requires_review,
            interaction_log=interaction
        )
    
    def provide_hint(self,
                    student_query: str,
                    student_profile: StudentProfile,
                    concept_id: str,
                    hint_level: int = 1) -> str:
        """
        Provide a progressive hint (Socratic method).
        
        Args:
            student_query: What student is stuck on
            student_profile: Student profile
            concept_id: Concept being learned
            hint_level: 1 (minimal) to 3 (substantial)
        """
        
        concept = self.gap_analyzer.graph.get_concept(concept_id)
        
        if hint_level == 1:
            # Minimal hint - redirect attention
            return f"Think about the prerequisites for {concept.name}. What do you know about those?"
        
        elif hint_level == 2:
            # Moderate hint - provide structure
            prereqs = self.gap_analyzer.graph.get_prerequisites(concept_id)
            if prereqs:
                return (f"To understand {concept.name}, you'll need to recall "
                       f"{prereqs[0].name}. How does that concept relate to your question?")
            return "Break the problem down into smaller steps. What's the first thing you need to figure out?"
        
        else:  # hint_level == 3
            # Substantial hint - provide partial solution
            retrieved = self.retriever.retrieve(student_query, top_k=2)
            if retrieved:
                context = retrieved[0].get('text', '')[:200]
                return f"Here's a relevant passage from the materials: {context}... How does this help?"
            return "Let me guide you through the first step..."
    
    def _identify_concept(self, query: str) -> Optional[str]:
        """
        Identify which concept the query is about.
        Uses keyword matching and retrieval.
        """
        # Retrieve relevant chunks
        chunks = self.retriever.retrieve(query, top_k=3)
        
        if not chunks:
            return None
        
        # Get concept from top chunk's metadata
        top_chunk = chunks[0]
        metadata = top_chunk.get('metadata', {})
        
        # Try to extract concept_id or infer from topic
        concept_id = metadata.get('concept_id')
        if concept_id:
            return concept_id
        
        # Fallback: infer from topic
        topic = metadata.get('topic', '')
        # Would need concept name -> ID mapping
        # For now, return topic as proxy
        return topic
    
    def _generate_next_steps(self,
                            gaps: List,
                            student_knowledge: KnowledgeState,
                            student_profile: StudentProfile,
                            concept_id: Optional[str]) -> List[str]:
        """Generate recommended next steps for student"""
        
        next_steps = []
        
        # Address gaps first
        if gaps:
            top_gap = gaps[0]
            next_steps.append(f"Review {top_gap.concept.name} to strengthen your foundation")
        
        # Suggest practice if ready
        if concept_id:
            concept_mastery = student_knowledge.get_concept(concept_id)
            if concept_mastery and concept_mastery.mastery_level.value >= 2:
                next_steps.append("Practice applying this concept with additional problems")
        
        # Suggest next concept if current is mastered
        if not gaps and concept_id:
            next_concept = self.gap_analyzer.suggest_next_learning_target(
                student_knowledge,
                student_profile
            )
            if next_concept:
                next_steps.append(f"You're ready to learn {next_concept.name}")
        
        if not next_steps:
            next_steps.append("Continue practicing and reviewing key concepts")
        
        return next_steps[:3]  # Top 3
    
    def _suggest_practice(self,
                         concept_id: Optional[str],
                         pedagogy: PedagogicalStrategy,
                         current_mastery: float) -> List[str]:
        """Suggest practice problems based on mastery level"""
        
        if not concept_id:
            return ["Review the course materials and try the practice problems provided."]
        
        practice = []
        
        # Adjust based on mastery
        if current_mastery < 0.5:
            practice.append("Start with guided practice problems with solutions")
            practice.append("Work through examples step-by-step")
        elif current_mastery < 0.7:
            practice.append("Try practice problems independently")
            practice.append("Check your work against provided solutions")
        else:
            practice.append("Challenge yourself with advanced problems")
            practice.append("Try explaining the concept to a peer")
        
        return practice
    
    def _suggest_related_concepts(self,
                                 concept_id: str,
                                 student_knowledge: KnowledgeState) -> List[str]:
        """Suggest related concepts to explore"""
        
        from knowledge_graph import RelationType
        
        related = self.gap_analyzer.graph.get_related_concepts(
            concept_id,
            RelationType.RELATED_TO
        )
        
        # Filter to concepts student might be ready for
        mastered_ids = {
            c.concept_id for c in student_knowledge.concepts.values()
            if c.mastery_level.value >= 4
        }
        
        suggestions = []
        for concept in related[:5]:
            prereqs = self.gap_analyzer.graph.get_prerequisites(concept.concept_id)
            prereq_ids = {p.concept_id for p in prereqs}
            
            if prereq_ids.issubset(mastered_ids):
                suggestions.append(concept.name)
        
        return suggestions[:3]
