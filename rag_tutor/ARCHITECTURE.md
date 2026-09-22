# System Architecture

## Overview

The RAG Tutor is a comprehensive adaptive learning system that combines retrieval-augmented generation, knowledge graphs, educational psychology principles, and real-time adaptation to provide personalized instruction.

## Core Components

### 1. Student Modeling Layer
**Purpose**: Model individual student characteristics and track learning progress

**Components**:
- `StudentProfile`: Demographics, cognitive traits (working memory, abstract reasoning, metacognition), learning style preferences
- `KnowledgeState`: Fine-grained mastery tracking for every concept using Bayesian Knowledge Tracing
- `ConceptMastery`: Individual concept tracking with BKT parameters, spaced repetition scheduling

**Key Algorithms**:
- Bayesian Knowledge Tracing (BKT) with P(learn), P(slip), P(guess) parameters
- SM-2 spaced repetition algorithm
- Temporal decay functions for memory retention

### 2. Knowledge Graph Layer
**Purpose**: Represent domain structure and prerequisite relationships

**Components**:
- `ConceptGraph`: NetworkX directed graph with typed relationships
- `PrerequisiteMapper`: Path finding and learning sequence optimization
- `DomainLoader`: JSON persistence and sample domain creation

**Relationships**:
- PREREQUISITE: Foundational dependencies
- RELATED_TO: Conceptual connections
- PART_OF: Hierarchical composition
- EXAMPLE_OF, CONTRASTS_WITH: Pedagogical links

### 3. Gap Analysis Layer
**Purpose**: Diagnose knowledge gaps and generate remediation plans

**Components**:
- `GapAnalyzer`: Identifies 5 types of gaps with severity scoring
- `RemediationPlanner`: Creates personalized learning sequences

**Gap Types**:
1. Missing Prerequisite: Concept never encountered
2. Weak Foundation: Partially learned prerequisite
3. Skill Decay: Previously mastered but forgotten
4. Comprehension Gap: Can't apply knowledge
5. Conceptual Misunderstanding: Wrong mental model

### 4. RAG Retrieval Layer
**Purpose**: Retrieve relevant content from course materials

**Components**:
- `DocumentLoader`: Multi-format ingestion with page tracking
- `Chunker`: Sliding-window chunking with metadata
- `HybridRetriever`: Dense (embeddings) + Sparse (BM25) fusion

**Retrieval Pipeline**:
```
Query → [Dense Retrieval, BM25 Retrieval] → RRF Fusion → Cross-encoder Rerank → Top-K
```

**Gap-Aware Enhancement**: Query expansion/biasing based on diagnosed gaps

### 5. Adaptive Teaching Layer
**Purpose**: Generate personalized explanations and teaching content

**Components**:
- `TeachingAgent`: Main orchestrator
- `ExplanationGenerator`: 7 explanation styles
- `PedagogyEngine`: Educational theory application

**Explanation Styles**:
- Concise, Detailed, Step-by-step, Example-driven
- Analogy-based, Visual, Interactive

**Pedagogical Strategies**:
- Bloom's Taxonomy (6 levels)
- Cognitive Load Theory (chunking, worked examples)
- Zone of Proximal Development (optimal difficulty)
- Scaffolding with fading

### 6. Assessment Layer
**Purpose**: Generate and grade formative assessments

**Components**:
- `QuestionGenerator`: 9 question types aligned with Bloom's
- `AutoGrader`: Multi-strategy grading
- `AdaptiveTest`: IRT-based adaptive testing

**Question Types**:
- Multiple Choice, True/False, Fill-in-blank
- Short Answer, Code Completion, Code Debugging
- Problem Solving, Essay, Code-from-scratch

**Grading Strategies**:
- Exact matching (objective)
- Fuzzy matching (fill-in-blank)
- Keyword extraction (short answer)
- LLM-based rubric grading (essay)

### 7. Mastery Update Layer
**Purpose**: Update knowledge state based on performance

**Components**:
- `MasteryTracker`: Coordinates all updates
- `IRTEngine`: 3-parameter logistic model
- `AdaptationEngine`: Real-time adaptation decisions

**Update Triggers**:
- Assessment results
- Practice attempts
- Teaching interactions
- Temporal decay

**Adaptation Triggers**:
- Performance decline/excellence
- Engagement drop
- Frustration detection
- Mastery achievement

