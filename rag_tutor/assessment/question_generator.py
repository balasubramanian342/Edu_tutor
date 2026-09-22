"""
Question Generator
Generates questions aligned with Bloom's taxonomy and concept difficulty.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
import random
import json

import sys
sys.path.append('..')

from knowledge_graph import ConceptNode


class QuestionType(Enum):
    """Types of questions aligned with Bloom's taxonomy"""
    MULTIPLE_CHOICE = "multiple_choice"          # Bloom 1-2
    TRUE_FALSE = "true_false"                    # Bloom 1
    FILL_IN_BLANK = "fill_in_blank"             # Bloom 1-2
    SHORT_ANSWER = "short_answer"                # Bloom 2-3
    CODE_COMPLETION = "code_completion"          # Bloom 3
    CODE_DEBUGGING = "code_debugging"            # Bloom 4
    PROBLEM_SOLVING = "problem_solving"          # Bloom 3-4
    ESSAY = "essay"                              # Bloom 5-6
    CODE_FROM_SCRATCH = "code_from_scratch"      # Bloom 6


@dataclass
class Question:
    """A generated assessment question"""
    question_id: str
    question_type: QuestionType
    concept_id: str
    concept_name: str
    
    # Content
    prompt: str
    difficulty: str  # easy, medium, hard
    bloom_level: int  # 1-6
    
    # For objective questions
    correct_answer: Optional[Any] = None
    options: Optional[List[str]] = None  # For multiple choice
    
    # For subjective questions
    rubric: Optional[Dict[str, Any]] = None
    sample_answer: Optional[str] = None
    
    # Metadata
    estimated_time_minutes: int = 5
    points: int = 1
    hints: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'question_id': self.question_id,
            'question_type': self.question_type.value,
            'concept_id': self.concept_id,
            'concept_name': self.concept_name,
            'prompt': self.prompt,
            'difficulty': self.difficulty,
            'bloom_level': self.bloom_level,
            'options': self.options,
            'estimated_time_minutes': self.estimated_time_minutes,
            'points': self.points,
            'hints': self.hints,
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Question':
        data = data.copy()
        data['question_type'] = QuestionType(data['question_type'])
        # Don't include answer in deserialization for security
        data.pop('correct_answer', None)
        data.pop('rubric', None)
        return cls(**data)


