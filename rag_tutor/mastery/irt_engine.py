"""
IRT Engine
Item Response Theory for ability estimation and item calibration.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import math

import sys
sys.path.append('..')

from student_model import StudentProfile


@dataclass
class ItemParameters:
    """
    IRT item parameters (3-parameter logistic model).
    """
    difficulty: float  # b parameter (-3 to +3, higher = harder)
    discrimination: float  # a parameter (0 to 3, higher = more discriminating)
    guessing: float  # c parameter (0 to 0.5, probability of guessing correctly)
    
    def to_dict(self) -> Dict:
        return {
            'difficulty': self.difficulty,
            'discrimination': self.discrimination,
            'guessing': self.guessing
        }
    
    @classmethod
    def from_difficulty_level(cls, difficulty_str: str) -> 'ItemParameters':
        """Create item parameters from difficulty string"""
        
        params_map = {
            'easy': ItemParameters(difficulty=-1.0, discrimination=1.0, guessing=0.25),
            'medium': ItemParameters(difficulty=0.0, discrimination=1.2, guessing=0.2),
            'hard': ItemParameters(difficulty=1.0, discrimination=1.5, guessing=0.15)
        }
        
        return params_map.get(difficulty_str, params_map['medium'])


class IRTEngine:
    """
    Item Response Theory engine for ability estimation.
    Uses 3-parameter logistic (3PL) model.
    """
    
    def __init__(self):
        # Store ability estimates per student per concept
        self.ability_estimates: Dict[str, Dict[str, float]] = {}
        # Store item parameters
        self.item_cache: Dict[str, ItemParameters] = {}
    
    def calculate_probability(self,
                            ability: float,
                            item_params: ItemParameters) -> float:
        """
        Calculate probability of correct response using 3PL model.
        
        P(θ) = c + (1 - c) / (1 + exp(-a(θ - b)))
        
        Args:
            ability: Student ability (theta), typically -3 to +3
            item_params: Item parameters (a, b, c)
        
        Returns:
            Probability of correct response (0-1)
        """
        
        a = item_params.discrimination
        b = item_params.difficulty
        c = item_params.guessing
        
        exponent = -a * (ability - b)
        
        # Avoid overflow
        if exponent > 20:
            logistic = 0
        elif exponent < -20:
            logistic = 1
        else:
            logistic = 1 / (1 + math.exp(exponent))
        
        prob = c + (1 - c) * logistic
        
        return max(0.0, min(1.0, prob))
    
    def update_ability(self,
                      student_profile: StudentProfile,
                      concept_id: str,
                      was_correct: bool,
                      difficulty: str,
                      max_iterations: int = 10) -> float:
        """
        Update ability estimate using Maximum Likelihood Estimation.
        
        Args:
            student_profile: Student profile
            concept_id: Concept being assessed
            was_correct: Whether response was correct
            difficulty: Item difficulty
            max_iterations: Max iterations for estimation
        
        Returns:
            Updated ability estimate
        """
        
        student_id = student_profile.student_id
        
        # Initialize if needed
        if student_id not in self.ability_estimates:
            self.ability_estimates[student_id] = {}
        
        if concept_id not in self.ability_estimates[student_id]:
            # Initialize based on cognitive profile
            initial_ability = self._initialize_ability(student_profile)
            self.ability_estimates[student_id][concept_id] = initial_ability
        
        current_ability = self.ability_estimates[student_id][concept_id]
        
        # Get item parameters
        item_params = ItemParameters.from_difficulty_level(difficulty)
        
        # Update using Newton-Raphson method
        for _ in range(max_iterations):
            # Calculate probability of correct response
            prob = self.calculate_probability(current_ability, item_params)
            
            # Calculate derivatives for Newton-Raphson
            a = item_params.discrimination
            b = item_params.difficulty
            c = item_params.guessing
            
            exponent = -a * (current_ability - b)
            if exponent > 20:
                exp_val = 0
            elif exponent < -20:
                exp_val = math.exp(20)
            else:
                exp_val = math.exp(exponent)
            
            denominator = (1 + exp_val) ** 2
            
            # First derivative (gradient)
            if denominator > 0:
                dprobdtheta = a * (1 - c) * exp_val / denominator
            else:
                dprobdtheta = 0.0001
            
            # Second derivative (for curvature)
            if denominator > 0:
                d2probdtheta2 = -a * a * (1 - c) * exp_val * (exp_val - 1) / (denominator * (1 + exp_val))
            else:
                d2probdtheta2 = -0.0001
            
            # Likelihood gradient
            if was_correct:
                gradient = dprobdtheta / prob if prob > 0.001 else 0
            else:
                gradient = -dprobdtheta / (1 - prob) if prob < 0.999 else 0
            
            # Hessian (curvature)
            if was_correct:
                hessian = d2probdtheta2 / prob - (dprobdtheta ** 2) / (prob ** 2) if prob > 0.001 else -0.01
            else:
                hessian = -d2probdtheta2 / (1 - prob) - (dprobdtheta ** 2) / ((1 - prob) ** 2) if prob < 0.999 else -0.01
            
            # Newton-Raphson update
            if abs(hessian) > 0.0001:
                delta = gradient / abs(hessian)
                current_ability += delta
                
                # Constrain to reasonable range
                current_ability = max(-3.0, min(3.0, current_ability))
                
                # Check convergence
                if abs(delta) < 0.01:
                    break
            else:
                break
        
        self.ability_estimates[student_id][concept_id] = current_ability
        
        return current_ability
    
    def get_ability(self,
                   student_id: str,
                   concept_id: str) -> Optional[float]:
        """Get current ability estimate"""
        return self.ability_estimates.get(student_id, {}).get(concept_id)
    
    def estimate_mastery_from_ability(self, ability: float) -> float:
        """
        Convert IRT ability to mastery probability.
        
        Args:
            ability: IRT ability estimate (-3 to +3)
        
        Returns:
            Mastery probability (0-1)
        """
        # Map ability to 0-1 scale
        # ability=-3 -> 0, ability=0 -> 0.5, ability=+3 -> 1
        mastery = (ability + 3) / 6
        return max(0.0, min(1.0, mastery))
    
    def recommend_difficulty(self,
                           student_id: str,
                           concept_id: str,
                           target_success_rate: float = 0.7) -> str:
        """
        Recommend item difficulty to achieve target success rate.
        
        Args:
            student_id: Student ID
            concept_id: Concept ID
            target_success_rate: Desired probability of success
        
        Returns:
            Recommended difficulty level
        """
        
        ability = self.get_ability(student_id, concept_id)
        
        if ability is None:
            return "medium"  # Default
        
        # Try each difficulty level
        best_difficulty = "medium"
        best_diff = float('inf')
        
        for diff_str in ['easy', 'medium', 'hard']:
            params = ItemParameters.from_difficulty_level(diff_str)
            prob = self.calculate_probability(ability, params)
            
            diff = abs(prob - target_success_rate)
            if diff < best_diff:
                best_diff = diff
                best_difficulty = diff_str
        
        return best_difficulty
    
    def calibrate_item(self,
                      responses: list,
                      initial_params: Optional[ItemParameters] = None) -> ItemParameters:
        """
        Calibrate item parameters from response data.
        
        Args:
            responses: List of (ability, was_correct) tuples
            initial_params: Initial parameter estimates
        
        Returns:
            Calibrated ItemParameters
        """
        
        # Simplified calibration (would use EM algorithm in production)
        if not responses:
            return ItemParameters(difficulty=0.0, discrimination=1.0, guessing=0.2)
        
        # Estimate difficulty from success rate
        success_rate = sum(1 for _, correct in responses if correct) / len(responses)
        
        # Logit transform
        if success_rate >= 0.99:
            difficulty = -2.0
        elif success_rate <= 0.01:
            difficulty = 2.0
        else:
            difficulty = -math.log(success_rate / (1 - success_rate))
        
        # Estimate discrimination from variance in responses
        # Higher variance across abilities = more discriminating
        if len(responses) > 5:
            discrimination = 1.5
        else:
            discrimination = 1.0
        
        return ItemParameters(
            difficulty=difficulty,
            discrimination=discrimination,
            guessing=0.2
        )
    
    def _initialize_ability(self, student_profile: StudentProfile) -> float:
        """Initialize ability based on student profile"""
        
        # Use cognitive profile to estimate initial ability
        abstract_reasoning = student_profile.cognitive_profile.abstract_reasoning
        processing_speed = student_profile.cognitive_profile.processing_speed
        
        # Map to -3 to +3 scale
        avg_cognitive = (abstract_reasoning + processing_speed) / 2
        ability = (avg_cognitive - 0.5) * 6  # Maps 0-1 to -3 to +3
        
        return ability
    
    def get_information(self,
                       ability: float,
                       item_params: ItemParameters) -> float:
        """
        Calculate Fisher information at given ability level.
        Higher information = more precise measurement.
        
        Args:
            ability: Student ability
            item_params: Item parameters
        
        Returns:
            Information value
        """
        
        prob = self.calculate_probability(ability, item_params)
        a = item_params.discrimination
        c = item_params.guessing
        
        q = 1 - prob
        
        if prob <= c or q == 0:
            return 0.0
        
        numerator = a * a * (prob - c) ** 2 * q
        denominator = prob * (1 - c) ** 2
        
        if denominator == 0:
            return 0.0
        
        information = numerator / denominator
        
        return information
