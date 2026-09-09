# Schema DB — Deutsch-Tutor

Migrazione Alembic `0001_initial` (task 1.2). Tutte le enum sono tipi nativi Postgres.

## ERD

```mermaid
erDiagram
    scenarios ||--o{ vocab_items : "ha"
    scenarios ||--o{ lessons : "ha"
    vocab_items ||--|| vocab_progress : "progresso"
    vocab_items ||--o{ review_events : "eventi"
    vocab_items ||--o{ user_sentences : "frasi"
    lessons ||--o{ review_events : "eventi"
    lessons ||--o{ messages : "messaggi"
    lessons ||--o{ user_sentences : "frasi"

    scenarios {
        int id PK
        string slug UK
        string title_de
        string title_it
        int week_number UK
        text description
        string role_label "nullable"
        jsonb key_phrases "lista {de, it, example}"
        jsonb swiss_variants "lista {standard, swiss, it}"
        jsonb imprevisti "lista stringhe"
        jsonb goals "lista stringhe"
    }

    vocab_items {
        int id PK
        string de
        string it
        string gender "der/die/das, nullable"
        string plural "nullable"
        bool separable
        text example_de
        int scenario_id FK "nullable"
        source_enum source "curated|requested|error|agent_used"
        timestamptz created_at
    }

    vocab_progress {
        int vocab_item_id PK,FK
        vocab_state_enum state "new|seen|used|consolidated"
        int correct_uses
        timestamptz last_reviewed_at "nullable"
        timestamptz next_review_at "nullable"
        int interval_days
        int lapses
    }

    review_events {
        int id PK
        int vocab_item_id FK
        review_source_enum source "warmup|flashcard|roleplay|test"
        review_result_enum result "correct|wrong"
        int lesson_id FK "nullable"
        timestamptz created_at
    }

    lessons {
        int id PK
        int scenario_id FK
        lesson_type_enum lesson_type "base|variant|incident|review"
        timestamptz started_at
        timestamptz ended_at "nullable"
        lesson_status_enum status "in_progress|completed|abandoned"
        jsonb summary "nullable"
    }

    messages {
        int id PK
        int lesson_id FK
        lesson_phase_enum phase "warmup|prep|roleplay|harvest|swiss"
        message_role_enum role "user|agent|system"
        text content
        jsonb corrections "nullable"
        jsonb requested_words "nullable"
        timestamptz created_at
    }

    user_sentences {
        int id PK
        int vocab_item_id FK
        int lesson_id FK
        text sentence
        bool is_correct
        text feedback
        timestamptz created_at
    }
```

## Tabelle

| Tabella | Scopo |
|---|---|
| `scenarios` | I 12 scenari del piano di studi; contenuti completi (key_phrases, varianti svizzere, imprevisti, goals) via JSONB. |
| `vocab_items` | Parole/frasi target, con genere, plurale, separabile, esempio e origine (`source`). |
| `vocab_progress` | Stato SRS per vocabolo (1:1 con `vocab_items`): stato, usi corretti, intervallo, lapses. |
| `review_events` | Storico degli eventi di ripasso (warmup, flashcard, roleplay, test) per le statistiche e la consolidazione. |
| `lessons` | Lezioni del piano (base, variant, incident, review) con stato e summary. |
| `messages` | Messaggi della lezione per fase, con correzioni e parole richieste (JSONB). |
| `user_sentences` | Frasi dell'utente per vocabolo, con esito e feedback. |

## Enum native

| Nome tipo | Valori |
|---|---|
| `source_enum` | curated, requested, error, agent_used |
| `vocab_state_enum` | new, seen, used, consolidated |
| `review_source_enum` | warmup, flashcard, roleplay, test |
| `review_result_enum` | correct, wrong |
| `lesson_type_enum` | base, variant, incident, review |
| `lesson_status_enum` | in_progress, completed, abandoned |
| `lesson_phase_enum` | warmup, prep, roleplay, harvest, swiss |
| `message_role_enum` | user, agent, system |

## Note

- `llm_calls` (log chiamate LLM) arriva in Fase 3, non fa parte dello schema minimo del task 1.2.
- `swiss_variants` è una lista di `{standard, swiss, it}` (v1.1); la bozza v1 la lasciava non tipizzata.
