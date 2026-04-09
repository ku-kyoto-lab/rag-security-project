# indexing.py
import os
import cohere
import chromadb
from dotenv import load_dotenv
from documents import SAMPLE_DOCS
from chunking import chunk_documents

load_dotenv()

# クライアント初期化
co = cohere.Client(os.getenv("COHERE_API_KEY"))
chroma_client = chromadb.PersistentClient(path="./chroma_db")  # ローカルに永続化


def build_index():
    # コレクション作成（すでにある場合は削除して再作成）
    chroma_client.delete_collection("rag_docs") if "rag_docs" in [
        c.name for c in chroma_client.list_collections()
    ] else None
    collection = chroma_client.create_collection(
        name="rag_docs", metadata={"hnsw:space": "cosine"}
    )

    # 全文書をEmbedding
    chunks = chunk_documents(SAMPLE_DOCS, chunk_size=200, overlap=20)
    texts = [chunk["text"] for chunk in chunks]  # ← docsからchunksに変更
    response = co.embed(
        texts=texts,
        model="embed-multilingual-v3.0",
        input_type="search_document",
    )
    embeddings = response.embeddings

    collection.add(
        ids=[chunk["id"] for chunk in chunks],  # ← chunk_idを使用
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
    print(
        f"インデックス構築完了: {len(chunks)}チャンクを登録（元文書{len(SAMPLE_DOCS)}件）"
    )


if __name__ == "__main__":
    build_index()
