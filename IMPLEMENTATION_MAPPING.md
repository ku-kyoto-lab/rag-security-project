# Implementation Mapping — Secure Manufacturing RAG Adoption Pack

This document maps each security and business claim in the
Secure Manufacturing RAG Adoption Pack to its corresponding
implementation in this repository and related projects.

Intended readers: IT / Security teams evaluating technical credibility.

---

## 1. Access Control (Fail Closed)

**Claim**: General employees cannot access confidential SOPs or design
documents. If identity provider (IdP) is unavailable, access is denied
— never silently permitted.

| File | Key Logic |
|------|-----------|
| `query.py` | `get_user_groups()` — raises `PermissionError` if IdP unavailable (Fail Closed) |
| `query.py` | ACL filtering: `any(g in allowed_groups for g in user_groups)` after vector search |
| `indexing.py` | `allowed_groups` embedded as metadata at indexing time (Access Label Mapping) |

Related projects:
- [rag-security-openai](https://github.com/ku-kyoto-lab/rag-security-openai) — same Fail Closed design with boolean flag attributes (OpenAI File Search constraint)
- [rag-security-cohere](https://github.com/ku-kyoto-lab/rag-security-cohere) — same design with Cohere Embed v3 + Rerank v3

---

## 2. Audit Logging (ISO 27001 Annex A 8.15)

**Claim**: Every query is recorded — who searched, when, what was
retrieved, whether PII was detected. Access denials are logged
separately for SIEM alerting.

| File | Key Logic |
|------|-----------|
| `audit_logger.py` | `log_query()` — records user_id, groups, query, docs_retrieved, rerank_scores, pii_detected |
| `audit_logger.py` | `log_access_denied()` — records ACCESS_DENIED events with reason; query truncated to 100 chars to prevent Log Injection |
| `query.py` | Audit log called at Step 7 (after output filtering, before response return) |

Output format: JSONL (1 record per line) — compatible with Splunk, Microsoft Sentinel, CloudWatch Logs.

---

## 3. Prompt Injection Defense (3-Layer)

**Claim**: Malicious inputs cannot manipulate the system.
Attacks embedded in retrieved documents are also detected
before entering the Vector Store.

| Layer | File | Key Logic |
|-------|------|-----------|
| Layer 1: Blocklist | `security/input_validation.py` | Pattern-based detection of direct injection attempts |
| Layer 2: LLM Intent Classifier | [rag-prompt-injection-lab](https://github.com/ku-kyoto-lab/rag-prompt-injection-lab) `defense/intent_classifier.py` | Claude Haiku-based intent judgment — paraphrase-resistant |
| Layer 3: Document Validator | [rag-prompt-injection-lab](https://github.com/ku-kyoto-lab/rag-prompt-injection-lab) `defense/document_validator.py` | Validates documents at indexing time; blocks embedded commands before Vector Store entry |

Detection benchmark: see [rag-prompt-injection-lab README](https://github.com/ku-kyoto-lab/rag-prompt-injection-lab) for detection rate / false positive rate measurements.

---

## 4. Output Safety (PII Filtering)

**Claim**: Personal information (email addresses, phone numbers,
credit card numbers) in retrieved documents is masked before
being returned to the user.

| File | Key Logic |
|------|-----------|
| `security/output_filter.py` | Regex-based PII detection — email, phone, credit card, API key candidates |
| `security/output_filter.py` | Script injection pattern removal |
| `query.py` | Output filter applied at Step 6 (before audit log, before response return) |

---

## 5. Event-Driven Reindexing

**Claim**: When a SOP is revised, the Vector Store is updated
immediately — not overnight. Stale and current versions never
coexist in the index.

| File | Key Logic |
|------|-----------|
| `reindex_trigger.py` | `delete_document()` → `reindex_document()` — delete-before-insert order enforced |
| `reindex_trigger.py` | `simulate_webhook()` — simulates document update Webhook (SharePoint / Confluence in production) |

Design rationale: insert-before-delete would allow a window where old
and new SOP chunks coexist, risking mixed responses. Delete-first
eliminates this window.

---

## 6. Production Readiness (Evals / Observability / Fallback / SLA/SLO)

**Claim**: Answer quality is continuously measured. The system
automatically switches to a fallback model on failure and
monitors SLO compliance in real time.

| Component | Project | Key Logic |
|-----------|---------|-----------|
| Evals (Model Grader + Code Grader) | [llm-production-ops](https://github.com/ku-kyoto-lab/llm-production-ops) `evals/` | LLM-as-a-Judge + rule-based dual evaluation for manufacturing QA tasks |
| Observability | [llm-production-ops](https://github.com/ku-kyoto-lab/llm-production-ops) `observability/` | Latency, token usage, error rate tracking |
| Prompt Versioning | [llm-production-ops](https://github.com/ku-kyoto-lab/llm-production-ops) `prompt_versioning/` | Version control and rollback for system prompts |
| Fallback Handler | [llm-production-ops](https://github.com/ku-kyoto-lab/llm-production-ops) `fallback/fallback_handler.py` | Auto-switch: claude-sonnet-4-6 → claude-haiku-4-5 on APIStatusError / RateLimitError / Timeout |
| SLA/SLO Monitor | [llm-production-ops](https://github.com/ku-kyoto-lab/llm-production-ops) `fallback/sla_monitor.py` | P95 latency ≤ 5s / error rate ≤ 5% / availability ≥ 95% |
| Alert Manager | [llm-production-ops](https://github.com/ku-kyoto-lab/llm-production-ops) `fallback/alert_manager.py` | Threshold breach alerts — pluggable (File → Slack → PagerDuty) |

---

## Summary

| Claim | Implementation | Status |
|-------|---------------|--------|
| Fail Closed access control | `query.py` + `indexing.py` | ✅ Implemented |
| Audit logging (ISO 27001) | `audit_logger.py` | ✅ Implemented |
| Prompt Injection defense (3-layer) | `security/` + rag-prompt-injection-lab | ✅ Implemented |
| PII output filtering | `security/output_filter.py` | ✅ Implemented |
| Event-driven reindexing | `reindex_trigger.py` | ✅ Implemented |
| Evals / Observability / Fallback / SLA/SLO | llm-production-ops | ✅ Implemented |