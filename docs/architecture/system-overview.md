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

## Notes

- `silo-forge` is the control plane and product center.
- `silo-forge-symphony` is the execution runtime integration layer.
- `contracts/` is the source-of-truth for cross-service boundaries.
- The product is intentionally moving toward `silo operations first`, not planning-first.
