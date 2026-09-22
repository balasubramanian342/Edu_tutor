"""
Pedagogy Engine
Applies educational theory to adapt teaching strategies.
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass

import sys
sys.path.append('..')

from student_model import StudentProfile, MasteryLevel


class ScaffoldingLevel(Enum):
    """Levels of instructional scaffolding"""
    MINIMAL = "minimal"          # Student is ready for independent work
    MODERATE = "moderate"        # Some guidance needed
    SUBSTANTIAL = "substantial"  # Significant support required
    INTENSIVE = "intensive"      # Heavy scaffolding needed


@dataclass
class PedagogicalStrategy:
    """Recommended teaching strategy"""
    scaffolding_level: ScaffoldingLevel
    chunking_size: str  # "small", "medium", "large"
    examples_count: int
    practice_frequency: str  # "high", "medium", "low"
    feedback_timing: str  # "immediate", "delayed"
    difficulty_adjustment: int  # -1 (easier), 0 (as-is), +1 (harder)
    
    # Specific techniques
    use_worked_examples: bool
    use_fading: bool  # Gradually reduce support
    use_interleaving: bool  # Mix different concepts
    use_spaced_repetition: bool
    
    def to_dict(self) -> Dict:
        return {
            'scaffolding_level': self.scaffolding_level.value,
            'chunking_size': self.chunking_size,
            'examples_count': self.examples_count,
            'practice_frequency': self.practice_frequency,
            'feedback_timing': self.feedback_timing,
            'difficulty_adjustment': self.difficulty_adjustment,
            'use_worked_examples': self.use_worked_examples,
            'use_fading': self.use_fading,
            'use_interleaving': self.use_interleaving,
            'use_spaced_repetition': self.use_spaced_repetition
        }


class PedagogyEngine:
    """
    Applies educational psychology principles to adapt instruction.
    Based on: Cognitive Load Theory, Zone of Proximal Development, 
    Bloom's Taxonomy, Spaced Repetition, etc.
    """
    
    @staticmethod
    def determine_strategy(student_profile: StudentProfile,
                          current_mastery_level: MasteryLevel,
                          concept_difficulty: str,
                          recent_performance: float) -> PedagogicalStrategy:
        """
        Determine optimal pedagogical strategy based on student state.
        
        Args:
            student_profile: Student's profile
            current_mastery_level: Current mastery of target concept
            concept_difficulty: Concept's inherent difficulty
            recent_performance: Recent success rate (0-1)
        """
        
        # Determine scaffolding level
        scaffolding = PedagogyEngine._determine_scaffolding(
            student_profile,
            current_mastery_level,
            recent_performance
        )
        
        # Chunking based on working memory
        chunking = PedagogyEngine._determine_chunking(student_profile)
        
        # Examples based on mastery and learning style
        examples_count = PedagogyEngine._determine_examples_count(
            student_profile,
            current_mastery_level
        )
        
        # Practice frequency
        practice_freq = PedagogyEngine._determine_practice_frequency(
            current_mastery_level,
            recent_performance
        )
        
        # Feedback timing
        feedback = PedagogyEngine._determine_feedback_timing(
            student_profile,
            current_mastery_level
        )
        
        # Difficulty adjustment
        difficulty_adj = PedagogyEngine._adjust_difficulty(
            concept_difficulty,
            recent_performance,
            student_profile
        )
        
        # Specific techniques
        use_worked = current_mastery_level in [MasteryLevel.NOT_STARTED, MasteryLevel.INTRODUCED]
        use_fading = current_mastery_level in [MasteryLevel.DEVELOPING, MasteryLevel.APPROACHING]
        use_interleaving = current_mastery_level >= MasteryLevel.APPROACHING
        use_spaced = current_mastery_level >= MasteryLevel.PROFICIENT
        
        return PedagogicalStrategy(
            scaffolding_level=scaffolding,
            chunking_size=chunking,
            examples_count=examples_count,
            practice_frequency=practice_freq,
            feedback_timing=feedback,
            difficulty_adjustment=difficulty_adj,
            use_worked_examples=use_worked,
            use_fading=use_fading,
            use_interleaving=use_interleaving,
            use_spaced_repetition=use_spaced
        )
    
    @staticmethod
    def _determine_scaffolding(student_profile: StudentProfile,
                              mastery_level: MasteryLevel,
                              recent_performance: float) -> ScaffoldingLevel:
        """Determine level of scaffolding needed"""
        
        # High scaffolding if:
        # - Low working memory or metacognition
        # - New concept
        # - Poor recent performance
        
        cognitive = student_profile.cognitive_profile
        
        if (cognitive.working_memory < 0.3 or 
            cognitive.metacognition < 0.3 or
            mastery_level == MasteryLevel.NOT_STARTED):
            return ScaffoldingLevel.INTENSIVE
        
        if (mastery_level == MasteryLevel.INTRODUCED or
            recent_performance < 0.4):
            return ScaffoldingLevel.SUBSTANTIAL
        
        if (mastery_level == MasteryLevel.DEVELOPING or
            recent_performance < 0.6):
            return ScaffoldingLevel.MODERATE
        
        return ScaffoldingLevel.MINIMAL
    
    @staticmethod
    def _determine_chunking(student_profile: StudentProfile) -> str:
        """Determine information chunk size"""
        wm = student_profile.cognitive_profile.working_memory
        
        if wm < 0.4:
            return "small"  # 150-250 words
        elif wm < 0.7:
            return "medium"  # 250-400 words
        else:
            return "large"  # 400-600 words
    
    @staticmethod
    def _determine_examples_count(student_profile: StudentProfile,
                                 mastery_level: MasteryLevel) -> int:
        """Determine number of examples to provide"""
        
        base_count = 2
        
        # More examples if student prefers them
        if student_profile.prefers_examples:
            base_count += 1
        
        # More examples for new concepts
        if mastery_level in [MasteryLevel.NOT_STARTED, MasteryLevel.INTRODUCED]:
            base_count += 1
        
        # Fewer examples for mastered concepts
        if mastery_level >= MasteryLevel.PROFICIENT:
            base_count = 1
        
        return min(4, max(1, base_count))
    
    @staticmethod
    def _determine_practice_frequency(mastery_level: MasteryLevel,
                                     recent_performance: float) -> str:
        """Determine how often to present practice opportunities"""
        
        # High frequency if:
        # - Low mastery
        # - Poor performance
        
        if mastery_level <= MasteryLevel.DEVELOPING or recent_performance < 0.5:
            return "high"  # Practice after every explanation
        elif mastery_level == MasteryLevel.APPROACHING or recent_performance < 0.7:
            return "medium"  # Practice every 2-3 explanations
        else:
            return "low"  # Periodic reviews only
    
    @staticmethod
    def _determine_feedback_timing(student_profile: StudentProfile,
                                  mastery_level: MasteryLevel) -> str:
        """Determine when to provide feedback"""
        
        # Immediate feedback for:
        # - Low metacognition (can't self-assess well)
        # - Early learning stages
        
        if (student_profile.cognitive_profile.metacognition < 0.5 or
            mastery_level <= MasteryLevel.DEVELOPING):
            return "immediate"
        else:
            return "delayed"  # Allow reflection first
    
    @staticmethod
    def _adjust_difficulty(concept_difficulty: str,
                          recent_performance: float,
                          student_profile: StudentProfile) -> int:
        """
        Determine if difficulty should be adjusted.
        Returns: -1 (easier), 0 (no change), +1 (harder)
        """
        
        # Make easier if struggling
        if recent_performance < 0.4:
            return -1
        
        # Make harder if excelling and has high abstract reasoning
        if (recent_performance > 0.85 and
            student_profile.cognitive_profile.abstract_reasoning > 0.7):
            return +1
        
        return 0
    
    @staticmethod
    def apply_bloom_taxonomy(current_level: int, target_level: int) -> List[str]:
        """
        Generate learning activities based on Bloom's taxonomy progression.
        
        Bloom's Levels:
        1. Remember: recall facts
        2. Understand: explain concepts
        3. Apply: use in new situations
        4. Analyze: break down and examine
        5. Evaluate: make judgments
        6. Create: produce new work
        """
        
        bloom_activities = {
            1: ["Define key terms", "List the main components", "Recall the basic facts"],
            2: ["Explain in your own words", "Summarize the main idea", "Give examples"],
            3: ["Solve a similar problem", "Apply this concept to a new scenario", "Demonstrate the technique"],
            4: ["Compare and contrast", "Identify the relationships", "Break down the components"],
            5: ["Critique this approach", "Evaluate the effectiveness", "Judge which method is better"],
            6: ["Design a solution", "Create your own example", "Develop a new approach"]
        }
        
        activities = []
        
        # Include activities for current level and path to target
        for level in range(current_level, target_level + 1):
            if level in bloom_activities:
                activities.extend(bloom_activities[level][:2])  # Top 2 activities per level
        
        return activities
    
    @staticmethod
    def apply_cognitive_load_theory(student_profile: StudentProfile,
                                   concept_complexity: str) -> Dict[str, any]:
        """
        Apply Cognitive Load Theory principles.
        
        Returns recommendations for managing cognitive load.
        """
        
        wm_capacity = student_profile.cognitive_profile.working_memory
        
        recommendations = {
            'max_simultaneous_concepts': 3 if wm_capacity > 0.6 else 2 if wm_capacity > 0.3 else 1,
            'use_worked_examples': concept_complexity in ['medium', 'hard'],
            'reduce_extraneous_load': wm_capacity < 0.5,
            'use_dual_coding': student_profile.primary_learning_style.value == 'visual',
            'allow_self_pacing': True,
            'provide_advance_organizers': concept_complexity == 'hard',
            'chunk_information': True,
            'eliminate_redundancy': wm_capacity < 0.4
        }
        
        return recommendations
    
    @staticmethod
    def apply_zone_of_proximal_development(current_mastery: float,
                                          available_difficulties: List[str]) -> str:
        """
        Apply ZPD principle - find the optimal challenge level.
        
        ZPD: Tasks should be challenging but achievable with support.
        """
        
        difficulty_map = {'easy': 0, 'medium': 1, 'hard': 2}
        
        # Map mastery to optimal difficulty
        if current_mastery < 0.3:
            optimal = 'easy'
        elif current_mastery < 0.7:
            optimal = 'medium'
        else:
            optimal = 'hard'
        
        # Return closest available difficulty
        if optimal in available_difficulties:
            return optimal
        
        # Find nearest
        optimal_val = difficulty_map[optimal]
        available_vals = [difficulty_map[d] for d in available_difficulties]
        nearest = min(available_vals, key=lambda x: abs(x - optimal_val))
        
        return [k for k, v in difficulty_map.items() if v == nearest][0]
