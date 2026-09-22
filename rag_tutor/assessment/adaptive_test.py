"""
Adaptive Testing
Implements adaptive testing using Item Response Theory principles.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
import math

import sys
sys.path.append('..')

from knowledge_graph import ConceptGraph
from student_model import StudentProfile, KnowledgeState
from .question_generator import QuestionGenerator, Question
from .grader import AutoGrader, GradingResult


@dataclass
class TestSession:
    """Active adaptive test session"""
    session_id: str
    student_id: str
    test_type: str  # "diagnostic", "formative", "summative"
    
    concepts_being_tested: List[str]
    questions_asked: List[Question] = field(default_factory=list)
    responses: List[Dict] = field(default_factory=list)
    
    # Adaptive tracking
    current_ability_estimate: float = 0.5  # Theta parameter in IRT
    confidence_in_estimate: float = 0.0
    
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            'session_id': self.session_id,
            'student_id': self.student_id,
            'test_type': self.test_type,
            'concepts_tested': self.concepts_being_tested,
            'questions_count': len(self.questions_asked),
            'responses_count': len(self.responses),
            'current_ability_estimate': self.current_ability_estimate,
            'started_at': self.started_at.isoformat(),
            'ended_at': self.ended_at.isoformat() if self.ended_at else None
        }


@dataclass
class TestResult:
    """Final test results with detailed analytics"""
    session_id: str
    student_id: str
    
    total_questions: int
    correct_answers: int
    total_points_earned: float
    total_points_possible: float
    
    score_percentage: float
    ability_estimate: float  # Final theta
    
    # Per-concept breakdown
    concept_scores: Dict[str, Dict] = field(default_factory=dict)
    
    # Recommendations
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommended_review: List[str] = field(default_factory=list)
    
    completed_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            'session_id': self.session_id,
            'student_id': self.student_id,
            'total_questions': self.total_questions,
            'correct_answers': self.correct_answers,
            'total_points_earned': self.total_points_earned,
            'total_points_possible': self.total_points_possible,
            'score_percentage': self.score_percentage,
            'ability_estimate': self.ability_estimate,
            'concept_scores': self.concept_scores,
            'strengths': self.strengths,
            'weaknesses': self.weaknesses,
            'recommended_review': self.recommended_review,
            'completed_at': self.completed_at.isoformat()
        }


class AdaptiveTest:
    """
    Adaptive testing engine using Item Response Theory.
    Adjusts difficulty based on student responses.
    """
    
    def __init__(self,
                 question_generator: QuestionGenerator,
                 grader: AutoGrader,
                 knowledge_graph: ConceptGraph):
        self.question_generator = question_generator
        self.grader = grader
        self.knowledge_graph = knowledge_graph
    
    def start_diagnostic_test(self,
                             student_profile: StudentProfile,
                             subject: str,
                             max_questions: int = 15) -> TestSession:
        """
        Start diagnostic test to assess baseline knowledge.
        
        Args:
            student_profile: Student taking the test
            subject: Subject area to diagnose
            max_questions: Maximum questions to ask
        """
        
        # Get all concepts in subject
        concepts = [c for c in self.knowledge_graph.concepts.values() 
                   if c.subject == subject]
        
        session = TestSession(
            session_id=f"DIAG_{student_profile.student_id}_{datetime.utcnow().timestamp()}",
            student_id=student_profile.student_id,
            test_type="diagnostic",
            concepts_being_tested=[c.concept_id for c in concepts],
            current_ability_estimate=0.5  # Start at medium difficulty
        )
        
        return session
    
    def get_next_question(self,
                         session: TestSession,
                         student_profile: StudentProfile) -> Optional[Question]:
        """
        Generate next adaptive question based on current ability estimate.
        Uses Item Response Theory to select optimal difficulty.
        
        Args:
            session: Current test session
            student_profile: Student profile
        
        Returns:
            Next question, or None if test should end
        """
        
        # Check stopping criteria
        if self._should_stop_test(session):
            return None
        
        # Select concept to test
        concept_id = self._select_next_concept(session)
        if not concept_id:
            return None
        
        concept = self.knowledge_graph.get_concept(concept_id)
        
        # Calculate target difficulty based on ability estimate
        target_difficulty = self._map_ability_to_difficulty(session.current_ability_estimate)
        
        # Select appropriate Bloom level
        bloom_level = self._select_bloom_level(session, concept_id)
        
        # Generate question
        question = self.question_generator.generate_for_concept(
            concept,
            bloom_level,
            difficulty=target_difficulty
        )
        
        session.questions_asked.append(question)
        
        return question
    
    def submit_answer(self,
                     session: TestSession,
                     question: Question,
                     student_answer: any) -> GradingResult:
        """
        Submit and grade an answer, update ability estimate.
        
        Args:
            session: Current test session
            question: Question being answered
            student_answer: Student's response
        
        Returns:
            Grading result
        """
        
        # Grade the answer
        result = self.grader.grade(question, student_answer)
        
        # Record response
        session.responses.append({
            'question_id': question.question_id,
            'concept_id': question.concept_id,
            'student_answer': student_answer,
            'grading_result': result.to_dict(),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Update ability estimate using IRT
        self._update_ability_estimate(session, question, result.is_correct)
        
        return result
    
    def end_test(self,
                session: TestSession,
                student_knowledge: KnowledgeState) -> TestResult:
        """
        End test and generate comprehensive results.
        
        Args:
            session: Test session to end
            student_knowledge: Student's knowledge state to update
        
        Returns:
            Final test results with recommendations
        """
        
        session.ended_at = datetime.utcnow()
        
        # Calculate overall statistics
        total_questions = len(session.responses)
        correct_count = sum(1 for r in session.responses 
                          if r['grading_result']['is_correct'])
        
        total_points = sum(r['grading_result']['points_earned'] 
                          for r in session.responses)
        possible_points = sum(r['grading_result']['points_possible'] 
                             for r in session.responses)
        
        score_pct = (total_points / possible_points * 100) if possible_points > 0 else 0
        
        # Calculate per-concept scores
        concept_scores = self._calculate_concept_scores(session)
        
        # Identify strengths and weaknesses
        strengths, weaknesses = self._identify_strengths_weaknesses(concept_scores)
        
        # Generate recommendations
        recommended_review = self._generate_recommendations(weaknesses, concept_scores)
        
        result = TestResult(
            session_id=session.session_id,
            student_id=session.student_id,
            total_questions=total_questions,
            correct_answers=correct_count,
            total_points_earned=total_points,
            total_points_possible=possible_points,
            score_percentage=score_pct,
            ability_estimate=session.current_ability_estimate,
            concept_scores=concept_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            recommended_review=recommended_review
        )
        
        # Update student knowledge state based on test results
        self._update_knowledge_state(session, student_knowledge)
        
        return result
    
    def _should_stop_test(self, session: TestSession) -> bool:
        """Determine if test should end"""
        
        # Maximum questions reached
        if len(session.questions_asked) >= 20:
            return True
        
        # High confidence in ability estimate (for adaptive tests)
        if (session.test_type == "diagnostic" and 
            session.confidence_in_estimate > 0.9 and
            len(session.questions_asked) >= 10):
            return True
        
        # All concepts tested sufficiently
        if session.test_type == "formative":
            min_per_concept = 2
            concept_counts = {}
            for q in session.questions_asked:
                concept_counts[q.concept_id] = concept_counts.get(q.concept_id, 0) + 1
            
            if all(count >= min_per_concept for count in concept_counts.values()):
                return True
        
        return False
    
    def _select_next_concept(self, session: TestSession) -> Optional[str]:
        """Select which concept to test next"""
        
        # Count questions per concept
        concept_counts = {}
        for q in session.questions_asked:
            concept_counts[q.concept_id] = concept_counts.get(q.concept_id, 0) + 1
        
        # For diagnostic, cover all concepts
        if session.test_type == "diagnostic":
            # Find least-tested concept
            for concept_id in session.concepts_being_tested:
                if concept_counts.get(concept_id, 0) == 0:
                    return concept_id
            
            # All tested at least once, test least-tested
            least_tested = min(session.concepts_being_tested,
                             key=lambda c: concept_counts.get(c, 0))
            return least_tested
        
        # For formative, can focus on areas of uncertainty
        return session.concepts_being_tested[0] if session.concepts_being_tested else None
    
    def _select_bloom_level(self, session: TestSession, concept_id: str) -> int:
        """Select Bloom level for next question"""
        
        # Start with lower levels, progress based on performance
        if len(session.responses) < 3:
            return 2  # Understand
        
        # Check recent performance on this concept
        concept_responses = [r for r in session.responses 
                           if r['concept_id'] == concept_id]
        
        if not concept_responses:
            return 2
        
        recent_correct = sum(1 for r in concept_responses[-3:] 
                           if r['grading_result']['is_correct'])
        
        if recent_correct >= 2:
            return 4  # Analyze
        elif recent_correct >= 1:
            return 3  # Apply
        else:
            return 2  # Understand
    
    def _map_ability_to_difficulty(self, ability: float) -> str:
        """Map ability estimate to difficulty level"""
        if ability < 0.4:
            return "easy"
        elif ability < 0.7:
            return "medium"
        else:
            return "hard"
    
    def _update_ability_estimate(self, session: TestSession,
                                question: Question, was_correct: bool):
        """
        Update ability estimate using simplified IRT.
        
        Uses 1-parameter logistic model (Rasch model).
        """
        
        # Question difficulty (normalized to -3 to +3 scale)
        difficulty_map = {"easy": -1.0, "medium": 0.0, "hard": 1.0}
        item_difficulty = difficulty_map[question.difficulty]
        
        # Current ability (theta)
        theta = (session.current_ability_estimate - 0.5) * 6  # Map 0-1 to -3 to +3
        
        # Probability of correct response given ability
        prob_correct = 1 / (1 + math.exp(-(theta - item_difficulty)))
        
        # Update theta based on response
        learning_rate = 0.2
        
        if was_correct:
            # Increase ability estimate if question was hard for current ability
            if prob_correct < 0.7:
                theta += learning_rate * (1 - prob_correct)
        else:
            # Decrease ability estimate if question should have been easy
            if prob_correct > 0.3:
                theta -= learning_rate * prob_correct
        
        # Map back to 0-1 scale
        session.current_ability_estimate = max(0.0, min(1.0, theta / 6 + 0.5))
        
        # Update confidence (increases with more questions)
        session.confidence_in_estimate = min(1.0, len(session.responses) / 15)
    
    def _calculate_concept_scores(self, session: TestSession) -> Dict[str, Dict]:
        """Calculate performance score for each concept"""
        
        concept_data = {}
        
        for response in session.responses:
            concept_id = response['concept_id']
            result = response['grading_result']
            
            if concept_id not in concept_data:
                concept = self.knowledge_graph.get_concept(concept_id)
                concept_data[concept_id] = {
                    'concept_name': concept.name if concept else concept_id,
                    'questions': 0,
                    'correct': 0,
                    'points_earned': 0.0,
                    'points_possible': 0.0
                }
            
            data = concept_data[concept_id]
            data['questions'] += 1
            if result['is_correct']:
                data['correct'] += 1
            data['points_earned'] += result['points_earned']
            data['points_possible'] += result['points_possible']
        
        # Calculate percentages
        for data in concept_data.values():
            if data['points_possible'] > 0:
                data['score_percentage'] = (data['points_earned'] / 
                                          data['points_possible'] * 100)
            else:
                data['score_percentage'] = 0
            
            data['mastery_level'] = self._score_to_mastery_level(data['score_percentage'])
        
        return concept_data
    
    def _score_to_mastery_level(self, score_pct: float) -> str:
        """Convert score to mastery level description"""
        if score_pct >= 90:
            return "mastered"
        elif score_pct >= 75:
            return "proficient"
        elif score_pct >= 60:
            return "approaching"
        elif score_pct >= 40:
            return "developing"
        else:
            return "beginning"
    
    def _identify_strengths_weaknesses(self, concept_scores: Dict) -> tuple:
        """Identify student's strengths and weaknesses"""
        
        strengths = []
        weaknesses = []
        
        for concept_id, data in concept_scores.items():
            if data['score_percentage'] >= 80:
                strengths.append(data['concept_name'])
            elif data['score_percentage'] < 60:
                weaknesses.append(data['concept_name'])
        
        return strengths[:5], weaknesses[:5]  # Top 5 each
    
    def _generate_recommendations(self, weaknesses: List[str],
                                 concept_scores: Dict) -> List[str]:
        """Generate study recommendations"""
        
        recommendations = []
        
        if weaknesses:
            recommendations.append(f"Review these concepts: {', '.join(weaknesses)}")
        
        # Find concepts that need more practice
        for data in concept_scores.values():
            if 50 <= data['score_percentage'] < 70:
                recommendations.append(
                    f"Practice more problems on {data['concept_name']}"
                )
        
        return recommendations[:5]
    
    def _update_knowledge_state(self, session: TestSession,
                               student_knowledge: KnowledgeState):
        """Update student's knowledge state based on test results"""
        
        for response in session.responses:
            concept_id = response['concept_id']
            was_correct = response['grading_result']['is_correct']
            question_difficulty = response.get('difficulty', 'medium')
            
            student_knowledge.update_concept(concept_id, was_correct, question_difficulty)
