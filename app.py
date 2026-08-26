# app.py
# FastAPIラッパー。既存の rag_query() は変更せず、HTTP層だけをかぶせる。

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from query import rag_query

# Fail Closed: 必須の環境変数がなければ起動時に落とす
# （黙って起動してリクエスト時に初めて倒れるより安全側に倒す）
REQUIRED_ENV = (
    "ANTHROPIC_API_KEY",
    "COHERE_API_KEY",
    "BEDROCK_GUARDRAIL_ID",
)

_missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
if _missing:
    raise RuntimeError(f"必須環境変数が未設定です（Fail Closed）: {', '.join(_missing)}")

app = FastAPI(title="Secure Manufacturing RAG API", version="0.1.0")


class QueryRequest(BaseModel):
    user_id: str
    question: str
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str


@app.get("/health")
def health() -> dict[str, str]:
    """liveness/readiness probe用。外部APIを叩かない軽いチェックにとどめる。"""
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    try:
        answer = rag_query(
            user_id=req.user_id,
            question=req.question,
            top_k=req.top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return QueryResponse(answer=answer)
