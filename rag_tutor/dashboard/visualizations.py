"""
Progress Visualizations
Generate visual representations of learning progress.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta

import sys
sys.path.append('..')

from student_model import KnowledgeState, MasteryLevel


class ProgressVisualizer:
    """
    Generates data structures for progress visualizations.
    Frontend will render these as actual charts.
    """
    
    @staticmethod
    def generate_mastery_timeline(mastery_updates: List[Dict]) -> Dict:
        """
        Generate timeline data for mastery progression.
        
        Args:
            mastery_updates: List of mastery update records
        
        Returns:
            Timeline data structure for line chart
        """
        
        # Sort by timestamp
        sorted_updates = sorted(mastery_updates, key=lambda u: u['timestamp'])
        
        timeline = {
            'type': 'line_chart',
            'title': 'Mastery Progress Over Time',
            'x_axis': 'Time',
            'y_axis': 'Mastery Level',
            'data_points': [
                {
                    'timestamp': update['timestamp'],
                    'mastery': update['new_mastery'],
                    'concept': update.get('concept_id', 'unknown')
                }
                for update in sorted_updates
            ]
        }
        
        return timeline
    
    @staticmethod
    def generate_concept_heatmap(student_knowledge: KnowledgeState) -> Dict:
        """
        Generate heatmap data showing mastery across concepts.
        
        Args:
            student_knowledge: Student's knowledge state
        
        Returns:
            Heatmap data structure
        """
        
        # Group by subject and unit
        hierarchy = {}
        
        for concept in student_knowledge.concepts.values():
            subject = concept.subject
            unit = concept.unit
            
            if subject not in hierarchy:
                hierarchy[subject] = {}
            
            if unit not in hierarchy[subject]:
                hierarchy[subject][unit] = []
            
            hierarchy[subject][unit].append({
                'concept_name': concept.concept_name,
                'mastery': concept.mastery_probability,
                'color_value': ProgressVisualizer._mastery_to_color(concept.mastery_probability)
            })
        
        return {
            'type': 'heatmap',
            'title': 'Concept Mastery Heatmap',
            'hierarchy': hierarchy,
            'legend': {
                'high': 'Mastered (>85%)',
                'medium': 'Proficient (60-85%)',
                'low': 'Developing (<60%)'
            }
        }
    
    @staticmethod
    def generate_progress_pie(student_knowledge: KnowledgeState) -> Dict:
        """
        Generate pie chart of mastery level distribution.
        
        Args:
            student_knowledge: Student's knowledge state
        
        Returns:
            Pie chart data structure
        """
        
        # Count concepts at each level
        level_counts = {
            'Mastered': 0,
            'Proficient': 0,
            'Approaching': 0,
            'Developing': 0,
            'Not Started': 0
        }
        
        for concept in student_knowledge.concepts.values():
            level = concept.mastery_level
            
            if level == MasteryLevel.MASTERED:
                level_counts['Mastered'] += 1
            elif level == MasteryLevel.PROFICIENT:
                level_counts['Proficient'] += 1
            elif level == MasteryLevel.APPROACHING:
                level_counts['Approaching'] += 1
            elif level == MasteryLevel.DEVELOPING:
                level_counts['Developing'] += 1
            else:
                level_counts['Not Started'] += 1
        
        return {
            'type': 'pie_chart',
            'title': 'Learning Progress Distribution',
            'segments': [
                {'label': label, 'value': count, 'percentage': 0}
                for label, count in level_counts.items()
                if count > 0
            ]
        }
    
    @staticmethod
    def generate_weekly_activity(interaction_logs: List[Dict]) -> Dict:
        """
        Generate weekly activity bar chart.
        
        Args:
            interaction_logs: List of interaction log records
        
        Returns:
            Bar chart data structure
        """
        
        # Group by day of week
        daily_counts = {i: 0 for i in range(7)}  # 0=Monday, 6=Sunday
        
        for log in interaction_logs:
            timestamp = datetime.fromisoformat(log['timestamp'])
            day_of_week = timestamp.weekday()
            daily_counts[day_of_week] += 1
        
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        return {
            'type': 'bar_chart',
            'title': 'Weekly Activity Pattern',
            'x_axis': 'Day of Week',
            'y_axis': 'Number of Interactions',
            'bars': [
                {'label': day_names[i], 'value': daily_counts[i]}
                for i in range(7)
            ]
        }
    
    @staticmethod
    def generate_subject_radar(student_knowledge: KnowledgeState) -> Dict:
        """
        Generate radar chart for subject-level mastery.
        
        Args:
            student_knowledge: Student's knowledge state
        
        Returns:
            Radar chart data structure
        """
        
        # Calculate mastery by subject
        subject_mastery = {}
        
        for concept in student_knowledge.concepts.values():
            subject = concept.subject
            
            if subject not in subject_mastery:
                subject_mastery[subject] = []
            
            subject_mastery[subject].append(concept.mastery_probability)
        
        # Calculate averages
        subject_averages = {
            subject: sum(scores) / len(scores) if scores else 0
            for subject, scores in subject_mastery.items()
        }
        
        return {
            'type': 'radar_chart',
            'title': 'Subject Mastery Overview',
            'axes': [
                {'label': subject, 'value': mastery * 100, 'max': 100}
                for subject, mastery in subject_averages.items()
            ]
        }
    
    @staticmethod
    def generate_learning_path_graph(learning_path: List[Dict]) -> Dict:
        """
        Generate directed graph visualization of learning path.
        
        Args:
            learning_path: Ordered list of concepts in learning path
        
        Returns:
            Graph data structure
        """
        
        nodes = [
            {
                'id': step['concept_id'],
                'label': step['concept_name'],
                'difficulty': step['difficulty']
            }
            for step in learning_path
        ]
        
        edges = [
            {
                'from': learning_path[i]['concept_id'],
                'to': learning_path[i + 1]['concept_id']
            }
            for i in range(len(learning_path) - 1)
        ]
        
        return {
            'type': 'directed_graph',
            'title': 'Your Learning Path',
            'nodes': nodes,
            'edges': edges
        }
    
    @staticmethod
    def generate_class_distribution(class_mastery_scores: List[float]) -> Dict:
        """
        Generate distribution histogram for class performance.
        
        Args:
            class_mastery_scores: List of mastery scores for all students
        
        Returns:
            Histogram data structure
        """
        
        # Create bins
        bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        bin_labels = ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%']
        bin_counts = [0] * len(bin_labels)
        
        for score in class_mastery_scores:
            for i in range(len(bins) - 1):
                if bins[i] <= score < bins[i + 1]:
                    bin_counts[i] += 1
                    break
            if score == 1.0:  # Include 100% in last bin
                bin_counts[-1] += 1
        
        return {
            'type': 'histogram',
            'title': 'Class Mastery Distribution',
            'x_axis': 'Mastery Range',
            'y_axis': 'Number of Students',
            'bins': [
                {'label': bin_labels[i], 'count': bin_counts[i]}
                for i in range(len(bin_labels))
            ]
        }
    
    @staticmethod
    def generate_engagement_gauge(engagement_score: float) -> Dict:
        """
        Generate gauge chart for engagement level.
        
        Args:
            engagement_score: Engagement score (0-1)
        
        Returns:
            Gauge chart data structure
        """
        
        # Determine level
        if engagement_score >= 0.8:
            level = 'High'
            color = 'green'
        elif engagement_score >= 0.5:
            level = 'Moderate'
            color = 'yellow'
        else:
            level = 'Low'
            color = 'red'
        
        return {
            'type': 'gauge',
            'title': 'Engagement Level',
            'value': engagement_score * 100,
            'max': 100,
            'level': level,
            'color': color,
            'thresholds': [
                {'value': 50, 'label': 'Low'},
                {'value': 80, 'label': 'Moderate'},
                {'value': 100, 'label': 'High'}
            ]
        }
    
    @staticmethod
    def _mastery_to_color(mastery: float) -> str:
        """Convert mastery level to color code"""
        if mastery >= 0.85:
            return 'high'
        elif mastery >= 0.6:
            return 'medium'
        else:
            return 'low'
    
    @staticmethod
    def export_for_charting_library(viz_data: Dict, library: str = "chartjs") -> Dict:
        """
        Convert visualization data to specific charting library format.
        
        Args:
            viz_data: Visualization data structure
            library: Target library ("chartjs", "plotly", "d3")
        
        Returns:
            Library-specific format
        """
        
        # Example for Chart.js format
        if library == "chartjs":
            viz_type = viz_data.get('type')
            
            if viz_type == 'line_chart':
                return {
                    'type': 'line',
                    'data': {
                        'labels': [p['timestamp'] for p in viz_data['data_points']],
                        'datasets': [{
                            'label': viz_data['title'],
                            'data': [p['mastery'] for p in viz_data['data_points']],
                            'borderColor': 'rgb(75, 192, 192)',
                            'tension': 0.1
                        }]
                    },
                    'options': {
                        'responsive': True,
                        'scales': {
                            'y': {'beginAtZero': True, 'max': 1}
                        }
                    }
                }
            
            elif viz_type == 'pie_chart':
                return {
                    'type': 'pie',
                    'data': {
                        'labels': [s['label'] for s in viz_data['segments']],
                        'datasets': [{
                            'data': [s['value'] for s in viz_data['segments']],
                            'backgroundColor': [
                                'rgb(75, 192, 192)',
                                'rgb(54, 162, 235)',
                                'rgb(255, 205, 86)',
                                'rgb(255, 99, 132)',
                                'rgb(201, 203, 207)'
                            ]
                        }]
                    }
                }
            
            elif viz_type == 'bar_chart':
                return {
                    'type': 'bar',
                    'data': {
                        'labels': [b['label'] for b in viz_data['bars']],
                        'datasets': [{
                            'label': viz_data['title'],
                            'data': [b['value'] for b in viz_data['bars']],
                            'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                            'borderColor': 'rgb(75, 192, 192)',
                            'borderWidth': 1
                        }]
                    }
                }
        
        # Return original if conversion not implemented
        return viz_data
