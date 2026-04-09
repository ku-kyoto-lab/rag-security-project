# query.py
import os
import cohere
import chromadb
import anthropic
from dotenv import load_dotenv
from documents import USER_GROUPS

load_dotenv()

# クライアント初期化
co = cohere.Client(os.getenv("COHERE_API_KEY"))
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_collection("rag_docs")
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def get_user_groups(user_id: str) -> list[str]:
    """IdP問い合わせのモック（実環境ではGraph API / LDAP等に置き換え）"""
    groups = USER_GROUPS.get(user_id)
    if not groups:
        # Fail Closed: グループ情報が取得できない場合はアクセスを拒否
        raise PermissionError(
            f"ユーザー '{user_id}' のグループ情報が取得できません。アクセスを拒否します。"
        )
    return groups


def rag_query(user_id: str, question: str, top_k: int = 5) -> str:
    # Step1: ユーザーグループ取得（Fail Closed）
    groups = get_user_groups(user_id)
    print(f"\n[{user_id}] グループ: {groups}")

    # Step2: 質問をEmbedding（クエリ時はsearch_queryを指定）
    query_embed = co.embed(
        texts=[question],
        model="embed-multilingual-v3.0",
        input_type="search_query",
    ).embeddings[0]

    # Step3: ChromaDBからACL-aware検索
    # ChromaDBのwhere句: allowed_groupsがユーザーグループのいずれかを含む文書のみ返す
    # ※ChromaDBはlist型のOR検索のため、グループごとにcontainsで検索してマージ
    results = collection.query(
        query_embeddings=[query_embed],
        n_results=min(top_k, 4),  # サンプルは4件のみ
        include=["documents", "metadatas", "distances"],
    )

    # Python側でACLフィルタリング
    docs = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        doc_groups = meta["allowed_groups"].split(",")
        if any(g in doc_groups for g in groups):
            docs.append(doc)

    if not docs:
        return "アクセス可能な文書が見つかりませんでした。"

    print(f"取得文書数（フィルタリング後）: {len(docs)}件")

    # Step4: Cohere Rerankで関連度順に並び替え
    rerank_response = co.rerank(
        query=question,
        documents=docs,
        model="rerank-multilingual-v3.0",
        top_n=3,
    )
    reranked_docs = [docs[r.index] for r in rerank_response.results]
    print(f"Rerank後: {[r.relevance_score for r in rerank_response.results]}")

    # Step5: Claudeで回答生成
    context = "\n---\n".join(reranked_docs)
    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": f"以下の文書のみを根拠として質問に回答してください。\n\n文書:\n{context}\n\n質問: {question}",
            }
        ],
    )
    return response.content[0].text


if __name__ == "__main__":
    question = "冷却システムの点検手順を教えてください"
    for user_id in ["tanaka", "suzuki", "yamada"]:
        print(f"\n{'=' * 50}")
        print(f"ユーザー: {user_id}")
        print(f"質問: {question}")
        answer = rag_query(user_id, question)
        print(f"回答: {answer}")
