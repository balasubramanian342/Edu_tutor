"""
Auto Grader
Automated grading for different question types with feedback generation.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Dict
from datetime import datetime
import re

import sys
sys.path.append('..')

from .question_generator import Question, QuestionType


@dataclass
class GradingResult:
    """Result of grading a student response"""
    question_id: str
    is_correct: bool
    points_earned: float
    points_possible: float
    
    # Feedback
    feedback: str
    detailed_feedback: Optional[str] = None
    
    # Analysis
    student_answer: Any = None
    correct_answer: Any = None
    partial_credit_breakdown: Optional[Dict[str, float]] = None
    
    # Metadata
    grading_method: str = "automatic"  # "automatic", "rubric", "manual_review"
    confidence: float = 1.0  # How confident the grader is (0-1)
    graded_at: datetime = None
    
    def __post_init__(self):
        if self.graded_at is None:
            self.graded_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        return {
            'question_id': self.question_id,
            'is_correct': self.is_correct,
            'points_earned': self.points_earned,
            'points_possible': self.points_possible,
            'feedback': self.feedback,
            'detailed_feedback': self.detailed_feedback,
            'grading_method': self.grading_method,
            'confidence': self.confidence,
            'graded_at': self.graded_at.isoformat()
        }


class AutoGrader:
    """
    Automated grading system for various question types.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize grader with optional LLM for subjective questions.
        
        Args:
            llm_client: Optional LLM for grading open-ended responses
        """
        self.llm_client = llm_client
    
    def grade(self, question: Question, student_answer: Any) -> GradingResult:
        """
        Grade a student's answer to a question.
        
        Args:
            question: The question being answered
            student_answer: Student's response
        
        Returns:
            GradingResult with score and feedback
        """
        
        # Route to appropriate grading method
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            return self._grade_multiple_choice(question, student_answer)
        
        elif question.question_type == QuestionType.TRUE_FALSE:
            return self._grade_true_false(question, student_answer)
        
        elif question.question_type == QuestionType.FILL_IN_BLANK:
            return self._grade_fill_in_blank(question, student_answer)
        
        elif question.question_type in [QuestionType.SHORT_ANSWER, QuestionType.ESSAY]:
            return self._grade_text_response(question, student_answer)
        
        elif question.question_type in [QuestionType.CODE_COMPLETION, 
                                       QuestionType.CODE_DEBUGGING,
                                       QuestionType.CODE_FROM_SCRATCH]:
            return self._grade_code_response(question, student_answer)
        
        elif question.question_type == QuestionType.PROBLEM_SOLVING:
            return self._grade_problem_solving(question, student_answer)
        
        else:
            return GradingResult(
                question_id=question.question_id,
                is_correct=False,
                points_earned=0,
                points_possible=question.points,
                feedback="Unable to grade this question type automatically.",
                grading_method="manual_review",
                confidence=0.0
            )
    
    def _grade_multiple_choice(self, question: Question, student_answer: Any) -> GradingResult:
        """Grade multiple choice question"""
        
        if student_answer is None:
            return GradingResult(
                question_id=question.question_id,
                is_correct=False,
                points_earned=0,
                points_possible=question.points,
                feedback="No answer provided.",
                student_answer=student_answer,
                correct_answer=question.correct_answer
            )
        
        # Normalize answers for comparison
        student_ans = str(student_answer).strip().lower()
        correct_ans = str(question.correct_answer).strip().lower()
        
        is_correct = student_ans == correct_ans
        
        # Generate feedback
        if is_correct:
            feedback = "Correct!"
            detailed = "Your answer matches the correct choice."
        else:
            feedback = "Incorrect."
            detailed = f"The correct answer is: {question.correct_answer}"
        
        return GradingResult(
            question_id=question.question_id,
            is_correct=is_correct,
            points_earned=question.points if is_correct else 0,
            points_possible=question.points,
            feedback=feedback,
            detailed_feedback=detailed,
            student_answer=student_answer,
            correct_answer=question.correct_answer,
            confidence=1.0
        )
    
    def _grade_true_false(self, question: Question, student_answer: Any) -> GradingResult:
        """Grade true/false question"""
        
        if student_answer is None:
            return GradingResult(
                question_id=question.question_id,
                is_correct=False,
                points_earned=0,
                points_possible=question.points,
                feedback="No answer provided."
            )
        
        # Normalize to boolean
        if isinstance(student_answer, bool):
            student_bool = student_answer
        else:
            student_str = str(student_answer).strip().lower()
            student_bool = student_str in ['true', 't', 'yes', 'y', '1']
        
        correct_bool = question.correct_answer
        if not isinstance(correct_bool, bool):
            correct_bool = str(correct_bool).strip().lower() in ['true', 't', 'yes', 'y', '1']
        
        is_correct = student_bool == correct_bool
        
        feedback = "Correct!" if is_correct else f"Incorrect. The answer is {correct_bool}."
        
        return GradingResult(
            question_id=question.question_id,
            is_correct=is_correct,
            points_earned=question.points if is_correct else 0,
            points_possible=question.points,
            feedback=feedback,
            student_answer=student_answer,
            correct_answer=question.correct_answer,
            confidence=1.0
        )
    
    def _grade_fill_in_blank(self, question: Question, student_answer: Any) -> GradingResult:
        """Grade fill-in-the-blank with fuzzy matching"""
        
        if not student_answer:
            return GradingResult(
                question_id=question.question_id,
                is_correct=False,
                points_earned=0,
                points_possible=question.points,
                feedback="No answer provided."
            )
        
        student_ans = str(student_answer).strip().lower()
        correct_ans = str(question.correct_answer).strip().lower()
        
        # Exact match
        if student_ans == correct_ans:
            return GradingResult(
                question_id=question.question_id,
                is_correct=True,
                points_earned=question.points,
                points_possible=question.points,
                feedback="Correct!",
                confidence=1.0
            )
        
        # Fuzzy match (handles minor typos)
        similarity = self._calculate_similarity(student_ans, correct_ans)
        
        if similarity > 0.9:  # Very close
            is_correct = True
            points = question.points
            feedback = "Correct! (minor spelling variation accepted)"
        elif similarity > 0.7:  # Partially correct
            is_correct = False
            points = question.points * 0.5
            feedback = f"Partially correct. Expected: {question.correct_answer}"
        else:
            is_correct = False
            points = 0
            feedback = f"Incorrect. Expected: {question.correct_answer}"
        
        return GradingResult(
            question_id=question.question_id,
            is_correct=is_correct,
            points_earned=points,
            points_possible=question.points,
            feedback=feedback,
            student_answer=student_answer,
            correct_answer=question.correct_answer,
            confidence=0.8 if similarity > 0.7 else 1.0
        )
    
    def _grade_text_response(self, question: Question, student_answer: str) -> GradingResult:
        """Grade text responses (short answer, essay)"""
        
        if not student_answer or not student_answer.strip():
            return GradingResult(
                question_id=question.question_id,
                is_correct=False,
                points_earned=0,
                points_possible=question.points,
                feedback="No answer provided."
            )
        
        # If LLM available, use it for grading
        if self.llm_client and question.rubric:
            return self._grade_with_llm(question, student_answer)
        
        # Otherwise, use keyword-based scoring
        return self._grade_text_keywords(question, student_answer)
    
    def _grade_text_keywords(self, question: Question, student_answer: str) -> GradingResult:
        """Grade text using keyword matching (fallback method)"""
        
        # Extract keywords from correct answer or sample answer
        keywords = []
        if question.sample_answer:
            keywords = self._extract_keywords(question.sample_answer)
        elif question.correct_answer:
            keywords = self._extract_keywords(str(question.correct_answer))
        
        if not keywords:
            # Can't auto-grade without keywords
            return GradingResult(
                question_id=question.question_id,
                is_correct=False,
                points_earned=0,
                points_possible=question.points,
                feedback="This answer requires manual review.",
                grading_method="manual_review",
                confidence=0.0
            )
        
        # Count keyword matches
        answer_lower = student_answer.lower()
        matches = sum(1 for kw in keywords if kw.lower() in answer_lower)
        match_ratio = matches / len(keywords) if keywords else 0
        
        # Score based on keyword coverage
        if match_ratio >= 0.7:
            points = question.points
            feedback = "Good answer! Covers key concepts."
            is_correct = True
        elif match_ratio >= 0.5:
            points = question.points * 0.75
            feedback = "Partially correct. Consider including more key concepts."
            is_correct = False
        elif match_ratio >= 0.3:
            points = question.points * 0.5
            feedback = "Incomplete answer. Missing several key concepts."
            is_correct = False
        else:
            points = question.points * 0.25
            feedback = "Answer does not adequately address the question."
            is_correct = False
        
        return GradingResult(
            question_id=question.question_id,
            is_correct=is_correct,
            points_earned=points,
            points_possible=question.points,
            feedback=feedback,
            detailed_feedback=f"Key concepts covered: {int(match_ratio * 100)}%",
            confidence=0.6  # Lower confidence for keyword matching
        )
    
    def _grade_with_llm(self, question: Question, student_answer: str) -> GradingResult:
        """Grade using LLM with rubric"""
        
        rubric_text = "\n".join([f"- {k}: {v}" for k, v in question.rubric.items()])
        
        prompt = f"""Grade this student answer according to the rubric.

