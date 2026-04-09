from typing import Any, Dict, List


def chunk_document(
    doc: Dict[str, Any],
    chunk_size: int = 200,
    overlap: int = 20,
) -> List[Dict[str, Any]]:
    """
    1文書をChunk化して返す。
    - chunk_size: 1チャンクあたりの最大文字数（日本語は1文字≒1トークンで近似）
    - overlap: 前後チャンクと重複させる文字数（文脈の連続性を保つため）
    """
    text = doc["text"]
    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]

        chunks.append(
            {
                # chunk_idはdoc_idにインデックスを付与して一意にする
                "id": f"{doc['id']}_chunk{chunk_index}",
                "text": chunk_text,
                "metadata": {
                    **doc["metadata"],
                    "source_doc_id": doc["id"],  # 元の文書IDを保持
                    "chunk_index": chunk_index,
                },
            }
        )

        # 次のchunkの開始位置：chunk_size分進めてoverlap分戻る
        start += chunk_size - overlap
        chunk_index += 1

    return chunks


def chunk_documents(
    docs: List[Dict[str, Any]],
    chunk_size: int = 200,
    overlap: int = 20,
) -> List[Dict[str, Any]]:
    """SAMPLE_DOCS全体をChunk化して1つのリストで返す"""
    all_chunks = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc, chunk_size, overlap))
    return all_chunks


if __name__ == "__main__":
    from documents import SAMPLE_DOCS

    # chunk_sizeを小さくしてChunking動作を確認
    chunks = chunk_documents(SAMPLE_DOCS, chunk_size=40, overlap=10)
    print(f"元文書数: {len(SAMPLE_DOCS)}件")
    print(f"Chunk後: {len(chunks)}件")
    for c in chunks:
        print(f"  [{c['id']}] {len(c['text'])}文字 | {c['text'][:30]}...")
