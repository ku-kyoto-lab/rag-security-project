# reindex_trigger.py
# イベント駆動再インデックス: 文書更新のWebhookシミュレーション

import os
import cohere
import chromadb
from dotenv import load_dotenv
from chunking import chunk_document
from audit_logger import log_query

load_dotenv()

co = cohere.Client(os.getenv("COHERE_API_KEY"))
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_collection("rag_docs")


def delete_document(doc_id: str) -> int:
    """
    ChromaDBから指定文書IDに関連する全チャンクを削除する。
    doc_001 → doc_001_chunk0, doc_001_chunk1 ... を全削除
    Returns: 削除したチャンク数
    """
    # 既存のチャンクIDを取得
    results = collection.get(where={"source_doc_id": doc_id})
    chunk_ids = results["ids"]

    if not chunk_ids:
        print(f"[REINDEX] 削除対象なし: {doc_id}")
        return 0

    collection.delete(ids=chunk_ids)
    print(f"[REINDEX] 削除完了: {doc_id} → {len(chunk_ids)}チャンク削除")
    return len(chunk_ids)


def reindex_document(doc: dict) -> int:
    """
    文書を再チャンク化してEmbeddingし、ChromaDBに登録する。
    Returns: 登録したチャンク数
    """
    # チャンク化
    chunks = chunk_document(doc, chunk_size=200, overlap=20)

    # Embedding
    texts = [chunk["text"] for chunk in chunks]
    response = co.embed(
        texts=texts,
        model="embed-multilingual-v3.0",
        input_type="search_document",
    )
    embeddings = response.embeddings

    # ChromaDBに登録
    collection.add(
        ids=[chunk["id"] for chunk in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {
                **chunk["metadata"],
                "allowed_groups": ",".join(chunk["metadata"]["allowed_groups"]),
            }
            for chunk in chunks
        ],
    )
    print(f"[REINDEX] 再登録完了: {doc['id']} → {len(chunks)}チャンク登録")
    return len(chunks)


def simulate_webhook(doc_id: str, updated_doc: dict) -> None:
    """
    文書更新Webhookのシミュレーション。
    delete → insert の順序を厳守する。
    """
    print(f"\n{'=' * 50}")
    print(f"[WEBHOOK] 文書更新イベント受信: {doc_id}")
    print(f"{'=' * 50}")

    # Step1: 既存チャンクを削除
    deleted = delete_document(doc_id)

    # Step2: 新しい内容で再登録
    inserted = reindex_document(updated_doc)

    print(f"[WEBHOOK] 完了: {deleted}チャンク削除 → {inserted}チャンク登録")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    # doc_001（冷却システム手順書）の更新シミュレーション
    # 点検頻度を「週1回」→「週2回」に変更した想定
    updated_doc_001 = {
        "id": "doc_001",
        "text": "冷却システム点検手順書（ラインA）改訂版: 保護具（耐熱手袋・安全靴）を着用し、"
        "冷却弁を開放して温度計が規定値（60℃以下）であることを確認する。"
        "流量計が規定値（毎分50リットル）であることを確認する。"
        "異常音・異常振動がないことを目視および触診で確認する。"
        "異常時は緊急停止ボタンを押し、保守リーダーに連絡すること。"
        "【改訂】点検頻度を週2回（月曜・木曜の始業前）に変更。"
        "記録は点検台帳に記入し、3年間保管する。",
        "metadata": {
            "doc_type": "SOP",
            "department": "製造部",
            "equipment": "冷却システム",
            "line": "line_a",
            "allowed_groups": ["maintenance_line_a", "plant_manager"],
        },
    }

    # 更新前のチャンク数確認
    before = collection.get(where={"source_doc_id": "doc_001"})
    print(f"更新前のチャンク数: {len(before['ids'])}件")
    print(f"チャンクID: {before['ids']}")

    # Webhookシミュレーション実行
    simulate_webhook("doc_001", updated_doc_001)

    # 更新後のチャンク数確認
    after = collection.get(where={"source_doc_id": "doc_001"})
    print(f"更新後のチャンク数: {len(after['ids'])}件")
    print(f"チャンクID: {after['ids']}")