class QuestionGenerator:
    """
    Generates formative assessment questions based on concepts and mastery level.
    """
    
    def __init__(self, question_bank_path: Optional[str] = None, llm_client=None):
        """
        Initialize with optional question bank and LLM for generation.
        
        Args:
            question_bank_path: Path to JSON file with pre-written questions
            llm_client: Optional LLM for generating new questions
        """
        self.question_bank = self._load_question_bank(question_bank_path) if question_bank_path else {}
        self.llm_client = llm_client
    
    def generate_for_concept(self,
                           concept: ConceptNode,
                           bloom_level: int,
                           question_type: Optional[QuestionType] = None,
                           difficulty: Optional[str] = None) -> Question:
        """
        Generate a question for a specific concept.
        
        Args:
            concept: Target concept
            bloom_level: Desired Bloom's taxonomy level (1-6)
            question_type: Specific question type (auto-selected if None)
            difficulty: Override concept difficulty
        """
        
        difficulty = difficulty or concept.difficulty
        
        # Auto-select question type if not specified
        if not question_type:
            question_type = self._select_question_type(bloom_level, difficulty)
        
        # Try to get from bank first
        if concept.concept_id in self.question_bank:
            bank_questions = self.question_bank[concept.concept_id]
            matching = [
                q for q in bank_questions
                if q['bloom_level'] == bloom_level and
                   q['question_type'] == question_type.value
            ]
            if matching:
                return self._create_from_bank(random.choice(matching), concept)
        
        # Generate new question
        if self.llm_client:
            return self._generate_with_llm(concept, bloom_level, question_type, difficulty)
        else:
            return self._generate_template_based(concept, bloom_level, question_type, difficulty)
    
    def generate_assessment_set(self,
                               concepts: List[ConceptNode],
                               target_bloom_levels: List[int],
                               total_questions: int = 10) -> List[Question]:
        """
        Generate a balanced set of questions covering multiple concepts.
        
        Args:
            concepts: Concepts to assess
            target_bloom_levels: Distribution of Bloom levels
            total_questions: Total number of questions
        """
        questions = []
        question_id = 1
        
        # Distribute questions across concepts and bloom levels
        questions_per_concept = max(1, total_questions // len(concepts))
        
        for concept in concepts:
            for bloom_level in target_bloom_levels[:questions_per_concept]:
                try:
                    question = self.generate_for_concept(concept, bloom_level)
                    question.question_id = f"Q{question_id:03d}"
                    questions.append(question)
                    question_id += 1
                    
                    if len(questions) >= total_questions:
                        break
                except Exception as e:
                    print(f"Error generating question for {concept.name}: {e}")
                    continue
            
            if len(questions) >= total_questions:
                break
        
        return questions
    
    def generate_adaptive_question(self,
                                  concept: ConceptNode,
                                  current_mastery: float,
                                  recent_performance: float) -> Question:
        """
        Generate a question adapted to current mastery level.
        Uses Item Response Theory principles.
        
        Args:
            concept: Target concept
            current_mastery: Student's mastery probability (0-1)
            recent_performance: Recent success rate (0-1)
        """
        
        # Determine appropriate Bloom level
        if current_mastery < 0.3:
            bloom_level = random.choice([1, 2])  # Remember, Understand
        elif current_mastery < 0.6:
            bloom_level = random.choice([2, 3])  # Understand, Apply
        elif current_mastery < 0.8:
            bloom_level = random.choice([3, 4])  # Apply, Analyze
        else:
            bloom_level = random.choice([4, 5, 6])  # Analyze, Evaluate, Create
        
        # Adjust difficulty based on recent performance
        if recent_performance < 0.5:
            difficulty = "easy"
        elif recent_performance > 0.8:
            difficulty = "hard"
        else:
            difficulty = concept.difficulty
        
        return self.generate_for_concept(concept, bloom_level, difficulty=difficulty)
    
    def _select_question_type(self, bloom_level: int, difficulty: str) -> QuestionType:
        """Select appropriate question type for bloom level"""
        
        type_mapping = {
            1: [QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE, QuestionType.FILL_IN_BLANK],
            2: [QuestionType.MULTIPLE_CHOICE, QuestionType.SHORT_ANSWER],
            3: [QuestionType.SHORT_ANSWER, QuestionType.PROBLEM_SOLVING, QuestionType.CODE_COMPLETION],
            4: [QuestionType.PROBLEM_SOLVING, QuestionType.CODE_DEBUGGING],
            5: [QuestionType.ESSAY, QuestionType.PROBLEM_SOLVING],
            6: [QuestionType.CODE_FROM_SCRATCH, QuestionType.ESSAY]
        }
        
        available_types = type_mapping.get(bloom_level, [QuestionType.SHORT_ANSWER])
        return random.choice(available_types)
    
    def _generate_template_based(self,
                                concept: ConceptNode,
                                bloom_level: int,
                                question_type: QuestionType,
                                difficulty: str) -> Question:
        """Generate question using templates (fallback)"""
        
        templates = {
            QuestionType.MULTIPLE_CHOICE: {
                1: f"What is {concept.name}?",
                2: f"Which of the following best describes {concept.name}?",
                3: f"How would you use {concept.name} to solve this problem?",
                4: f"What is the key difference between {concept.name} and similar concepts?"
            },
            QuestionType.TRUE_FALSE: {
                1: f"{concept.name} is a fundamental concept in {concept.subject}. True or False?",
                2: f"{concept.name} always requires {concept.keywords[0] if concept.keywords else 'prerequisites'}. True or False?"
            },
            QuestionType.SHORT_ANSWER: {
                2: f"Explain {concept.name} in your own words.",
                3: f"Give an example of how {concept.name} is used.",
                4: f"Compare and contrast {concept.name} with related concepts."
            },
            QuestionType.PROBLEM_SOLVING: {
                3: f"Solve this problem using {concept.name}: [Problem would be inserted here]",
                4: f"Debug this implementation of {concept.name}: [Code would be inserted here]"
            }
        }
        
        prompt_templates = templates.get(question_type, {})
        prompt = prompt_templates.get(bloom_level, f"Explain {concept.name}")
        
        # Generate options for multiple choice
        options = None
        correct_answer = None
        
        if question_type == QuestionType.MULTIPLE_CHOICE:
            correct_answer = f"Correct definition of {concept.name}"
            options = [
                correct_answer,
                f"Incorrect option A about {concept.name}",
                f"Incorrect option B about {concept.name}",
                f"Incorrect option C about {concept.name}"
            ]
            random.shuffle(options)
        elif question_type == QuestionType.TRUE_FALSE:
            correct_answer = random.choice([True, False])
            options = ["True", "False"]
        
        # Generate hints
        hints = [
            f"Review the definition of {concept.name}",
            f"Think about examples of {concept.name}",
            f"Consider the prerequisites: {', '.join([kw for kw in concept.keywords[:2]])}"
        ]
        
        return Question(
            question_id=f"Q_{concept.concept_id}_{bloom_level}",
            question_type=question_type,
            concept_id=concept.concept_id,
            concept_name=concept.name,
            prompt=prompt,
            difficulty=difficulty,
            bloom_level=bloom_level,
            correct_answer=correct_answer,
            options=options,
            estimated_time_minutes=self._estimate_time(question_type, difficulty),
            points=bloom_level,
            hints=hints[:2],
            tags=[concept.subject, concept.unit, difficulty]
        )
    
    def _generate_with_llm(self,
                          concept: ConceptNode,
                          bloom_level: int,
                          question_type: QuestionType,
                          difficulty: str) -> Question:
        """Generate question using LLM"""
        
        bloom_descriptions = {
            1: "Recall and recognize factual information",
            2: "Explain and interpret meaning",
            3: "Apply knowledge to new situations",
            4: "Break down and examine components",
            5: "Make judgments and critiques",
            6: "Create new solutions or products"
        }
        
        prompt = f"""Generate a {difficulty} {question_type.value} question for assessing student understanding of:

Concept: {concept.name}
Subject: {concept.subject}
Description: {concept.description}
Keywords: {', '.join(concept.keywords)}

Bloom's Taxonomy Level: {bloom_level} - {bloom_descriptions[bloom_level]}

The question should:
1. Be clear and unambiguous
2. Match the specified difficulty level
3. Assess at the specified Bloom level
4. Be answerable based on standard course materials

Return JSON format:
{{
    "prompt": "the question text",
    "correct_answer": "the answer (for objective questions)",
    "options": ["option1", "option2", ...] (for multiple choice),
    "rubric": {{"criteria": "description"}} (for subjective questions),
    "hints": ["hint1", "hint2"]
}}"""
        
        try:
            if self.llm_client:
                response = self.llm_client.generate(
                    system_prompt="You are an educational assessment expert.",
                    user_prompt=prompt,
                    temperature=0.8,
                    max_tokens=500
                )
                
                # Parse response
                data = json.loads(response)
                
                return Question(
                    question_id=f"Q_{concept.concept_id}_{bloom_level}",
                    question_type=question_type,
                    concept_id=concept.concept_id,
                    concept_name=concept.name,
                    prompt=data['prompt'],
                    difficulty=difficulty,
                    bloom_level=bloom_level,
                    correct_answer=data.get('correct_answer'),
                    options=data.get('options'),
                    rubric=data.get('rubric'),
                    estimated_time_minutes=self._estimate_time(question_type, difficulty),
                    points=bloom_level,
                    hints=data.get('hints', [])[:2],
                    tags=[concept.subject, concept.unit, difficulty]
                )
        except Exception as e:
            print(f"LLM generation failed: {e}, falling back to template")
        
        # Fallback to template
        return self._generate_template_based(concept, bloom_level, question_type, difficulty)
    
    def _estimate_time(self, question_type: QuestionType, difficulty: str) -> int:
        """Estimate time to complete question in minutes"""
        
        base_times = {
            QuestionType.MULTIPLE_CHOICE: 2,
            QuestionType.TRUE_FALSE: 1,
            QuestionType.FILL_IN_BLANK: 2,
            QuestionType.SHORT_ANSWER: 5,
            QuestionType.CODE_COMPLETION: 8,
            QuestionType.CODE_DEBUGGING: 10,
            QuestionType.PROBLEM_SOLVING: 10,
            QuestionType.ESSAY: 15,
            QuestionType.CODE_FROM_SCRATCH: 20
        }
        
        base = base_times.get(question_type, 5)
        
        # Adjust for difficulty
        if difficulty == "hard":
            base = int(base * 1.5)
        elif difficulty == "easy":
            base = int(base * 0.75)
        
        return max(1, base)
    
    def _create_from_bank(self, bank_data: Dict, concept: ConceptNode) -> Question:
        """Create question from question bank entry"""
        
        return Question(
            question_id=bank_data.get('question_id', f"Q_{concept.concept_id}"),
            question_type=QuestionType(bank_data['question_type']),
            concept_id=concept.concept_id,
            concept_name=concept.name,
            prompt=bank_data['prompt'],
            difficulty=bank_data.get('difficulty', concept.difficulty),
            bloom_level=bank_data['bloom_level'],
            correct_answer=bank_data.get('correct_answer'),
            options=bank_data.get('options'),
            rubric=bank_data.get('rubric'),
            sample_answer=bank_data.get('sample_answer'),
            estimated_time_minutes=bank_data.get('estimated_time_minutes', 5),
            points=bank_data.get('points', bank_data['bloom_level']),
            hints=bank_data.get('hints', []),
            tags=bank_data.get('tags', [])
        )
    
    def _load_question_bank(self, filepath: str) -> Dict[str, List[Dict]]:
        """Load pre-written questions from JSON file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load question bank: {e}")
            return {}
    
    def save_question_bank(self, filepath: str, questions: List[Question]):
        """Save questions to question bank"""
        
        bank = {}
        for q in questions:
            if q.concept_id not in bank:
                bank[q.concept_id] = []
            
            bank[q.concept_id].append({
                'question_id': q.question_id,
                'question_type': q.question_type.value,
                'prompt': q.prompt,
                'difficulty': q.difficulty,
                'bloom_level': q.bloom_level,
                'correct_answer': q.correct_answer,
                'options': q.options,
                'rubric': q.rubric,
                'sample_answer': q.sample_answer,
                'estimated_time_minutes': q.estimated_time_minutes,
                'points': q.points,
                'hints': q.hints,
                'tags': q.tags
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(bank, f, indent=2)
