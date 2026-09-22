"""
Student Dashboard
Personalized progress view for students.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import sys
sys.path.append('..')

from student_model import StudentProfile, KnowledgeState, MasteryLevel
from knowledge_graph import ConceptGraph
from gap_analysis import GapAnalyzer
from mastery import MasteryTracker


@dataclass
class StudentReport:
    """Comprehensive student progress report"""
    student_id: str
    student_name: str
    
    # Overall statistics
    overall_mastery: float
    concepts_mastered: int
    concepts_in_progress: int
    total_study_time_hours: float
    
    # Recent activity
    last_active: datetime
    sessions_this_week: int
    practice_problems_completed: int
    
    # Progress breakdown
    subject_progress: Dict[str, Dict] = field(default_factory=dict)
    recent_improvements: List[Dict] = field(default_factory=list)
    concepts_needing_review: List[str] = field(default_factory=list)
    
    # Goals and recommendations
    next_learning_targets: List[str] = field(default_factory=list)
    recommended_study_time: int = 0  # minutes per day
    strengths: List[str] = field(default_factory=list)
    areas_for_improvement: List[str] = field(default_factory=list)
    
    # Achievements
    recently_mastered: List[str] = field(default_factory=list)
    current_streak: int = 0  # days of consistent study
    
    generated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            'student_id': self.student_id,
            'student_name': self.student_name,
            'overall_mastery': self.overall_mastery,
            'concepts_mastered': self.concepts_mastered,
            'concepts_in_progress': self.concepts_in_progress,
            'total_study_time_hours': self.total_study_time_hours,
            'last_active': self.last_active.isoformat(),
            'sessions_this_week': self.sessions_this_week,
            'practice_problems_completed': self.practice_problems_completed,
            'subject_progress': self.subject_progress,
            'recent_improvements': self.recent_improvements,
            'concepts_needing_review': self.concepts_needing_review,
            'next_learning_targets': self.next_learning_targets,
            'recommended_study_time': self.recommended_study_time,
            'strengths': self.strengths,
            'areas_for_improvement': self.areas_for_improvement,
            'recently_mastered': self.recently_mastered,
            'current_streak': self.current_streak,
            'generated_at': self.generated_at.isoformat()
        }


class StudentDashboard:
    """
    Generates personalized progress reports and recommendations for students.
    """
    
    def __init__(self,
                 knowledge_graph: ConceptGraph,
                 gap_analyzer: GapAnalyzer,
                 mastery_tracker: MasteryTracker):
        self.knowledge_graph = knowledge_graph
        self.gap_analyzer = gap_analyzer
        self.mastery_tracker = mastery_tracker
    
    def generate_report(self,
                       student_profile: StudentProfile,
                       student_knowledge: KnowledgeState) -> StudentReport:
        """
        Generate comprehensive progress report for a student.
        
        Args:
            student_profile: Student's profile
            student_knowledge: Student's knowledge state
        
        Returns:
            Complete student report
        """
        
        # Overall statistics
        overall_mastery = student_knowledge.get_overall_mastery()
        mastered_count = len(student_knowledge.get_mastered_concepts())
        
        in_progress = len([
            c for c in student_knowledge.concepts.values()
            if c.mastery_level in [MasteryLevel.DEVELOPING, 
                                  MasteryLevel.APPROACHING,
                                  MasteryLevel.PROFICIENT]
        ])
        
        total_time = student_profile.total_time_minutes / 60  # Convert to hours
        
        # Recent activity (would come from interaction logs in production)
        sessions_this_week = self._count_recent_sessions(student_profile, days=7)
        practice_count = self._count_practice_problems(student_knowledge)
        
        # Subject-level progress
        subject_progress = self._calculate_subject_progress(student_knowledge)
        
        # Recent improvements
        recent_improvements = self.mastery_tracker.get_recent_improvements(
            student_profile.student_id,
            days=7
        )
        
        # Concepts needing review (spaced repetition)
        needs_review = [
            c.concept_name for c in student_knowledge.get_concepts_for_review()
        ]
        
        # Next learning targets
        next_targets = self._identify_next_targets(student_profile, student_knowledge)
        
        # Recommended study time
        recommended_time = self._calculate_recommended_study_time(
            student_profile,
            student_knowledge
        )
        
        # Strengths and areas for improvement
        strengths, areas_for_improvement = self._analyze_strengths_weaknesses(
            student_knowledge
        )
        
        # Recently mastered concepts
        recently_mastered = self._get_recently_mastered(
            student_knowledge,
            days=7
        )
        
        # Learning streak
        streak = self._calculate_study_streak(student_profile)
        
        return StudentReport(
            student_id=student_profile.student_id,
            student_name=student_profile.name,
            overall_mastery=overall_mastery,
            concepts_mastered=mastered_count,
            concepts_in_progress=in_progress,
            total_study_time_hours=total_time,
            last_active=student_profile.last_active or datetime.utcnow(),
            sessions_this_week=sessions_this_week,
            practice_problems_completed=practice_count,
            subject_progress=subject_progress,
            recent_improvements=recent_improvements,
            concepts_needing_review=needs_review[:5],
            next_learning_targets=next_targets,
            recommended_study_time=recommended_time,
            strengths=strengths,
            areas_for_improvement=areas_for_improvement,
            recently_mastered=recently_mastered,
            current_streak=streak
        )
    
    def get_progress_summary(self,
                            student_profile: StudentProfile,
                            student_knowledge: KnowledgeState) -> Dict:
        """Get quick progress summary (for dashboard widget)"""
        
        return {
            'overall_mastery': f"{student_knowledge.get_overall_mastery() * 100:.0f}%",
            'concepts_mastered': len(student_knowledge.get_mastered_concepts()),
            'total_concepts': len(student_knowledge.concepts),
            'study_time_today': 0,  # Would track from session data
            'current_streak': self._calculate_study_streak(student_profile),
            'next_review_due': self._get_next_review_time(student_knowledge)
        }
    
    def get_concept_details(self,
                           student_knowledge: KnowledgeState,
                           concept_id: str) -> Dict:
        """Get detailed view of a single concept's progress"""
        
        concept_mastery = student_knowledge.get_concept(concept_id)
        
        if not concept_mastery:
            return {'error': 'Concept not found'}
        
        # Get learning trajectory
        trajectory = self.mastery_tracker.get_mastery_trajectory(
            student_knowledge.student_id,
            concept_id
        )
        
        return {
            'concept_name': concept_mastery.concept_name,
            'mastery_level': concept_mastery.mastery_level.name,
            'mastery_probability': concept_mastery.mastery_probability,
            'attempts': concept_mastery.attempts,
            'correct_attempts': concept_mastery.correct_attempts,
            'success_rate': concept_mastery.recent_success_rate,
            'first_seen': concept_mastery.first_seen.isoformat(),
            'last_practiced': concept_mastery.last_practiced.isoformat(),
            'time_to_mastery': concept_mastery.time_to_mastery_minutes,
            'needs_review': concept_mastery.needs_review(),
            'next_review': concept_mastery.next_review_date.isoformat() if concept_mastery.next_review_date else None,
            'trajectory': [
                {
                    'timestamp': u.timestamp.isoformat(),
                    'mastery': u.new_mastery,
                    'level': u.new_level
                }
                for u in trajectory
            ]
        }
    
    def get_learning_path(self,
                         student_profile: StudentProfile,
                         student_knowledge: KnowledgeState,
                         target_concept_id: Optional[str] = None) -> Dict:
        """Get recommended learning path"""
        
        if target_concept_id:
            # Path to specific concept
            mastered_ids = {
                c.concept_id for c in student_knowledge.get_mastered_concepts()
            }
            
            path = self.knowledge_graph.find_learning_path(
                target_concept_id,
                mastered_ids
            )
            
            return {
                'target_concept': self.knowledge_graph.get_concept(target_concept_id).name,
                'steps': [
                    {
                        'concept_id': c.concept_id,
                        'concept_name': c.name,
                        'difficulty': c.difficulty,
                        'estimated_time': c.typical_time_minutes
                    }
                    for c in path
                ],
                'total_time_estimate': sum(c.typical_time_minutes for c in path)
            }
        else:
            # General next steps
            next_concept = self.gap_analyzer.suggest_next_learning_target(
                student_knowledge,
                student_profile
            )
            
            if next_concept:
                return {
                    'next_concept': next_concept.name,
                    'concept_id': next_concept.concept_id,
                    'difficulty': next_concept.difficulty,
                    'estimated_time': next_concept.typical_time_minutes,
                    'prerequisites_met': True
                }
            else:
                return {'message': 'Continue practicing current concepts'}
    
    def _calculate_subject_progress(self,
                                   student_knowledge: KnowledgeState) -> Dict[str, Dict]:
        """Calculate progress for each subject"""
        
        subjects = {}
        
        for concept in student_knowledge.concepts.values():
            subject = concept.subject
            
            if subject not in subjects:
                subjects[subject] = {
                    'total_concepts': 0,
                    'mastered': 0,
                    'in_progress': 0,
                    'not_started': 0,
                    'average_mastery': 0.0,
                    'mastery_sum': 0.0
                }
            
            data = subjects[subject]
            data['total_concepts'] += 1
            data['mastery_sum'] += concept.mastery_probability
            
            if concept.mastery_level == MasteryLevel.MASTERED:
                data['mastered'] += 1
            elif concept.mastery_level in [MasteryLevel.DEVELOPING,
                                          MasteryLevel.APPROACHING,
                                          MasteryLevel.PROFICIENT]:
                data['in_progress'] += 1
            else:
                data['not_started'] += 1
        
        # Calculate averages
        for data in subjects.values():
            if data['total_concepts'] > 0:
                data['average_mastery'] = data['mastery_sum'] / data['total_concepts']
                data['completion_percentage'] = (data['mastered'] / data['total_concepts']) * 100
            del data['mastery_sum']  # Remove intermediate calculation
        
        return subjects
    
    def _identify_next_targets(self,
                              student_profile: StudentProfile,
                              student_knowledge: KnowledgeState) -> List[str]:
        """Identify next learning targets"""
        
        next_concept = self.gap_analyzer.suggest_next_learning_target(
            student_knowledge,
            student_profile
        )
        
        if next_concept:
            return [next_concept.name]
        
        # Fallback: concepts that need review
        review_concepts = student_knowledge.get_concepts_for_review()
        return [c.concept_name for c in review_concepts[:3]]
    
    def _calculate_recommended_study_time(self,
                                         student_profile: StudentProfile,
                                         student_knowledge: KnowledgeState) -> int:
        """Calculate recommended daily study time in minutes"""
        
        # Base recommendation
        base_time = 30  # 30 minutes per day
        
        # Adjust based on pace preference
        if student_profile.pace_preference.value == "fast":
            base_time = 45
        elif student_profile.pace_preference.value == "slow":
            base_time = 20
        
        # Adjust based on current progress
        if student_profile.overall_mastery < 0.3:
            base_time += 10  # Need more time if struggling
        
        return base_time
    
    def _analyze_strengths_weaknesses(self,
                                     student_knowledge: KnowledgeState) -> tuple:
        """Identify student's strengths and weaknesses"""
        
        # Analyze by subject/unit
        performance_by_subject = {}
        
        for concept in student_knowledge.concepts.values():
            subject = concept.subject
            
            if subject not in performance_by_subject:
                performance_by_subject[subject] = []
            
            performance_by_subject[subject].append(concept.mastery_probability)
        
        # Calculate averages
        subject_averages = {
            subject: sum(scores) / len(scores) if scores else 0
            for subject, scores in performance_by_subject.items()
        }
        
        # Identify strengths (>70%) and weaknesses (<50%)
        strengths = [
            subject for subject, avg in subject_averages.items()
            if avg > 0.7
        ]
        
        weaknesses = [
            subject for subject, avg in subject_averages.items()
            if avg < 0.5
        ]
        
        return strengths[:3], weaknesses[:3]
    
    def _get_recently_mastered(self,
                              student_knowledge: KnowledgeState,
                              days: int) -> List[str]:
        """Get concepts mastered in recent period"""
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        recent = []
        for concept in student_knowledge.concepts.values():
            if (concept.mastery_level == MasteryLevel.MASTERED and
                concept.time_to_mastery_minutes is not None):
                # Estimate when mastered (would be better with explicit timestamp)
                recent.append(concept.concept_name)
        
        return recent[:5]
    
    def _calculate_study_streak(self, student_profile: StudentProfile) -> int:
        """Calculate consecutive days of study"""
        # Would track from session data in production
        # For now, estimate from last active
        if not student_profile.last_active:
            return 0
        
        days_since = (datetime.utcnow() - student_profile.last_active).days
        
        if days_since <= 1:
            return max(1, student_profile.total_sessions // 3)
        else:
            return 0
    
    def _count_recent_sessions(self, student_profile: StudentProfile, days: int) -> int:
        """Count sessions in recent period"""
        # Would query interaction logs in production
        return min(student_profile.total_sessions, days)
    
    def _count_practice_problems(self, student_knowledge: KnowledgeState) -> int:
        """Count total practice problems completed"""
        return sum(c.attempts for c in student_knowledge.concepts.values())
    
    def _get_next_review_time(self, student_knowledge: KnowledgeState) -> Optional[str]:
        """Get next spaced repetition review time"""
        review_concepts = student_knowledge.get_concepts_for_review()
        
        if review_concepts:
            return "Now"
        
        # Find soonest upcoming review
        upcoming = [
            c.next_review_date for c in student_knowledge.concepts.values()
            if c.next_review_date and c.next_review_date > datetime.utcnow()
        ]
        
        if upcoming:
            soonest = min(upcoming)
            hours = (soonest - datetime.utcnow()).total_seconds() / 3600
            
            if hours < 24:
                return f"In {int(hours)} hours"
            else:
                return f"In {int(hours / 24)} days"
        
        return None
