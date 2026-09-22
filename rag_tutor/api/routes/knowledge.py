"""Knowledge Graph Routes — real concept data."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter
from typing import Optional
from api.store import GRAPH, MAPPER

router = APIRouter()


@router.get("/concepts")
async def list_concepts(subject: Optional[str] = None):
    concepts = list(GRAPH.concepts.values())
    if subject:
        concepts = [c for c in concepts if c.subject == subject]
    return {
        "concepts": [
            {
                "concept_id": c.concept_id,
                "name": c.name,
                "subject": c.subject,
                "unit": c.unit,
                "difficulty": c.difficulty,
                "bloom_level": c.bloom_level,
                "typical_time_minutes": c.typical_time_minutes,
                "keywords": c.keywords,
                "prerequisites": [p.name for p in GRAPH.get_prerequisites(c.concept_id)]
            }
            for c in concepts
        ]
    }


@router.get("/subjects")
async def list_subjects():
    subjects = list(set(c.subject for c in GRAPH.concepts.values()))
    return {"subjects": subjects}


@router.get("/concepts/{concept_id}/path")
async def get_learning_path(concept_id: str, mastered: str = ""):
    mastered_ids = set(m.strip() for m in mastered.split(",") if m.strip())
    concept = GRAPH.get_concept(concept_id)
    if not concept:
        from fastapi import HTTPException
        raise HTTPException(404, "Concept not found")
    path = MAPPER.find_path_to_concept(concept_id, mastered_ids)
    return {
        "target": concept.name,
        "missing_steps": [
            {"concept_id": c.concept_id, "name": c.name, "difficulty": c.difficulty,
             "estimated_minutes": c.typical_time_minutes}
            for c in path.missing_prerequisites
        ],
        "total_minutes": path.estimated_time_minutes
    }


@router.get("/graph")
async def get_full_graph():
    nodes = [
        {"id": c.concept_id, "label": c.name, "subject": c.subject,
         "unit": c.unit, "difficulty": c.difficulty, "bloom_level": c.bloom_level}
        for c in GRAPH.concepts.values()
    ]
    edges = []
    for source, target, data in GRAPH.graph.edges(data=True):
        edges.append({
            "from": source, "to": target,
            "type": data["relation_type"].value,
            "strength": data.get("strength", 1.0)
        })
    return {"nodes": nodes, "edges": edges}
