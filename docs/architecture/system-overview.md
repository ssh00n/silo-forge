# System Overview

This page gives a visual, operator-first view of how Silo Forge is structured.

## 1. Product topology

```mermaid
flowchart LR
    Operator[Operator]

    subgraph SF[Silo Forge]
      UI[Frontend / Next.js]
      API[Backend / FastAPI]
      DB[(Postgres)]
      Q[Redis Queue]
      W[Worker]
      C[contracts/]
    end

    subgraph SYM[Silo Forge Symphony]
      Bridge[Runtime bridge]
      Runner[Symphony runner]
      WS[Workspace]
    end

    Operator --> UI
    UI --> API
    API --> DB
    API --> Q
    W --> Q
    W --> Bridge
    Bridge --> Runner
    Runner --> WS
    Bridge --> API

    C -. schemas .- UI
    C -. schemas .- API
    C -. schemas .- Bridge
```

## 2. Core runtime flow

```mermaid
sequenceDiagram
    participant O as Operator
    participant UI as Frontend
    participant API as Backend
    participant DB as Postgres
    participant RQ as Redis
    participant WK as Worker
    participant SY as Symphony

    O->>UI: Open task
    UI->>API: Load task, silos, runtime runs
    API->>DB: Read silo/task/run state
    DB-->>API: Current state
    API-->>UI: Task + silo options + run history

    O->>UI: Dispatch task to silo
    UI->>API: POST execution-runs/dispatch
    API->>DB: Create TaskExecutionRun
    API->>RQ: Enqueue dispatch job
    API-->>UI: Run queued

    WK->>RQ: Consume job
    WK->>SY: Dispatch request
    SY-->>API: Callback updates
    API->>DB: Update run + activity
    API-->>UI: Refetch/streamed updates
```

## 3. Core operator surfaces

```mermaid
flowchart TD
    Dashboard[Dashboard]
    Silos[Silos overview]
    Detail[Silo detail]
    Task[Board task detail]
    Activity[Activity feed]

    Dashboard -->|Open next silo| Detail
    Dashboard -->|Open active assignment| Task
    Silos --> Detail
    Detail -->|Open current work| Task
    Task -->|Dispatch / retry / continue| Detail
    Task --> Activity
    Detail --> Activity
    Dashboard --> Activity
```

## 4. Responsibility split

```mermaid
flowchart TD
    subgraph Frontend
      F1[silo-ops health taxonomy]
      F2[task demand classification]
      F3[dispatch continuity view-models]
      F4[presentation + operator guidance]
    end

    subgraph Backend
      B1[persistence]
      B2[runtime orchestration]
      B3[metrics read models]
      B4[activity + approvals]
      B5[minimal operational summaries]
    end

    subgraph Symphony
      S1[dispatch intake]
      S2[workspace/run execution]
      S3[callback emission]
    end

    Frontend --> Backend
    Backend --> Symphony
    Symphony --> Backend
```

## 5. What is core vs secondary

### Core UX

- create and configure silos
- inspect silo health and workload
- assign task work to the right silo
- continue or retry on the current silo
- intervene on blocked, failed, or approval-gated runs

### Secondary UX

- silo requests and planning queues
- future capacity planning
- richer recommendation explanation such as switching-cost scoring

## 6. Domain model

```mermaid
flowchart TD
    Org[Organization]
    User[User / Operator]
    Group[Board group]
    Board[Board]
    Task[Task]
    Approval[Approval]
    Activity[Activity event]

    Silo[Silo]
    Role[Silo role]
    Request[Silo request]
    RuntimeOp[Silo runtime operation]
    Run[Task execution run]

    Org --> User
    Org --> Group
    Org --> Board
    Org --> Silo
    Org --> Request

    Group --> Board
    Board --> Task
    Board --> Approval
    Board --> Activity

    Silo --> Role
    Silo --> RuntimeOp
    Silo --> Run

    Task --> Run
    Task --> Approval
    Task --> Activity

    Request -. materializes .-> Silo
    Run --> Activity
    Approval --> Activity
    RuntimeOp --> Activity
```

