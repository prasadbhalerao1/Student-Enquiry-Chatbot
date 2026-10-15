Written for: engineers and reviewers reading this repository for the first time.

# System Architecture

A teacher-facing student information assistant for a third-year CSBS department.
This document explains how the system is put together and, where a decision was
not obvious, why it was made that way.

> All student records in this system are **synthetic**. Authentication is a
> **demonstration selector**, not real authentication. See
> [Security model](#6-security-model).

---

## Contents

1. [The one-paragraph version](#1-the-one-paragraph-version)
2. [System context](#2-system-context)
3. [Component architecture](#3-component-architecture)
4. [Data model](#4-data-model)
5. [Request lifecycle](#5-request-lifecycle)
6. [Security model](#6-security-model)
7. [AI architecture](#7-ai-architecture)
8. [Streaming protocol](#8-streaming-protocol)
9. [Calculation semantics](#9-calculation-semantics)
10. [Deployment topology](#10-deployment-topology)
11. [Design decisions](#11-design-decisions)

---

## 1. The one-paragraph version

A Next.js frontend talks to a FastAPI backend over HTTPS with a signed session
cookie. The backend resolves each teacher's permitted subjects from the database
on **every** request, then serves only records inside that scope. An AI assistant
answers natural-language questions by calling a fixed set of thirteen
database-backed tools — never SQL — each of which re-checks authorization before
reading. Model responses stream token-by-token over Server-Sent Events. The model
provider is chosen per request from the teacher's own API key, or from a single
server-configured fallback.

---

## 2. System context

```mermaid
graph LR
    T["👤 Faculty member<br/>(browser)"]

    subgraph VERCEL["Vercel"]
        FE["Next.js frontend<br/>9 pages · SSR + client"]
        BE["FastAPI backend<br/>22 endpoints · ASGI"]
    end

    DB[("Neon PostgreSQL<br/>11 tables · 27,975 rows")]
    AI["AI provider<br/>OpenAI · Anthropic · Gemini<br/>Groq · Ollama · …"]

    T -->|"HTTPS"| FE
    FE -->|"fetch + session cookie<br/>(SameSite=None, Secure)"| BE
    BE -->|"SQLAlchemy, parameterized"| DB
    BE -->|"LangChain, per-request key"| AI
    AI -.->|"SSE token stream"| BE
    BE -.->|"SSE passthrough"| FE

    style T fill:#e6f2f1,stroke:#0f766e
    style FE fill:#fff,stroke:#5c6b77
    style BE fill:#fff,stroke:#5c6b77
    style DB fill:#f1f3f5,stroke:#5c6b77
    style AI fill:#f1f3f5,stroke:#5c6b77
```

**Trust boundaries.** The browser is untrusted: it supplies a session cookie and
nothing else that matters. The frontend never decides what a teacher may see —
it renders what the backend returns. The AI provider is untrusted with respect to
authorization: the model can *ask* for any subject, and the backend refuses
anything outside scope.

---

## 3. Component architecture

```mermaid
graph TD
    subgraph FRONTEND["Frontend — Next.js 16 / React 19 / TS"]
        PAGES["app/<br/>dashboard · subjects · attendance<br/>students · performance · assignments<br/>extracurricular · assistant · settings"]
        SHELL["components/<br/>AppShell · AuthGate · SessionProvider<br/>UI primitives"]
        HOOKS["lib/<br/>api.ts · use-api.ts · use-chat.ts (SSE parser)"]
        PAGES --> SHELL
        PAGES --> HOOKS
    end

    subgraph BACKEND["Backend — FastAPI / Python 3.12"]
        ROUTES["api/routes/<br/>auth · academics · chat"]
        DEPS["api/dependencies.py<br/>session → principal · rate limits"]
        SEC["core/security.py<br/>TeacherPrincipal<br/>require_subject / require_student"]
        SVC["services/<br/>analytics.py<br/>attendance_math.py"]
        AILAYER["ai/<br/>provider_factory · model_registry<br/>tools (13) · orchestration"]
        PROMPT["prompts/<br/>teacher_assistant.py"]
        MODELS["models/ · schemas/<br/>ORM + Pydantic v2"]

        ROUTES --> DEPS
        DEPS --> SEC
        ROUTES --> SVC
        ROUTES --> AILAYER
        AILAYER --> PROMPT
        AILAYER --> SEC
        AILAYER --> SVC
        SVC --> MODELS
    end

    HOOKS -->|"HTTPS + cookie"| ROUTES
    MODELS --> DB[("PostgreSQL")]

    style FRONTEND fill:#f6f7f8,stroke:#c7d0d7
    style BACKEND fill:#f6f7f8,stroke:#c7d0d7
    style SEC fill:#e6f2f1,stroke:#0f766e,stroke-width:2px
    style SVC fill:#e6f2f1,stroke:#0f766e
```

Two things are deliberate here:

- **`core/security.py` is the only place authorization is decided.** Routes and
  AI tools both call into it. There is no second implementation to drift.
- **`services/` is shared by routes and AI tools.** The number a teacher sees on
  the dashboard and the number the assistant quotes come from the same function,
  so they cannot disagree.

### Directory map

```
backend/app/
├── main.py                 app, CORS, body-size limit, security headers
├── api/
│   ├── routes/             auth.py · academics.py · chat.py
│   └── dependencies.py     current_teacher, rate limiters
├── core/
│   ├── config.py           settings (env-driven)
│   ├── db.py               engine, session, Base
│   ├── security.py         ★ TeacherPrincipal + all scope checks
│   └── logging.py          credential-redacting log filter
├── models/                 11 SQLAlchemy tables + CHECK constraints
├── schemas/                Pydantic v2 request/response models
├── services/
│   ├── attendance_math.py  ★ exact Fraction arithmetic
│   └── analytics.py        all business queries
├── ai/
│   ├── provider_factory.py build a chat model; SSRF-validated endpoints
│   ├── model_registry.py   per-provider capabilities
│   ├── tools.py            ★ 13 scoped tools; no SQL tool
│   └── orchestration.py    tool loop + SSE streaming
└── prompts/
    └── teacher_assistant.py  versioned system prompt
```

---

## 4. Data model

```mermaid
erDiagram
    TEACHERS ||--o{ TEACHER_SUBJECTS : "is assigned"
    SUBJECTS ||--o{ TEACHER_SUBJECTS : "taught by"
    SUBJECTS ||--o{ ATTENDANCE : "has"
    SUBJECTS ||--o{ ASSESSMENTS : "has"
    SUBJECTS ||--o{ ASSIGNMENTS : "has"
    STUDENTS ||--o{ ATTENDANCE : "has"
    STUDENTS ||--o{ GRADES : "receives"
    STUDENTS ||--o{ STUDENT_ASSIGNMENTS : "submits"
    STUDENTS ||--o{ STUDENT_ACTIVITIES : "participates"
    ASSESSMENTS ||--o{ GRADES : "scored in"
    ASSIGNMENTS ||--o{ STUDENT_ASSIGNMENTS : "submitted as"
    EXTRACURRICULAR_ACTIVITIES ||--o{ STUDENT_ACTIVITIES : "recorded as"

    TEACHERS {
        string teacher_id PK
        string full_name
        string designation
        bool is_department_coordinator
    }
    SUBJECTS {
        string subject_code PK
        string subject_name
        string subject_type "Theory|Lab"
    }
    TEACHER_SUBJECTS {
        int id PK
        string teacher_id FK
        string subject_code FK
    }
    STUDENTS {
        string student_id PK
        string roll_number UK
        string division "A|B|C"
    }
    ATTENDANCE {
        string student_id FK
        string subject_code FK
        int classes_conducted "CHECK > 0"
        int classes_attended "CHECK 0..conducted"
    }
    ASSESSMENTS {
        string assessment_id PK
        int max_marks
        float weightage
    }
    GRADES {
        string assessment_id FK
        string student_id FK
        float marks_obtained "NULL = not evaluated"
        bool is_absent
    }
    ASSIGNMENTS {
        string assignment_id PK
        date due_date
    }
    STUDENT_ASSIGNMENTS {
        string assignment_id FK
        string student_id FK
        string status "pending|submitted|evaluated"
        date submission_date
        float marks_obtained
    }
    STUDENT_ACTIVITIES {
        string activity_id FK
        string student_id FK
        string role
        string achievement "nullable"
    }
```

`TEACHER_SUBJECTS` is the **authorization table**. It is the single source of
truth for what a teacher may see, read fresh on every request. Subject-to-faculty
mapping appears nowhere else — not in the frontend, not in a config file, not in
the AI prompt.

### Invariants enforced by the database

Application bugs cannot violate these, because PostgreSQL rejects the write:

```sql
CHECK (classes_conducted > 0)
CHECK (classes_attended BETWEEN 0 AND classes_conducted)
CHECK (status IN ('pending','submitted','evaluated'))
CHECK (marks_obtained IS NULL OR marks_obtained >= 0)
UNIQUE (student_id, subject_code)      -- one attendance row per pair
UNIQUE (teacher_id, subject_code)      -- no duplicate assignments
```

---

## 5. Request lifecycle

Every data request takes the same five steps. Nothing short-circuits them.

```mermaid
sequenceDiagram
    participant B as Browser
    participant R as Route
    participant D as dependencies.py
    participant S as security.py
    participant A as analytics.py
    participant DB as PostgreSQL

    B->>R: GET /api/subjects/CB3202T/attendance<br/>Cookie: csbs_faculty_session=…
    R->>D: current_teacher()
    D->>D: verify cookie signature (itsdangerous)
    Note over D: forged / expired → 401
    D->>DB: SELECT subject_code FROM teacher_subjects<br/>WHERE teacher_id = ?
    DB-->>D: {CB3202L, CB3202T}
    D-->>R: TeacherPrincipal(scope)
    R->>S: principal.require_subject("CB3202T")
    Note over S: not in scope → 403<br/>(same 403 for "does not exist",<br/>so the catalogue cannot be enumerated)
    S-->>R: ok
    R->>A: subject_attendance(db, code, threshold, …)
    A->>DB: parameterized SELECT, paginated
    DB-->>A: rows
    A->>A: attendance_math.percentage() — exact Fraction
    A-->>R: Page[AttendanceRow]
    R-->>B: 200 + Cache-Control: no-store
```

**Why the scope is re-read every request** rather than baked into the cookie: a
cookie issued before a teaching assignment changed would carry stale permissions
until it expired. Reading from `teacher_subjects` costs one indexed query and
makes revocation immediate.

---

## 6. Security model

```mermaid
graph TD
    REQ["Incoming request"]
    C1{"Valid signed<br/>session cookie?"}
    C2{"Teacher still<br/>exists?"}
    C3{"Subject in<br/>teacher_subjects?"}
    C4{"Student enrolled in<br/>one of those subjects?"}
    C5{"Coordinator role<br/>required?"}
    OK["Serve only<br/>permitted records"]
    D401["401 Unauthorized"]
    D403["403 Forbidden"]

    REQ --> C1
    C1 -->|no| D401
    C1 -->|yes| C2
    C2 -->|no| D401
    C2 -->|yes| C3
    C3 -->|no| D403
    C3 -->|yes| C4
    C4 -->|no| D403
    C4 -->|yes| C5
    C5 -->|"yes & not coordinator"| D403
    C5 -->|otherwise| OK

    style D401 fill:#fdeceb,stroke:#b4231f
    style D403 fill:#fdeceb,stroke:#b4231f
    style OK fill:#e8f5ec,stroke:#15803d
```

### What is never trusted

| Input | Treatment |
|---|---|
| `teacher_id` in a body, query or chat message | **Ignored.** Identity comes only from the signed cookie. |
| `subject_code` in a URL | Validated by regex, then checked against the DB scope. |
| `student_id` in a URL | Checked for enrollment in a subject the teacher teaches. |
| A `system` role in the chat transcript | Rejected by the Pydantic schema (422). |
| Text inside tool results or student records | Treated as data. It cannot grant permissions. |
| A model's choice to call a tool | The tool re-checks scope itself before reading. |

### Defence in depth

```mermaid
graph LR
    L1["1 · Pydantic schema<br/>regex-validated IDs<br/>size limits"]
    L2["2 · Signed cookie<br/>HttpOnly · 8h · Secure"]
    L3["3 · TeacherPrincipal<br/>scope from DB"]
    L4["4 · Per-tool recheck<br/>model not trusted"]
    L5["5 · DB constraints<br/>CHECK · UNIQUE · FK"]

    L1 --> L2 --> L3 --> L4 --> L5

    style L3 fill:#e6f2f1,stroke:#0f766e,stroke-width:2px
    style L4 fill:#e6f2f1,stroke:#0f766e,stroke-width:2px
```

The system prompt is a **behavioural** control, not a security control. If the
model ignored every instruction in it, the tools would still refuse out-of-scope
reads. This is verified by tests that call tools directly, bypassing the model.

### Credential handling

```mermaid
graph LR
    K["Teacher's API key"]
    MEM["React state<br/>(memory only)"]
    REQ["POST /api/chat<br/>over HTTPS"]
    CLIENT["LangChain client<br/>built for this call"]
    GONE["discarded"]

    K --> MEM --> REQ --> CLIENT --> GONE

    NO1["✗ localStorage"]
    NO2["✗ cookie / URL"]
    NO3["✗ database"]
    NO4["✗ logs"]

    MEM -.-> NO1
    MEM -.-> NO2
    REQ -.-> NO3
    REQ -.-> NO4

    style NO1 fill:#fdeceb,stroke:#b4231f
    style NO2 fill:#fdeceb,stroke:#b4231f
    style NO3 fill:#fdeceb,stroke:#b4231f
    style NO4 fill:#fdeceb,stroke:#b4231f
```

A regex filter on every log record redacts API-key and connection-string shapes,
and `sanitize_provider_error()` replaces raw SDK exceptions — which routinely
echo the `Authorization` header — with actionable text.

---

## 7. AI architecture

```mermaid
graph TD
    MSG["Teacher's question"]
    CFG["Resolve provider<br/>teacher's key ▸ server default ▸ error"]
    CAP{"Model supports<br/>tool calling?"}

    TOOLS["bind 13 scoped tools"]
    LOOP["Tool loop<br/>max 4 rounds"]
    AUTH{"Tool checks<br/>teacher scope"}
    RUN["Run parameterized query"]
    DENY["Return refusal<br/>as a tool result"]

    CTX["Aggregate-only snapshot<br/>in the prompt"]
    STREAM["model.astream()"]
    SSE["SSE frames → browser"]

    MSG --> CFG --> CAP
    CAP -->|yes| TOOLS --> LOOP --> AUTH
    AUTH -->|in scope| RUN --> LOOP
    AUTH -->|out of scope| DENY --> LOOP
    LOOP --> STREAM
    CAP -->|no| CTX --> STREAM
    STREAM --> SSE

    style AUTH fill:#e6f2f1,stroke:#0f766e,stroke-width:2px
    style DENY fill:#fdeceb,stroke:#b4231f
```

### The thirteen tools

There is **no SQL tool and no write tool**. Each is a fixed operation bound to one
`TeacherPrincipal` and one database session.

| Area | Tools |
|---|---|
| Scope | `get_teacher_subjects` · `find_students` |
| Attendance | `get_subject_attendance_summary` · `get_low_attendance_students` · `get_student_attendance` · `get_classes_needed_for_target` |
| Academic | `get_subject_performance_summary` · `get_students_below_marks_threshold` · `get_student_academic_summary` |
| Assignments | `get_assignment_submission_summary` · `get_student_assignment_status` |
| Extracurricular | `get_extracurricular_summary` · `get_student_extracurricular` |

Results are capped at 40 rows and **disclose truncation**, so the assistant cannot
claim to have analyzed everyone when it saw a subset. Tool results also carry the
relevant definitions — the threshold used, what "overdue" means, how missing marks
were handled — so the model restates them accurately instead of guessing.

### Provider abstraction

```mermaid
graph LR
    CFG["ProviderConfig<br/>provider · model · key · base_url"]
    REG["model_registry<br/>capabilities per provider"]
    FACT["provider_factory"]
    VAL["URL validation<br/>DNS resolve → reject<br/>private / loopback / metadata"]

    A["langchain-anthropic"]
    G["langchain-google-genai"]
    Q["langchain-groq"]
    O["langchain-ollama"]
    X["langchain-openai<br/>+ base_url →<br/>OpenAI · OpenRouter<br/>DeepSeek · Together · custom"]

    CFG --> REG --> FACT
    FACT --> VAL
    VAL --> A & G & Q & O & X

    style VAL fill:#e6f2f1,stroke:#0f766e
```

Five OpenAI-wire-compatible services share one client with a different `base_url`,
so adding another is a registry entry, not new code.

---

## 8. Streaming protocol

Tokens are forwarded as the provider emits them. Nothing is buffered to
completion; there is no simulated typing.

```mermaid
sequenceDiagram
    participant UI as use-chat.ts
    participant API as POST /api/chat
    participant ORC as orchestration
    participant M as Model

    UI->>API: {messages, provider?}
    API->>ORC: stream_chat(...)
    ORC-->>UI: event: status {"thinking"}
    ORC->>M: ainvoke(messages + tools)
    M-->>ORC: tool_calls
    ORC-->>UI: event: tool {running}
    ORC->>ORC: authorize + query DB
    ORC-->>UI: event: tool {complete | denied}
    ORC->>M: astream(messages + results)
    loop each chunk
        M-->>ORC: chunk
        ORC-->>UI: event: token {"text"}
        Note over UI: appended immediately
    end
    ORC-->>UI: event: done {"ok": true}

    Note over UI,API: Stop uses AbortController<br/>the read is raced against the abort signal<br/>so partial text is kept
```

| Event | Payload | Client behaviour |
|---|---|---|
| `status` | `{state}` | Show "thinking" / "generating" |
| `tool` | `{name, state}` | Badge; `denied` renders in red |
| `token` | `{text}` | Append to the message |
| `error` | `{message, kind}` | Show error + Retry. **Never fabricate.** |
| `done` | `{ok}` | Finish and clean up |

A failed provider call surfaces the failure. It is never replaced with invented
text — a property covered by tests.

---

## 9. Calculation semantics

### Attendance — exact arithmetic

All attendance maths lives in `services/attendance_math.py` and uses `Fraction`,
not floats, so `30/40` is *exactly* 75% and is **not** flagged as below a 75%
threshold.

```
percentage = classes_attended / classes_conducted × 100

classes needed to reach target T:
    n = max(0, ⌈(T·C − A·100) / (100 − T)⌉)
```

A target of 100% after any absence raises an error rather than returning a
misleading number.

### Two averages, both labelled

```mermaid
graph TD
    SRC["Attendance rows"]
    P["Pooled<br/>Σattended / Σconducted<br/><i>every class counts equally</i>"]
    M["Mean per student<br/>avg of each student's %<br/><i>every student counts equally</i>"]
    SRC --> P
    SRC --> M
    style P fill:#e6f2f1,stroke:#0f766e
    style M fill:#e8eefc,stroke:#1d4ed8
```

These differ whenever subjects have different class counts, so the UI shows both
with their definitions rather than one unlabelled "average".

### Three distinctions the system refuses to blur

```mermaid
graph LR
    subgraph G["Grades"]
        G1["marks = NULL<br/>is_absent = false<br/><b>not evaluated</b>"]
        G2["marks = NULL<br/>is_absent = true<br/><b>absent</b>"]
        G3["marks = 0.0<br/><b>scored zero</b>"]
    end
    subgraph A["Assignments"]
        A1["pending + due passed<br/><b>overdue</b>"]
        A2["submitted, no marks<br/><b>awaiting evaluation</b>"]
        A3["pending, not yet due<br/><b>still open</b>"]
    end
    style G3 fill:#fdeceb,stroke:#b4231f
    style A1 fill:#fdeceb,stroke:#b4231f
```

Unevaluated work is **excluded from the denominator**, never counted as zero.
Work submitted but not yet marked is **never** reported as overdue. The dataset
deliberately contains all three grade states so the distinction is exercised
against real data, not only in fixtures.

---

## 10. Deployment topology

```mermaid
graph TD
    U["👤 Browser"]
    FE["Vercel — Next.js<br/>frontend-kappa-puce-90.vercel.app<br/>static + client components"]
    BE["Vercel — FastAPI<br/>csbs-faculty-api.vercel.app<br/>api/index.py · 60s · 1024MB"]
    DB[("Neon PostgreSQL<br/>pooled connection")]
    AI["Gemini / BYOK provider"]

    U --> FE
    FE -->|"cookie: SameSite=None; Secure"| BE
    BE --> DB
    BE --> AI

    style FE fill:#e8f5ec,stroke:#15803d
    style BE fill:#fdf2e2,stroke:#a65c00
```

**The backend runs on serverless with real constraints**, measured rather than
assumed:

| Works | Constrained |
|---|---|
| Health, sessions, cookies | SSE capped at 60 s — a long turn can truncate |
| All data endpoints | Pool cannot persist; a **pooled** Neon string is required |
| Authorization (401/403) | Rate limiter is per-instance, so limits are weaker |
| Tool calling and streaming | Cold starts add latency |

`backend/render.yaml` and `backend/Dockerfile` run the same code on a container
host, where streaming and pooling behave as designed. No code changes needed.

---

## 11. Design decisions

### Why no vector database, RAG or agent graph

This data is relational. "Which students are below 75% in CB3202T?" is an indexed
`WHERE` clause with exact arithmetic — a vector store would make it slower, less
accurate and harder to authorize. Embeddings also break the scope model: you
cannot easily express "only this teacher's subjects" over a similarity search.
Database-backed tools are the correct design here, and adding retrieval
infrastructure would have been decoration.

### Why tools instead of generated SQL

A text-to-SQL tool would mean the model composing queries against a schema it
could be talked into misreading, with authorization enforced by prompt text. The
fixed tool set means the set of possible queries is finite, reviewable, and each
one re-checks scope in code.

### Why the scope is re-read per request

Cost: one indexed query. Benefit: permission changes take effect immediately
rather than when a cookie expires.

### Why `Fraction` instead of float

`30/40` must be exactly 75%. With floats, a student sitting exactly on the
threshold can be flagged as below it depending on rounding — a visible, unfair
error in a report a teacher might act on.

### Why both averages are shown

Picking one silently would misrepresent a cohort whenever subjects have different
class counts. Showing both with their definitions is the honest option.

### Why the API key never touches storage

A key in `localStorage` survives in a shared browser; in the database it becomes
a breach liability. Memory-only means reloading the page clears it — a deliberate
trade of convenience for a credential that cannot outlive the session.

---

## Related documents

- [README](../README.md) — setup, API reference, troubleshooting
- [Before using real college records](../README.md#before-using-real-college-records)
  — what this system would need first