Question: {question.prompt}

Sample Answer: {question.sample_answer or 'Not provided'}

Rubric:
{rubric_text}

Student Answer: {student_answer}

Provide a grade from 0 to {question.points} and constructive feedback.
Return JSON format:
{{
    "points": <number>,
    "is_correct": <boolean>,
    "feedback": "<brief feedback>",
    "detailed_feedback": "<specific strengths and areas for improvement>"
}}"""
        
        try:
            if self.llm_client:
                import json
                response = self.llm_client.generate(
                    system_prompt="You are an educational grader providing fair, constructive feedback.",
                    user_prompt=prompt,
                    temperature=0.3,
                    max_tokens=300
                )
                
                data = json.loads(response)
                
                return GradingResult(
                    question_id=question.question_id,
                    is_correct=data['is_correct'],
                    points_earned=float(data['points']),
                    points_possible=question.points,
                    feedback=data['feedback'],
                    detailed_feedback=data.get('detailed_feedback'),
                    grading_method="rubric",
                    confidence=0.85
                )
        except Exception as e:
            print(f"LLM grading failed: {e}")
        
        # Fallback
        return self._grade_text_keywords(question, student_answer)
    
    def _grade_code_response(self, question: Question, student_code: str) -> GradingResult:
        """Grade code submissions"""
        
        if not student_code or not student_code.strip():
            return GradingResult(
                question_id=question.question_id,
                is_correct=False,
                points_earned=0,
                points_possible=question.points,
                feedback="No code provided."
            )
        
        # In production, would run test cases
        # For now, use heuristics
        
        # Check for syntax errors (basic)
        has_syntax_error = self._check_syntax_errors(student_code)
        
        if has_syntax_error:
            return GradingResult(
                question_id=question.question_id,
                is_correct=False,
                points_earned=0,
                points_possible=question.points,
                feedback="Code contains syntax errors. Please fix and resubmit.",
                confidence=0.9
            )
        
        # Placeholder: would run actual test cases
        # For now, give partial credit
        return GradingResult(
            question_id=question.question_id,
            is_correct=False,
            points_earned=question.points * 0.5,
            points_possible=question.points,
            feedback="Code submission received. Manual review required for full grading.",
            grading_method="manual_review",
            confidence=0.5
        )
    
    def _grade_problem_solving(self, question: Question, student_answer: str) -> GradingResult:
        """Grade problem-solving questions"""
        # Similar to text response but may involve steps
        return self._grade_text_response(question, student_answer)
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity (Levenshtein distance normalized)"""
        if str1 == str2:
            return 1.0
        
        # Simple implementation
        len1, len2 = len(str1), len(str2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Count matching characters
        matches = sum(c1 == c2 for c1, c2 in zip(str1, str2))
        max_len = max(len1, len2)
        
        return matches / max_len
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text"""
        # Simple keyword extraction
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
        
        # Tokenize and filter
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        
        # Return unique keywords
        return list(set(keywords))
    
    def _check_syntax_errors(self, code: str) -> bool:
        """Basic syntax error check"""
        try:
            compile(code, '<string>', 'exec')
            return False
        except SyntaxError:
            return True
        except:
            return False  # Other errors, not syntax
