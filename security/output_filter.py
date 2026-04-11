# security/output_filter.py
# LLM05: Improper Output Handling対策

import re

# PII検出パターン（日本の書式に対応）
PII_PATTERNS = [
    (r"[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4}", "クレジットカード番号"),
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "メールアドレス"),
    (r"0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{4}", "電話番号"),
]

# コードインジェクション検出パターン
CODE_INJECTION_PATTERNS = [
    (r"<script[\s\S]*?>[\s\S]*?</script>", "scriptタグ"),
    (r"javascript:", "javascriptスキーム"),
]

# 機密情報検出パターン
SECRET_PATTERNS = [
    (r"\b[A-Za-z0-9]{32,45}\b", "APIキー候補"),
]


def filter_output(text: str) -> tuple[str, list[str]]:
    """
    LLMの出力からPII・コードインジェクション・機密情報を除去する。
    Returns:
        (filtered_text, warnings): フィルタリング済みテキストと検出した警告リスト
    """
    warnings = []

    # PIIフィルタリング
    for pattern, label in PII_PATTERNS:
        if re.search(pattern, text):
            warnings.append(f"{label}を検出・マスクしました")
            text = re.sub(pattern, "[REDACTED]", text)

    # コードインジェクションフィルタリング

    for pattern, label in CODE_INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            warnings.append(f"{label}を検出・除去しました")
            text = re.sub(pattern, "[REMOVED]", text, flags=re.IGNORECASE)

    # 機密情報フィルタリング
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text):
            warnings.append(f"{label}を検出・マスクしました")
            text = re.sub(pattern, "[REDACTED]", text)

    return text, warnings


if __name__ == "__main__":
    test_cases = [
        # 正常な回答
        "冷却システムの点検頻度は週1回です。",
        # メールアドレス含む
        "担当者はtanaka@factory.co.jpまでご連絡ください。",
        # 電話番号含む
        "緊急連絡先は06-1234-5678です。",
        # クレジットカード番号含む
        "カード番号4111-1111-1111-1111は使用できません。",
        # scriptタグ含む
        "手順書の内容: <script>alert('xss')</script> 点検後に記録すること。",
    ]

    for text in test_cases:
        filtered, warnings = filter_output(text)
        print(f"入力: {text}")
        print(f"出力: {filtered}")
        if warnings:
            print(f"警告: {warnings}")
        print()