### 8. Dashboard Layer
**Purpose**: Visualize progress and provide insights

**Components**:
- `StudentDashboard`: Personal progress view
- `TeacherDashboard`: Class-level analytics
- `ProgressVisualizer`: Chart data generation

**Visualizations**:
- Mastery timeline, Concept heatmap, Progress pie
- Weekly activity, Subject radar, Learning path graph
- Class distribution, Engagement gauge

### 9. Persistence Layer
**Purpose**: Store and retrieve all data

**Components**:
- SQLAlchemy ORM models
- Database connection management
- Transaction handling

**Tables**:
- students, concept_mastery, interaction_logs
- test_sessions, concepts, concept_relationships
- questions, mastery_updates

### 10. API Layer
**Purpose**: Expose functionality via REST endpoints

**Framework**: FastAPI with automatic OpenAPI documentation

**Route Groups**:
- `/api/students`: Student CRUD operations
- `/api/teaching`: Question answering, explanations
- `/api/assessment`: Test creation, grading
- `/api/dashboard`: Analytics and reports
- `/api/knowledge`: Knowledge graph queries

## Data Flow

### Teaching Flow
```
1. Student asks question
2. Identify target concept
3. Analyze knowledge gaps
4. Perform gap-aware retrieval
5. Determine pedagogical strategy
6. Generate adaptive explanation
7. Log interaction
8. Update engagement metrics
```

### Assessment Flow
```
1. Start test (diagnostic/formative/summative)
2. Estimate initial ability (IRT)
3. Select optimal difficulty question
4. Student submits answer
5. Grade automatically
6. Update ability estimate
7. Update concept mastery (BKT)
8. Determine next question or end test
9. Generate results and recommendations
```

### Adaptation Flow
```
1. Monitor performance continuously
2. Detect adaptation triggers
3. Evaluate current state
4. Make adaptation decision
5. Adjust difficulty/pace/modality/scaffolding
6. Apply changes to next interaction
7. Track adaptation effectiveness
```

## Educational Theory Integration

### Bayesian Knowledge Tracing
- Models P(mastery) as hidden variable
- Updates based on observed correctness
- Accounts for guessing and slipping

### Item Response Theory
- 3-parameter logistic model
- Estimates student ability (theta)
- Calibrates item difficulty, discrimination, guessing

### Bloom's Taxonomy
- 6 cognitive levels: Remember → Understand → Apply → Analyze → Evaluate → Create
- Questions and scaffolding aligned to levels
- Gradual progression through levels

### Cognitive Load Theory
- Adjusts chunk size to working memory
- Uses worked examples for complex concepts
- Reduces extraneous cognitive load

### Zone of Proximal Development
- Targets 70-80% success rate
- Provides support for challenging tasks
- Gradually fades scaffolding

## Deployment Architecture

### Development
```
Local Machine
├── Python application
├── SQLite database
├── Chroma vector store
└── BM25 index files
```

### Production (Recommended)
```
Load Balancer
├── API Servers (FastAPI + Uvicorn)
├── PostgreSQL (student data)
├── Chroma/Pinecone (vector search)
├── Redis (caching, sessions)
└── Background Workers (mastery decay, analytics)
```

## Extensibility Points

1. **LLM Integration**: Plug in any LLM (Gemini, OpenAI, Anthropic, local models)
2. **Retrieval Backend**: Swap Chroma for Pinecone, Weaviate, etc.
3. **Question Types**: Add new question formats
4. **Explanation Styles**: Define custom teaching approaches
5. **Gap Types**: Implement domain-specific gap detection
6. **Visualization**: Add custom chart types

## Performance Considerations

- **Retrieval**: <200ms for hybrid search + rerank
- **Teaching**: <500ms with LLM, <100ms template-based
- **Assessment**: <50ms for objective grading
- **Mastery Update**: <10ms for BKT update
- **Adaptation**: <20ms for decision logic

## Security Considerations

- Student PII stored encrypted
- API authentication required (not implemented in prototype)
- LLM prompts sanitized
- File uploads validated
- Rate limiting on API endpoints

## Future Enhancements

1. Multi-modal content (video, audio, interactive)
2. Peer learning and collaboration
3. Advanced analytics (learning curves, intervention effectiveness)
4. Mobile app support
5. Voice interaction
6. Real-time collaborative learning
