"""
Interaction Logging
Records all student-system interactions for analytics and adaptation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, List


class InteractionType(Enum):
    """Types of student-system interactions"""
    QUESTION_ASKED = "question_asked"
    EXPLANATION_RECEIVED = "explanation_received"
    PRACTICE_ATTEMPTED = "practice_attempted"
    ASSESSMENT_TAKEN = "assessment_taken"
    HINT_REQUESTED = "hint_requested"
    FEEDBACK_GIVEN = "feedback_given"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


@dataclass
class InteractionLog:
    """
    Single interaction record.
    Persisted for learning analytics and model improvement.
    """
    student_id: str
    interaction_type: InteractionType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Context
    concept_id: Optional[str] = None
    concept_name: Optional[str] = None
    subject: Optional[str] = None
    unit: Optional[str] = None
    
    # Content
    student_input: Optional[str] = None
    system_response: Optional[str] = None
    
    # Metadata
    difficulty: Optional[str] = None  # easy, medium, hard
    was_correct: Optional[bool] = None
    confidence_score: Optional[float] = None  # How confident the system was (0-1)
    
    # Performance
    response_time_seconds: Optional[float] = None
    num_hints_used: int = 0
    
    # Retrieval metadata (for RAG transparency)
    retrieved_chunks: Optional[List[str]] = None
    retrieval_scores: Optional[List[float]] = None
    
    # Session
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'student_id': self.student_id,
            'interaction_type': self.interaction_type.value,
            'timestamp': self.timestamp.isoformat(),
            'concept_id': self.concept_id,
            'concept_name': self.concept_name,
            'subject': self.subject,
            'unit': self.unit,
            'student_input': self.student_input,
            'system_response': self.system_response,
            'difficulty': self.difficulty,
            'was_correct': self.was_correct,
            'confidence_score': self.confidence_score,
            'response_time_seconds': self.response_time_seconds,
            'num_hints_used': self.num_hints_used,
            'retrieved_chunks': self.retrieved_chunks,
            'retrieval_scores': self.retrieval_scores,
            'session_id': self.session_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'InteractionLog':
        data = data.copy()
        data['interaction_type'] = InteractionType(data['interaction_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class InteractionLogger:
    """
    Manages interaction logging with batching and persistence.
    """
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self.buffer: List[InteractionLog] = []
        self.buffer_size = 10  # Flush after 10 interactions
    
    def log(self, interaction: InteractionLog):
        """Add interaction to buffer"""
        self.buffer.append(interaction)
        
        if len(self.buffer) >= self.buffer_size:
            self.flush()
    
    def flush(self):
        """Persist buffered interactions"""
        if not self.buffer:
            return
        
        if self.storage_path:
            # In production, would write to database
            # For now, append to JSON file
            import json
            from pathlib import Path
            
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Append to file
            with open(path, 'a', encoding='utf-8') as f:
                for interaction in self.buffer:
                    f.write(json.dumps(interaction.to_dict()) + '\n')
        
        self.buffer.clear()
    
    def get_recent_interactions(self, student_id: str, limit: int = 50) -> List[InteractionLog]:
        """Retrieve recent interactions for a student"""
        if not self.storage_path:
            return []
        
        import json
        from pathlib import Path
        
        path = Path(self.storage_path)
        if not path.exists():
            return []
        
        interactions = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line.strip())
                if data['student_id'] == student_id:
                    interactions.append(InteractionLog.from_dict(data))
        
        # Return most recent
        interactions.sort(key=lambda x: x.timestamp, reverse=True)
        return interactions[:limit]
    
    def get_concept_history(self, student_id: str, concept_id: str) -> List[InteractionLog]:
        """Get all interactions for a specific concept"""
        if not self.storage_path:
            return []
        
        import json
        from pathlib import Path
        
        path = Path(self.storage_path)
        if not path.exists():
            return []
        
        interactions = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line.strip())
                if data['student_id'] == student_id and data.get('concept_id') == concept_id:
                    interactions.append(InteractionLog.from_dict(data))
        
        interactions.sort(key=lambda x: x.timestamp)
        return interactions
