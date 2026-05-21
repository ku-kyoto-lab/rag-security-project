# RAG Security Project — Secure RAG Pipeline for Manufacturing Environments

A security-first RAG (Retrieval-Augmented Generation) pipeline designed for manufacturing enterprise environments, where document-level access control, audit trails, and operational continuity are non-negotiable requirements.

Implements ACL-aware retrieval, audit logging, Prompt Injection defense, PII filtering, and event-driven reindexing — mapped to the OWASP LLM Top 10 (2025).

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Claude](https://img.shields.io/badge/Claude-claude--sonnet--4--6-blueviolet)
![Cohere](https://img.shields.io/badge/Cohere-Embed%20v3%20%2F%20Rerank%20v3.5-coral)
![OWASP](https://img.shields.io/badge/OWASP%20LLM-Top%2010%202025-red)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Overview

This project demonstrates how to build a **secure RAG system for manufacturing environments**, where a single misconfigured access control can expose confidential SOPs, design specifications, or financial reports to unauthorized users.

The core challenge: *a Vector Store has no concept of "who is allowed to see what."* In a manufacturing plant, a Line A maintenance worker should never retrieve Line B's restricted procedures — and an `all_staff` employee should never access executive-level reports, even if the question is semantically relevant.

This project solves that by implementing ACL-aware retrieval at the application layer, following a **Fail Closed** design principle: if user group information cannot be retrieved, access is denied — never silently permitted.

Built as a companion to a blog series on [Zenn](https://zenn.dev/kukyotolab).

---

## Why This Project

Standard RAG implementations retrieve documents based on semantic similarity alone — without regard to access permissions. In manufacturing enterprise environments, this creates risks that are difficult to accept:

- A general employee queries the RAG chatbot and retrieves confidential management reports
- A maintenance worker on Line A accesses Line B's restricted SOPs through a semantically similar query
- An outdated SOP (not yet reindexed after revision) is returned to a night-shift worker, leading to incorrect procedure execution
- A Prompt Injection attack in a production environment extracts sensitive documents via the LLM's response

This project addresses those risks with a layered security architecture:

**Input layer**
- Prompt Injection detection before the query reaches the LLM
- Per-user rate limiting to prevent unbounded token consumption

**Retrieval layer**
- `allowed_groups` embedded at indexing time via Access Label Mapping
- Fail Closed group resolution at query time (PermissionError if IdP unavailable)
- Python-side ACL filtering after vector search

**Output layer**
- PII detection and masking in LLM responses (email, phone, credit card numbers)
- Script injection pattern removal

**Operations layer**
- JSONL audit logging for post-incident investigation and compliance (ISO 27001 Annex A 8.15)
- Event-driven reindexing to ensure SOP revisions are reflected immediately — not overnight

---

## Architecture

### Indexing Pipeline

```
Source Documents (PDF / Word / Internal Wiki)
        |
        v
+-------------------------+
|   Document Processor    |
|  - Text extraction      |
|  - Chunking             |
|    (200 chars,          |
|     overlap=20)         |
+-------------------------+
        |
        v
+-------------------------+
|    Metadata Tagger      |
|  - allowed_groups       |  <-- fetched from IdP (AD / Entra ID)
|    (Access Label        |
|     Mapping)            |
|  - doc_type             |
|  - department           |
|  - effective_date       |
+-------------------------+
        |
        v
  Cohere Embed v3
  (embed-multilingual-v3.0)
        |
        v
  ChromaDB  <-- text + metadata stored together
```

### Query Pipeline

```
User Query
        |
        v
+-----------------------------+
| [Step 0] Input Validation   |  security/input_validation.py
|  - Prompt Injection         |  LLM01
|    pattern detection        |
|  - Max length enforcement   |
+-----------------------------+
        |
        v
+-----------------------------+
| [Step 0] Rate Limiter       |  security/rate_limiter.py
|  - 5 req / 60 sec           |  LLM10
|  - 10,000 tokens / day      |
|    (per user)               |
+-----------------------------+
        |
        v
+-----------------------------+
| [Step 1] Group Resolution   |  Fail Closed
|  - Fetch from IdP           |
|  - PermissionError if       |
|    unavailable              |
+-----------------------------+
        |
        v
+-----------------------------+
| [Step 2] Cohere Embed v3    |
|  input_type: search_query   |
+-----------------------------+
        |
        v
+-----------------------------+
| [Step 3] ChromaDB Search    |
|  + Python ACL Filtering     |  LLM08
|  any(g in allowed_groups    |
|      for g in user_groups)  |
+-----------------------------+
        |
        v
+-----------------------------+
| [Step 4] Cohere Rerank v3.5 |
|  rerank-multilingual-v3.0   |
+-----------------------------+
        |
        v
+-----------------------------+
| [Step 5] Claude             |
|  Response generation from   |
|  retrieved context only     |
+-----------------------------+
        |
        v
+-----------------------------+
| [Step 6] Output Filter      |  security/output_filter.py
|  - PII masking              |  LLM05
|    (email / phone /         |
|     credit card)            |
|  - Script injection removal |
+-----------------------------+
        |
        v
+-----------------------------+
| [Step 7] Audit Logger       |  audit_logger.py
|  - JSONL record:            |
|    user_id, groups, query,  |
|    docs_retrieved,          |
|    rerank_scores,           |
|    pii_detected             |
+-----------------------------+
        |
        v
  Response returned to user
```

### File Structure

```
rag-security-project/
├── documents.py          # Sample documents + USER_GROUPS mock
├── chunking.py           # Text chunking (200 chars, overlap=20)
├── indexing.py           # Embed → ChromaDB registration
├── query.py              # Full ACL-aware query pipeline
├── audit_logger.py       # JSONL audit log writer
├── reindex_trigger.py    # Event-driven reindex (Webhook simulation)
├── security/
│   ├── __init__.py
│   ├── input_validation.py   # Prompt Injection defense (LLM01)
│   ├── output_filter.py      # PII detection and masking (LLM05)
│   └── rate_limiter.py       # Request and token rate limiting (LLM10)
├── customer-value-pack/
│   ├── 01_executive_one_pager.pptx
│   ├── 02_rollout_plan.pptx
│   ├── dashboard/
│   │   ├── generate_dashboard.py
│   │   └── dashboard_output.html
│   └── IMPLEMENTATION_MAPPING.md
├── .env.example
└── chroma_db/            # Local vector store (gitignored)
```

---

## OWASP LLM Top 10 Mapping

The implementations here address the following OWASP LLM Top 10 (2025) risk categories. These are foundational controls — not exhaustive mitigations for each category.

| OWASP LLM Risk | Related Implementation | Scope in This Project |
|---|---|---|
| LLM01: Prompt Injection | `security/input_validation.py` | Blocklist-based detection for direct injection. Indirect Prompt Injection via retrieved chunks is discussed in Blog Series Part 4. |
| LLM02: Sensitive Information Disclosure | `query.py` error handling, `security/output_filter.py` | Error messages sanitized; PII masked in LLM responses. |
| LLM05: Improper Output Handling | `security/output_filter.py` | Regex-based PII detection (email, phone, credit card, API key candidates). Script injection removal. |
| LLM06: Excessive Agency | System prompt in `query.py` | LLM instructed to answer only from retrieved context ("以下の文書のみを根拠として回答してください"). |
| LLM08: Vector and Embedding Weaknesses | `indexing.py`, `query.py` | `allowed_groups` embedded at indexing time; enforced at query time via Fail Closed design. |
| LLM10: Unbounded Consumption | `security/rate_limiter.py` | Per-user request rate (5 req/60s) and daily token limits (10,000 tokens/day). |

---

## Key Design Decisions

**Why Python-side ACL filtering instead of ChromaDB metadata filtering?**
ChromaDB cannot filter on list-type metadata fields — `allowed_groups` is stored as a list, and ChromaDB's `where` clause does not support list membership checks. Filtering at the application layer after vector search is the only reliable approach without changing the data model.

**Why Fail Closed for group resolution?**
If the IdP (AD/Entra ID) is unavailable, silently granting access is a security failure. Denying access explicitly and logging the event is the safer default for manufacturing environments, where the cost of unauthorized document access exceeds the cost of a temporarily blocked query.

**Why Cohere Rerank after ChromaDB search?**
Vector search optimizes for recall — it returns the most semantically similar chunks regardless of precise relevance. Rerank re-scores the Top 5 candidates by relevance precision and returns the Top 3. In ACL-filtered results (often 1–3 documents), Rerank prevents a high-similarity but low-relevance chunk from being ranked first and misleading the LLM response.

**Why event-driven reindexing instead of scheduled batch?**
In manufacturing environments, an outdated SOP returned to a night-shift worker can lead to incorrect procedure execution. Scheduled batch reindexing introduces a window of inconsistency that is operationally unacceptable. Event-driven reindexing (Webhook simulation) ensures SOP revisions are reflected immediately.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Package Manager | uv |
| Vector Store | ChromaDB (local, persistent) |
| Embedding Model | Cohere Embed v3 (`embed-multilingual-v3.0`) |
| Reranking Model | Cohere Rerank v3.5 (`rerank-multilingual-v3.0`) |
| LLM | Anthropic Claude (`claude-sonnet-4-6`) |
| Code Quality | Ruff |
| Environment | python-dotenv |

---

## How to Run

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) installed
- Cohere API key ([dashboard.cohere.com](https://dashboard.cohere.com/))
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com/))

### Setup

```bash
git clone https://github.com/ku-kyoto-lab/rag-security-project.git
cd rag-security-project

uv sync

cp .env.example .env
# Add your API keys to .env:
#   COHERE_API_KEY=your_key_here
#   ANTHROPIC_API_KEY=your_key_here
```

### Build the Index

```bash
uv run python indexing.py
# → Indexed 5 chunks from 4 documents
```

### Run Queries

```bash
uv run python query.py
```

Access control in action — same question, three different users:

```
[tanaka]  groups: ['maintenance_line_a', 'all_staff']
          docs retrieved (after ACL filter): 3
          → Returns cooling system SOP correctly ✅

[yamada]  groups: ['all_staff']
          docs retrieved (after ACL filter): 1
          → "No relevant documents found for this query." ✅

[suzuki]  groups: ['executive', 'plant_manager', 'all_staff']
          docs retrieved (after ACL filter): 4
          → Returns cooling system SOP correctly ✅
```

### Test Event-Driven Reindex

```bash
uv run python reindex_trigger.py
# Simulates a document update Webhook:
# → Deletes stale chunks → reindexes updated document
```

---

## Known Limitations

- **Mock IdP**: `USER_GROUPS` is a hardcoded dict. Production use requires integration with AD/Entra ID or an LDAP provider.
- **Local vector store**: ChromaDB runs locally. For production, a managed vector store (e.g., Pinecone, Weaviate) with backup and HA is recommended.
- **Blocklist-based injection detection**: `input_validation.py` uses pattern matching. Adversarial prompts not in the blocklist will pass through. A classification-based approach (as implemented in `rag-prompt-injection-lab`) provides stronger coverage.
- **Single-language PII patterns**: `output_filter.py` targets Japanese and English patterns. Other locales require additional regex rules.

---

## Blog Series

This project is documented in a seven-part series (written in Japanese):

| # | Title | Link |
|---|---|---|
| Part 1 | Access Control Design for Manufacturing RAG Systems | [Zenn →](https://zenn.dev/kukyotolab/articles/ed209091142b2a) |
| Part 2 | Implementing ACL-Aware Retrieval with ChromaDB + Cohere | [Zenn →](https://zenn.dev/kukyotolab/articles/f52e4daf35fab2) |
| Part 3 | Audit Logging + Event-Driven Reindexing | [Zenn →](https://zenn.dev/kukyotolab/articles/46e651877241a4) |
| Part 4 | Prompt Injection Defense: Comparing Three Approaches | [Zenn →](https://zenn.dev/kukyotolab/articles/bdc38a5cfb27cb) |
| Part 5 | 3-Provider RAG Comparison: Claude / OpenAI / Cohere | [Zenn →](https://zenn.dev/kukyotolab/articles/three-provider-rag-comparison) |
| Part 6 | Production Operations: Evals / Observability / Prompt Versioning / Fallback | [Zenn →](https://zenn.dev/kukyotolab/articles/llm_production_ops) |
| Part 7 | From Architecture to Business Value | [Zenn →](https://zenn.dev/kukyotolab) |

> Part 6 and Part 7 links will be updated after publication.

---

## Related Projects

| Project | Description |
|---|---|
| [rag-security-openai](https://github.com/ku-kyoto-lab/rag-security-openai) | OpenAI edition — same architecture with GPT-4o-mini + OpenAI Vector Store |
| [rag-security-cohere](https://github.com/ku-kyoto-lab/rag-security-cohere) | Cohere edition — Cohere Embed v3 + Rerank v3 + Command R+ |
| [rag-prompt-injection-lab](https://github.com/ku-kyoto-lab/rag-prompt-injection-lab) | 3-layer Prompt Injection defense with detection eval (LLM01 / LLM08) |
| [llm-production-ops](https://github.com/ku-kyoto-lab/llm-production-ops) | Production operations: Evals / Observability / Prompt Versioning / Fallback |
| [claude-agent-lab](https://github.com/ku-kyoto-lab/claude-agent-lab) | Single Agent with Human-in-the-Loop approval-gated tool execution (LLM06) |

---

## Author

**ku-kyoto-lab**
Security Consultant | AI Security & Zero Trust Specialist

- GitHub: [ku-kyoto-lab](https://github.com/ku-kyoto-lab)
- Zenn: [kukyotolab](https://zenn.dev/kukyotolab)
- LinkedIn: [Profile](https://www.linkedin.com/in/ku-kyoto-lab/)

20+ years in enterprise IT across network engineering, virtualization, zero trust, and cyber consulting (NTT, VMware TAM, Zscaler CSM, Deloitte Tohmatsu Cyber). Currently building expertise in LLM application security and OWASP LLM Top 10 implementation.
