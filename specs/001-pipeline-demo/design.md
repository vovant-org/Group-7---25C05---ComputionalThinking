# Design artifacts – Pipeline demo (Lab04)

Chosen from the Lab04 list: user story, sequence diagram, activity diagram (written in Mermaid).
The other artifacts (use case, state machine, package, deployment, ERD, C4) were left out on purpose:
the feature has one actor, no persistent state and no database.

## 1. User story
**As a** user of StoryFrame Studio, **I want** to type one request and see the planned video or the reason it cannot be built, **so that** I know whether to change the request.

Acceptance: see `spec.md` scenarios 1–10.

## 2. Sequence diagram
```mermaid
sequenceDiagram
    actor U as User
    participant UI as Streamlit page / CLI
    participant P as run_pipeline
    participant R as Router
    participant S as Scene Segmenter
    participant B as Budget Optimizer
    participant V as Voice Segmenter
    participant T as Timeline Assembler
    U->>UI: request text and options
    UI->>P: Request, claim fixtures, MockTTS
    P->>R: route(request)
    R-->>P: RouteDecision
    break REJECT or CLARIFY
        P-->>UI: stopped at router, messages
    end
    P->>S: select_claims, build_scenes
    S-->>P: scenes and report
    break fewer than 6 or more than 30 scenes
        P-->>UI: SCENES_INVALID
    end
    P->>B: optimize(scenes, budget, profile)
    B-->>P: OptimizeResult
    break infeasible
        P-->>UI: BUDGET_INFEASIBLE, reason, suggestion
    end
    P->>V: segment_voices(sentences)
    V-->>P: voice units
    P->>T: assemble(scenes, audio durations)
    T-->>P: Timeline and codes
    P-->>UI: PipelineResult (OK or TIMELINE_CHECKS_FAILED)
    UI-->>U: stages, scenes, voice units, timeline bar
```

## 3. Activity diagram
```mermaid
flowchart TD
    A([Request]) --> B[Router: route]
    B --> C{Status}
    C -->|REJECT| X1([Stop: ROUTER_REJECTED])
    C -->|CLARIFY| X2([Stop: ROUTER_CLARIFY])
    C -->|ACCEPT| D[Select claims and build scenes]
    D --> E{6 to 30 scenes?}
    E -->|no| X3([Stop: SCENES_INVALID])
    E -->|yes| F[Resolve budget: request, text, auto]
    F --> G[Optimize render modes]
    G --> H{Feasible?}
    H -->|no| X4([Stop: BUDGET_INFEASIBLE])
    H -->|yes| I[Segment voices, estimate S19]
    I --> J[Get audio durations, assemble timeline]
    J --> K{S12 and S13 hold?}
    K -->|no| X5([Stop: TIMELINE_CHECKS_FAILED, timeline kept])
    K -->|yes| Z([OK: timeline ready])
```
