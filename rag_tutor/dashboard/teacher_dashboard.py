"""
Teacher Dashboard
Class-level analytics and insights for instructors.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

import sys
sys.path.append('..')

from student_model import StudentProfile, KnowledgeState, MasteryLevel
from knowledge_graph import ConceptGraph


@dataclass
class ClassAnalytics:
    """Class-level analytics and insights"""
    class_id: str
    class_name: str
    
    # Overall statistics
    total_students: int
    active_students: int  # Active in last 7 days
    average_mastery: float
    
    # Concept coverage
    concepts_taught: int
    average_concepts_per_student: float
    
    # Performance distribution
    students_excelling: int  # >80% mastery
    students_on_track: int  # 60-80% mastery
    students_struggling: int  # <60% mastery
    
    # Engagement metrics
    average_session_length: float
    average_sessions_per_week: float
    total_practice_problems: int
    
    # Concept-level insights
    challenging_concepts: List[Dict] = field(default_factory=list)
    well_understood_concepts: List[Dict] = field(default_factory=list)
    
    # Student insights
    top_performers: List[Dict] = field(default_factory=list)
    students_needing_attention: List[Dict] = field(default_factory=list)
    
    # Trends
    mastery_trend: str = "stable"  # "improving", "declining", "stable"
    engagement_trend: str = "stable"
    
    generated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            'class_id': self.class_id,
            'class_name': self.class_name,
            'total_students': self.total_students,
            'active_students': self.active_students,
            'average_mastery': self.average_mastery,
            'concepts_taught': self.concepts_taught,
            'average_concepts_per_student': self.average_concepts_per_student,
            'students_excelling': self.students_excelling,
            'students_on_track': self.students_on_track,
            'students_struggling': self.students_struggling,
            'average_session_length': self.average_session_length,
            'average_sessions_per_week': self.average_sessions_per_week,
            'total_practice_problems': self.total_practice_problems,
            'challenging_concepts': self.challenging_concepts,
            'well_understood_concepts': self.well_understood_concepts,
            'top_performers': self.top_performers,
            'students_needing_attention': self.students_needing_attention,
            'mastery_trend': self.mastery_trend,
            'engagement_trend': self.engagement_trend,
            'generated_at': self.generated_at.isoformat()
        }


class TeacherDashboard:
    """
    Generates class-level analytics and insights for teachers.
    """
    
    def __init__(self, knowledge_graph: ConceptGraph):
        self.knowledge_graph = knowledge_graph
    
    def generate_class_analytics(self,
                                class_id: str,
                                class_name: str,
                                student_profiles: List[StudentProfile],
                                student_knowledge_states: Dict[str, KnowledgeState]) -> ClassAnalytics:
        """
        Generate comprehensive class analytics.
        
        Args:
            class_id: Class identifier
            class_name: Class name
            student_profiles: List of student profiles
            student_knowledge_states: Dict mapping student_id to KnowledgeState
        
        Returns:
            ClassAnalytics with insights
        """
        
        total_students = len(student_profiles)
        
        # Active students (last 7 days)
        cutoff = datetime.utcnow() - timedelta(days=7)
        active = sum(
            1 for s in student_profiles
            if s.last_active and s.last_active >= cutoff
        )
        
        # Average mastery
        masteries = [s.overall_mastery for s in student_profiles]
        avg_mastery = sum(masteries) / len(masteries) if masteries else 0
        
        # Concept coverage
        all_concepts = set()
        for knowledge in student_knowledge_states.values():
            all_concepts.update(knowledge.concepts.keys())
        
        concepts_taught = len(all_concepts)
        avg_concepts = sum(
            len(k.concepts) for k in student_knowledge_states.values()
        ) / len(student_knowledge_states) if student_knowledge_states else 0
        
        # Performance distribution
        excelling = sum(1 for s in student_profiles if s.overall_mastery > 0.8)
        on_track = sum(1 for s in student_profiles if 0.6 <= s.overall_mastery <= 0.8)
        struggling = sum(1 for s in student_profiles if s.overall_mastery < 0.6)
        
        # Engagement metrics
        avg_session_length = sum(
            s.average_session_length for s in student_profiles
        ) / len(student_profiles) if student_profiles else 0
        
        avg_sessions_week = sum(
            min(s.total_sessions, 10) for s in student_profiles  # Cap at 10 for weekly estimate
        ) / len(student_profiles) if student_profiles else 0
        
        total_practice = sum(
            sum(c.attempts for c in k.concepts.values())
            for k in student_knowledge_states.values()
        )
        
        # Concept-level insights
        challenging, well_understood = self._analyze_concept_difficulty(
            student_knowledge_states
        )
        
        # Student insights
        top_performers = self._identify_top_performers(
            student_profiles,
            limit=5
        )
        
        need_attention = self._identify_students_needing_attention(
            student_profiles,
            student_knowledge_states,
            limit=5
        )
        
        # Trends (would require historical data)
        mastery_trend = self._analyze_mastery_trend(student_profiles)
        engagement_trend = self._analyze_engagement_trend(student_profiles)
        
        return ClassAnalytics(
            class_id=class_id,
            class_name=class_name,
            total_students=total_students,
            active_students=active,
            average_mastery=avg_mastery,
            concepts_taught=concepts_taught,
            average_concepts_per_student=avg_concepts,
            students_excelling=excelling,
            students_on_track=on_track,
            students_struggling=struggling,
            average_session_length=avg_session_length,
            average_sessions_per_week=avg_sessions_week,
            total_practice_problems=total_practice,
            challenging_concepts=challenging,
            well_understood_concepts=well_understood,
            top_performers=top_performers,
            students_needing_attention=need_attention,
            mastery_trend=mastery_trend,
            engagement_trend=engagement_trend
        )
    
    def get_concept_analytics(self,
                             concept_id: str,
                             student_knowledge_states: Dict[str, KnowledgeState]) -> Dict:
        """Get detailed analytics for a specific concept"""
        
        concept = self.knowledge_graph.get_concept(concept_id)
        
        if not concept:
            return {'error': 'Concept not found'}
        
        # Collect data across all students
        mastery_scores = []
        attempt_counts = []
        success_rates = []
        students_mastered = 0
        students_struggling = 0
        
        for knowledge in student_knowledge_states.values():
            concept_mastery = knowledge.get_concept(concept_id)
            
            if concept_mastery and concept_mastery.attempts > 0:
                mastery_scores.append(concept_mastery.mastery_probability)
                attempt_counts.append(concept_mastery.attempts)
                success_rates.append(concept_mastery.recent_success_rate)
                
                if concept_mastery.mastery_level == MasteryLevel.MASTERED:
                    students_mastered += 1
                elif concept_mastery.mastery_probability < 0.5:
                    students_struggling += 1
        
        if not mastery_scores:
            return {
                'concept_name': concept.name,
                'students_attempted': 0,
                'message': 'No student data yet'
            }
        
        return {
            'concept_id': concept_id,
            'concept_name': concept.name,
            'difficulty': concept.difficulty,
            'students_attempted': len(mastery_scores),
            'students_mastered': students_mastered,
            'students_struggling': students_struggling,
            'average_mastery': sum(mastery_scores) / len(mastery_scores),
            'average_attempts': sum(attempt_counts) / len(attempt_counts),
            'average_success_rate': sum(success_rates) / len(success_rates),
            'mastery_distribution': self._create_distribution(mastery_scores),
            'is_challenging': sum(mastery_scores) / len(mastery_scores) < 0.5
        }
    
    def get_student_comparison(self,
                              student_profiles: List[StudentProfile],
                              metric: str = "mastery") -> List[Dict]:
        """
        Compare students by a specific metric.
        
        Args:
            student_profiles: List of students
            metric: "mastery", "engagement", "progress"
        
        Returns:
            Ranked list of students
        """
        
        if metric == "mastery":
            key_func = lambda s: s.overall_mastery
        elif metric == "engagement":
            key_func = lambda s: s.total_sessions
        elif metric == "progress":
            key_func = lambda s: s.concepts_mastered
        else:
            key_func = lambda s: s.overall_mastery
        
        sorted_students = sorted(student_profiles, key=key_func, reverse=True)
        
        return [
            {
                'rank': i + 1,
                'student_id': s.student_id,
                'student_name': s.name,
                'value': key_func(s),
                'overall_mastery': s.overall_mastery,
                'concepts_mastered': s.concepts_mastered
            }
            for i, s in enumerate(sorted_students)
        ]
    
    def get_intervention_recommendations(self,
                                        student_profile: StudentProfile,
                                        student_knowledge: KnowledgeState) -> List[Dict]:
        """
        Generate intervention recommendations for a specific student.
        
        Returns:
            List of recommended interventions
        """
        
        recommendations = []
        
        # Check overall mastery
        if student_profile.overall_mastery < 0.4:
            recommendations.append({
                'priority': 'high',
                'type': 'academic_support',
                'title': 'Schedule one-on-one tutoring',
                'reason': f'{student_profile.name} is struggling with core concepts (mastery: {student_profile.overall_mastery * 100:.0f}%)',
                'actions': [
                    'Review fundamental concepts',
                    'Identify specific learning gaps',
                    'Provide additional practice materials'
                ]
            })
        
        # Check engagement
        if student_profile.last_active:
            days_inactive = (datetime.utcnow() - student_profile.last_active).days
            
            if days_inactive > 7:
                recommendations.append({
                    'priority': 'medium',
                    'type': 'engagement',
                    'title': 'Re-engage student',
                    'reason': f'{student_profile.name} has been inactive for {days_inactive} days',
                    'actions': [
                        'Send check-in message',
                        'Offer flexible schedule options',
                        'Identify barriers to participation'
                    ]
                })
        
        # Check for specific struggling concepts
        weak_concepts = student_knowledge.get_weak_concepts(threshold=0.4)
        
        if len(weak_concepts) > 3:
            recommendations.append({
                'priority': 'medium',
                'type': 'remediation',
                'title': 'Provide targeted remediation',
                'reason': f'{student_profile.name} is struggling with {len(weak_concepts)} concepts',
                'actions': [
                    f'Focus on: {", ".join([c.concept_name for c in weak_concepts[:3]])}',
                    'Provide alternative explanations',
                    'Use different teaching modalities'
                ]
            })
        
        # Check for excellence
        if student_profile.overall_mastery > 0.85 and student_profile.concepts_mastered > 5:
            recommendations.append({
                'priority': 'low',
                'type': 'enrichment',
                'title': 'Provide advanced challenges',
                'reason': f'{student_profile.name} is excelling (mastery: {student_profile.overall_mastery * 100:.0f}%)',
                'actions': [
                    'Offer advanced topics',
                    'Encourage peer tutoring',
                    'Provide independent projects'
                ]
            })
        
        return sorted(recommendations, key=lambda r: {'high': 0, 'medium': 1, 'low': 2}[r['priority']])
    
    def _analyze_concept_difficulty(self,
                                   student_knowledge_states: Dict[str, KnowledgeState]) -> tuple:
        """Identify challenging and well-understood concepts"""
        
        concept_performance = defaultdict(list)
        
        # Collect performance data
        for knowledge in student_knowledge_states.values():
            for concept_id, concept_mastery in knowledge.concepts.items():
                if concept_mastery.attempts > 0:
                    concept_performance[concept_id].append(concept_mastery.mastery_probability)
        
        # Calculate averages
        concept_averages = {
            concept_id: (sum(scores) / len(scores), len(scores))
            for concept_id, scores in concept_performance.items()
            if len(scores) >= 3  # Need at least 3 students
        }
        
        # Identify challenging (<50% avg) and well-understood (>80% avg)
        challenging = [
            {
                'concept_id': cid,
                'concept_name': self.knowledge_graph.get_concept(cid).name if self.knowledge_graph.get_concept(cid) else cid,
                'average_mastery': avg,
                'students_attempted': count
            }
            for cid, (avg, count) in concept_averages.items()
            if avg < 0.5
        ]
        
        well_understood = [
            {
                'concept_id': cid,
                'concept_name': self.knowledge_graph.get_concept(cid).name if self.knowledge_graph.get_concept(cid) else cid,
                'average_mastery': avg,
                'students_attempted': count
            }
            for cid, (avg, count) in concept_averages.items()
            if avg > 0.8
        ]
        
        # Sort by severity/excellence
        challenging.sort(key=lambda x: x['average_mastery'])
        well_understood.sort(key=lambda x: x['average_mastery'], reverse=True)
        
        return challenging[:5], well_understood[:5]
    
    def _identify_top_performers(self,
                                student_profiles: List[StudentProfile],
                                limit: int) -> List[Dict]:
        """Identify top-performing students"""
        
        sorted_students = sorted(
            student_profiles,
            key=lambda s: (s.overall_mastery, s.concepts_mastered),
            reverse=True
        )
        
        return [
            {
                'student_id': s.student_id,
                'student_name': s.name,
                'overall_mastery': s.overall_mastery,
                'concepts_mastered': s.concepts_mastered
            }
            for s in sorted_students[:limit]
        ]
    
    def _identify_students_needing_attention(self,
                                           student_profiles: List[StudentProfile],
                                           student_knowledge_states: Dict[str, KnowledgeState],
                                           limit: int) -> List[Dict]:
        """Identify students who need extra support"""
        
        students_with_scores = []
        
        for profile in student_profiles:
            # Calculate "need" score
            need_score = 0
            reasons = []
            
            # Low mastery
            if profile.overall_mastery < 0.5:
                need_score += (0.5 - profile.overall_mastery) * 100
                reasons.append('low mastery')
            
            # Inactivity
            if profile.last_active:
                days_inactive = (datetime.utcnow() - profile.last_active).days
                if days_inactive > 3:
                    need_score += days_inactive * 2
                    reasons.append(f'inactive {days_inactive} days')
            
            # Struggling concepts
            if profile.student_id in student_knowledge_states:
                knowledge = student_knowledge_states[profile.student_id]
                weak = len(knowledge.get_weak_concepts(threshold=0.4))
                if weak > 2:
                    need_score += weak * 5
                    reasons.append(f'{weak} weak concepts')
            
            if need_score > 0:
                students_with_scores.append({
                    'student_id': profile.student_id,
                    'student_name': profile.name,
                    'need_score': need_score,
                    'reasons': reasons,
                    'overall_mastery': profile.overall_mastery
                })
        
        # Sort by need score
        students_with_scores.sort(key=lambda x: x['need_score'], reverse=True)
        
        return students_with_scores[:limit]
    
    def _analyze_mastery_trend(self, student_profiles: List[StudentProfile]) -> str:
        """Analyze overall mastery trend (would need historical data)"""
        # Placeholder - would compare current to previous period
        avg_mastery = sum(s.overall_mastery for s in student_profiles) / len(student_profiles) if student_profiles else 0
        
        if avg_mastery > 0.7:
            return "improving"
        elif avg_mastery < 0.5:
            return "needs_attention"
        else:
            return "stable"
    
    def _analyze_engagement_trend(self, student_profiles: List[StudentProfile]) -> str:
        """Analyze engagement trend"""
        # Check recent activity
        cutoff = datetime.utcnow() - timedelta(days=7)
        active_count = sum(
            1 for s in student_profiles
            if s.last_active and s.last_active >= cutoff
        )
        
        activity_rate = active_count / len(student_profiles) if student_profiles else 0
        
        if activity_rate > 0.7:
            return "high"
        elif activity_rate < 0.4:
            return "low"
        else:
            return "moderate"
    
    def _create_distribution(self, scores: List[float]) -> Dict:
        """Create distribution buckets for scores"""
        buckets = {
            '0-20%': 0,
            '20-40%': 0,
            '40-60%': 0,
            '60-80%': 0,
            '80-100%': 0
        }
        
        for score in scores:
            pct = score * 100
            if pct < 20:
                buckets['0-20%'] += 1
            elif pct < 40:
                buckets['20-40%'] += 1
            elif pct < 60:
                buckets['40-60%'] += 1
            elif pct < 80:
                buckets['60-80%'] += 1
            else:
                buckets['80-100%'] += 1
        
        return buckets