### Reading the model

- `Silo` is the main operating unit.
- `TaskExecutionRun` is the runtime attempt that joins a task to a silo.
- `SiloRequest` is secondary planning state that can materialize into a silo later.
- `ActivityEvent` is the explainability layer that records what happened across the product.

## 7. Approval and escalation flow

```mermaid
sequenceDiagram
    participant O as Operator
    participant UI as Frontend
    participant API as Backend
    participant RUN as TaskExecutionRun
    participant APP as Approval
    participant ACT as Activity

    O->>UI: Open blocked / failed run
    UI->>API: POST escalate
    API->>RUN: Mark run escalated
    API->>APP: Create pending approval
    API->>ACT: Emit task.execution_run.escalated
    API-->>UI: Updated run + approval state

    O->>UI: Review approval queue
    UI->>API: Approve or reject
    API->>APP: Update approval
    API->>ACT: Emit approval update
    API-->>UI: Approval resolution

    Note over UI,API: Operator can retry or continue the run after approval resolution
```

### Why this matters

- escalation is not an isolated runtime action
- it creates governance state
- governance state flows back into runtime guidance on the dashboard, task detail, and silo detail

## 8. Contract boundary map

```mermaid
flowchart LR
    subgraph Contracts[contracts/]
      EX[execution/*]
      ACT[activity/*]
      Q[queue/*]
      TEL[telemetry/*]
    end

    subgraph FE[Frontend]
      FEGen[generated schemas]
      FEOps[silo-ops + runtime helpers]
    end

    subgraph BE[Backend]
      BESchema[generated_schemas.py]
      BEWrap[contract wrappers / finalizers]
      BEAPI[API + services]
    end

    subgraph SYM[Symphony]
      SYGen[generated schemas]
      SYBridge[dispatch + callback bridge]
    end

    EX --> FEGen
    EX --> BESchema
    EX --> SYGen

    ACT --> FEGen
    ACT --> BESchema

    Q --> BESchema
    Q --> SYGen

    TEL --> BESchema
    TEL --> FEGen

    FEGen --> FEOps
    BESchema --> BEWrap
    BEWrap --> BEAPI
    SYGen --> SYBridge
```

### Boundary rule

- schemas live in one place: `contracts/`
- each service consumes generated artifacts locally
- services do not import each other's runtime code directly

## 9. Multi-service integration map

```mermaid
flowchart LR
    Operator[Operator]

    subgraph ControlPlane[Silo Forge control plane]
      Frontend[Frontend]
      Backend[Backend API]
      Metrics[Read models / metrics]
      Activity[Activity + telemetry]
    end

    subgraph Execution[Silo Forge Symphony]
      Dispatch[Dispatch intake]
      Runtime[Runtime execution]
      Callback[Callback emitter]
    end

    subgraph Infra[Infrastructure]
      PG[(Postgres)]
      Redis[(Redis)]
      GW[Gateways]
    end

    subgraph Future[Future microservices]
      M1[Org automation service]
      M2[Provisioning service]
      M3[Observability service]
    end

    Operator --> Frontend
    Frontend --> Backend
    Backend --> Metrics
    Backend --> Activity
    Backend --> PG
    Backend --> Redis
    Backend --> GW

    Redis --> Dispatch
    Dispatch --> Runtime
    Runtime --> Callback
    Callback --> Backend

    Backend -. contracts / APIs .-> M1
    Backend -. contracts / APIs .-> M2
    Backend -. contracts / APIs .-> M3
```

### Integration direction

- Silo Forge remains the product center and operator surface.
- runtime systems and future microservices should connect through explicit contracts and APIs.
- new services should not fork the core state vocabulary independently.

## Notes

- `silo-forge` is the control plane and product center.
- `silo-forge-symphony` is the execution runtime integration layer.
- `contracts/` is the source-of-truth for cross-service boundaries.
- The product is intentionally moving toward `silo operations first`, not planning-first.
