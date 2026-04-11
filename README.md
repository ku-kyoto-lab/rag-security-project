# RAG Security Project

A manufacturing-sector RAG (Retrieval-Augmented Generation) system with ACL-aware retrieval and security implementations, built with ChromaDB, Cohere, and Claude.

## Overview

This project implements a secure RAG pipeline for manufacturing environments, featuring:
- **ACL-aware retrieval**: Access control based on user group membership (Fail Closed design)
- **Prompt Injection defense**: Input validation against known attack patterns (OWASP LLM01)
- **Output filtering**: PII detection and masking (OWASP LLM05)
- **Rate limiting**: Request and token consumption controls (OWASP LLM10)

## Project Structure

    rag-security-project/
    ├── documents.py          # Sample documents and USER_GROUPS mock
    ├── chunking.py           # Text chunking with overlap
    ├── indexing.py           # Embedding and ChromaDB indexing
    ├── query.py              # ACL → Embed → Rerank → Claude pipeline
    ├── security/
    │   ├── __init__.py
    │   ├── input_validation.py   # LLM01: Prompt Injection defense
    │   ├── output_filter.py      # LLM05: PII detection and masking
    │   └── rate_limiter.py       # LLM10: Rate and token limiting
    ├── .env.example          # Environment variable template
    └── chroma_db/            # ChromaDB persistent storage (gitignored)

## Tech Stack

- **LLM**: Anthropic Claude (claude-sonnet-4-20250514)
- **Embedding**: Cohere embed-multilingual-v3.0
- **Reranking**: Cohere rerank-multilingual-v3.0
- **Vector Store**: ChromaDB (persistent)
- **Package Manager**: uv

## Setup

    git clone https://github.com/ku-kyoto-lab/rag-security-project.git
    cd rag-security-project
    uv add chromadb cohere anthropic python-dotenv
    cp .env.example .env
    # Edit .env and add your API keys
    uv run python indexing.py
    uv run python query.py

## OWASP LLM Top 10 Coverage

| Implementation | OWASP Category |
|---|---|
| security/input_validation.py | LLM01: Prompt Injection |
| security/output_filter.py | LLM05: Improper Output Handling |
| security/rate_limiter.py | LLM10: Unbounded Consumption |
| ACL-aware retrieval in query.py | LLM08: Vector and Embedding Weaknesses |

## Security Design

### ACL-aware Retrieval (Fail Closed)
User group membership is verified against a mock IdP on every query. Documents are filtered by allowed_groups metadata before reranking. If group information cannot be retrieved, access is denied.

### Prompt Injection Defense
Input is validated against known injection patterns before reaching the RAG pipeline, preventing unnecessary API costs and protecting downstream processing.

### Output Filtering
Claude's responses are scanned for PII (email addresses, phone numbers, credit card numbers) and code injection patterns before being returned to the user.

## Related Articles (Zenn)

- [製造業向けRAGシステムのアクセス制御設計](https://zenn.dev/kukyotolab/articles/ed209091142b2a) — Design
- [ChromaDB + CohereでACL-aware retrievalを実装する](https://zenn.dev/kukyotolab/articles/f52e4daf35fab2) — Implementation

## Author

[@kukyotolab](https://zenn.dev/kukyotolab)
