# Dockerfile
# マルチステージ：依存解決（builder）と実行（runtime）を分離しイメージを小さく保つ

# ---------- builder ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 依存定義だけを先にCOPYしてレイヤキャッシュを効かせる
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# ---------- runtime ----------
FROM python:3.12-slim AS runtime

# rootで動かさない
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# アプリコード（.dockerignoreで .env / chroma_db は除外済み）
COPY --chown=appuser:appuser . .

# appuserが/app直下に新規ファイル（audit_log.jsonl等）を書けるようにする
RUN chown appuser:appuser /app

# ChromaDBの永続化ディレクトリを事前作成し、appuser所有にする
# （ボリューム/PVC未マウント時でも起動でき、マウント時も所有権を引き継ぐ）
RUN mkdir -p /data/chroma && chown -R appuser:appuser /data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CHROMA_PERSIST_DIR=/data/chroma

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
