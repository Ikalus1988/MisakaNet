# MisakaNet Architecture

## Core Flywheel

```mermaid
graph LR
    A[Lessons] --> B[Search]
    B --> C[Agent]
    C --> D[Feedback]
    D --> A
```

## Draft Pipeline

```mermaid
graph TD
    G[Guard] --> T[Tombstone]
    T --> D[Draft]
    D --> V[Validate]
    V --> P[Published]
    P --> A[Lessons]
```

## Key Flow

1. **Agent** encounters error → **Search** for lessons
2. **Apply** lesson → report outcome
3. If failure → create **Draft** lesson
4. **Guard** validates → **Publish** to lessons
5. Loop continues
