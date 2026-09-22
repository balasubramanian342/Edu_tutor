"""
Domain Loader
Loads knowledge graphs from structured definitions (JSON/YAML).
"""

import json
from pathlib import Path
from typing import Dict, List
from .concept_graph import ConceptGraph, ConceptNode, RelationType


class DomainLoader:
    """
    Loads domain knowledge graphs from configuration files.
    """
    
    @staticmethod
    def load_from_json(filepath: str) -> ConceptGraph:
        """
        Load knowledge graph from JSON file.
        
        Expected format:
        {
            "concepts": [
                {
                    "concept_id": "ds_array",
                    "name": "Arrays",
                    "subject": "Data Structures",
                    "unit": "Unit 1",
                    "bloom_level": 2,
                    "difficulty": "easy",
                    "description": "...",
                    "keywords": ["array", "index", "element"],
                    "typical_time_minutes": 45
                }
            ],
            "relationships": [
                {
                    "source": "ds_variable",
                    "target": "ds_array",
                    "type": "prerequisite",
                    "strength": 1.0
                }
            ]
        }
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        graph = ConceptGraph()
        
        # Load concepts
        for concept_data in data.get('concepts', []):
            concept = ConceptNode(
                concept_id=concept_data['concept_id'],
                name=concept_data['name'],
                subject=concept_data['subject'],
                unit=concept_data['unit'],
                bloom_level=concept_data.get('bloom_level', 2),
                difficulty=concept_data.get('difficulty', 'medium'),
                description=concept_data.get('description', ''),
                keywords=concept_data.get('keywords', []),
                typical_time_minutes=concept_data.get('typical_time_minutes', 30),
                practice_questions_available=concept_data.get('practice_questions_available', 0)
            )
            graph.add_concept(concept)
        
        # Load relationships
        for rel_data in data.get('relationships', []):
            relation_type = RelationType(rel_data['type'])
            graph.add_relationship(
                rel_data['source'],
                rel_data['target'],
                relation_type,
                rel_data.get('strength', 1.0)
            )
        
        return graph
    
    @staticmethod
    def save_to_json(graph: ConceptGraph, filepath: str):
        """Save knowledge graph to JSON file"""
        data = graph.export_to_dict()
        
        # Convert to expected format
        output = {
            'concepts': list(data['nodes'].values()),
            'relationships': data['edges']
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
    
    @staticmethod
    def create_sample_cs_graph() -> ConceptGraph:
        """
        Create a sample Computer Science knowledge graph for testing.
        Covers basic Data Structures concepts.
        """
        graph = ConceptGraph()
        
        # Foundational concepts
        concepts_data = [
            # Unit 1: Basics
            {
                'concept_id': 'ds_variable',
                'name': 'Variables and Data Types',
                'subject': 'Data Structures',
                'unit': 'Unit 1',
                'bloom_level': 1,
                'difficulty': 'easy',
                'description': 'Understanding variables, primitive types, and memory',
                'keywords': ['variable', 'int', 'float', 'string', 'memory'],
                'typical_time_minutes': 30
            },
            {
                'concept_id': 'ds_array',
                'name': 'Arrays',
                'subject': 'Data Structures',
                'unit': 'Unit 1',
                'bloom_level': 2,
                'difficulty': 'easy',
                'description': 'Fixed-size sequential data structure',
                'keywords': ['array', 'index', 'element', 'contiguous'],
                'typical_time_minutes': 45
            },
            {
                'concept_id': 'ds_complexity',
                'name': 'Time Complexity',
                'subject': 'Data Structures',
                'unit': 'Unit 1',
                'bloom_level': 3,
                'difficulty': 'medium',
                'description': 'Big O notation and algorithm efficiency',
                'keywords': ['big o', 'time complexity', 'O(n)', 'O(1)'],
                'typical_time_minutes': 60
            },
            
            # Unit 2: Linear Structures
            {
                'concept_id': 'ds_linked_list',
                'name': 'Linked Lists',
                'subject': 'Data Structures',
                'unit': 'Unit 2',
                'bloom_level': 3,
                'difficulty': 'medium',
                'description': 'Dynamic sequential data structure with pointers',
                'keywords': ['linked list', 'node', 'pointer', 'head', 'tail'],
                'typical_time_minutes': 60
            },
            {
                'concept_id': 'ds_stack',
                'name': 'Stack',
                'subject': 'Data Structures',
                'unit': 'Unit 2',
                'bloom_level': 2,
                'difficulty': 'medium',
                'description': 'LIFO data structure',
                'keywords': ['stack', 'push', 'pop', 'LIFO', 'top'],
                'typical_time_minutes': 45
            },
            {
                'concept_id': 'ds_queue',
                'name': 'Queue',
                'subject': 'Data Structures',
                'unit': 'Unit 2',
                'bloom_level': 2,
                'difficulty': 'medium',
                'description': 'FIFO data structure',
                'keywords': ['queue', 'enqueue', 'dequeue', 'FIFO', 'front', 'rear'],
                'typical_time_minutes': 45
            },
            
            # Unit 3: Recursion & Advanced
            {
                'concept_id': 'ds_recursion',
                'name': 'Recursion',
                'subject': 'Data Structures',
                'unit': 'Unit 3',
                'bloom_level': 4,
                'difficulty': 'hard',
                'description': 'Function calling itself with base case',
                'keywords': ['recursion', 'base case', 'recursive call', 'stack frame'],
                'typical_time_minutes': 90
            },
            {
                'concept_id': 'ds_tree',
                'name': 'Binary Trees',
                'subject': 'Data Structures',
                'unit': 'Unit 3',
                'bloom_level': 4,
                'difficulty': 'hard',
                'description': 'Hierarchical data structure',
                'keywords': ['tree', 'root', 'leaf', 'parent', 'child', 'binary'],
                'typical_time_minutes': 75
            },
            {
                'concept_id': 'ds_sorting',
                'name': 'Sorting Algorithms',
                'subject': 'Data Structures',
                'unit': 'Unit 3',
                'bloom_level': 3,
                'difficulty': 'medium',
                'description': 'Algorithms to order elements',
                'keywords': ['sorting', 'bubble sort', 'merge sort', 'quick sort'],
                'typical_time_minutes': 90
            }
        ]
        
        # Add concepts
        for data in concepts_data:
            concept = ConceptNode(**data)
            graph.add_concept(concept)
        
        # Add prerequisite relationships
        prerequisites = [
            # Unit 1
            ('ds_variable', 'ds_array', 1.0),
            ('ds_variable', 'ds_complexity', 0.5),
            
            # Unit 2
            ('ds_array', 'ds_linked_list', 0.8),
            ('ds_variable', 'ds_linked_list', 1.0),
            ('ds_array', 'ds_stack', 0.7),
            ('ds_linked_list', 'ds_stack', 0.6),
            ('ds_array', 'ds_queue', 0.7),
            ('ds_linked_list', 'ds_queue', 0.6),
            
            # Unit 3
            ('ds_linked_list', 'ds_recursion', 0.6),
            ('ds_stack', 'ds_recursion', 0.8),
            ('ds_recursion', 'ds_tree', 0.9),
            ('ds_linked_list', 'ds_tree', 0.7),
            ('ds_array', 'ds_sorting', 0.9),
            ('ds_complexity', 'ds_sorting', 0.8),
            ('ds_recursion', 'ds_sorting', 0.7)
        ]
        
        for source, target, strength in prerequisites:
            graph.add_relationship(source, target, RelationType.PREREQUISITE, strength)
        
        # Add some related-to relationships
        related = [
            ('ds_stack', 'ds_queue', RelationType.RELATED_TO, 0.8),
            ('ds_array', 'ds_linked_list', RelationType.RELATED_TO, 0.7)
        ]
        
        for source, target, rel_type, strength in related:
            graph.add_relationship(source, target, rel_type, strength)
        
        return graph
    
    @staticmethod
    def validate_graph(graph: ConceptGraph) -> Dict[str, List]:
        """
        Validate knowledge graph for common issues.
        Returns dict of issues found.
        """
        issues = {
            'cycles': [],
            'orphaned_concepts': [],
            'missing_prerequisites': [],
            'difficulty_inversions': []
        }
        
        # Check for cycles
        cycles = graph.detect_cycles()
        if cycles:
            issues['cycles'] = cycles
        
        # Check for orphaned concepts (no connections)
        for concept_id in graph.concepts:
            prereqs = graph.get_prerequisites(concept_id)
            dependents = graph.get_dependents(concept_id)
            
            if not prereqs and not dependents and len(graph.concepts) > 1:
                issues['orphaned_concepts'].append(concept_id)
        
        # Check difficulty inversions (hard prereq for easy concept)
        difficulty_order = {'easy': 0, 'medium': 1, 'hard': 2}
        
        for concept_id, concept in graph.concepts.items():
            prereqs = graph.get_prerequisites(concept_id)
            
            for prereq in prereqs:
                if difficulty_order[prereq.difficulty] > difficulty_order[concept.difficulty]:
                    issues['difficulty_inversions'].append(
                        f"{prereq.name} ({prereq.difficulty}) -> {concept.name} ({concept.difficulty})"
                    )
        
        return issues
