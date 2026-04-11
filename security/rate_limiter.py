# security/rate_limiter.py
# LLM10: Unbounded Consumption対策

import time
from collections import defaultdict

# レート制限の設定
MAX_REQUESTS_PER_MINUTE = 5  # 1分間あたりの最大リクエスト数
MAX_TOKENS_PER_DAY = 10000  # 1日あたりの最大トークン消費量（概算）
WINDOW_SECONDS = 60  # レート制限のウィンドウ幅（秒）


class RateLimiter:
    def __init__(self):
        # ユーザーごとのリクエスト履歴 {user_id: [timestamp, ...]}
        self.request_history: dict[str, list[float]] = defaultdict(list)
        # ユーザーごとの日次トークン消費量 {user_id: {"date": str, "tokens": int}}
        self.token_usage: dict[str, dict] = defaultdict(
            lambda: {"date": "", "tokens": 0}
        )

    def check_rate_limit(self, user_id: str) -> tuple[bool, str]:
        """
        リクエストレート制限をチェックする。
        Returns:
            (is_allowed, reason): 許可ならTrue・空文字、拒否ならFalse・理由
        """
        now = time.time()
        window_start = now - WINDOW_SECONDS

        # ウィンドウ外の古い履歴を削除
        self.request_history[user_id] = [
            t for t in self.request_history[user_id] if t > window_start
        ]

        # リクエスト数チェック
        request_count = len(self.request_history[user_id])
        if request_count >= MAX_REQUESTS_PER_MINUTE:
            return False, (
                f"レート制限超過: {WINDOW_SECONDS}秒間に"
                f"{MAX_REQUESTS_PER_MINUTE}回以上のリクエストがありました"
            )

        # リクエストを記録
        self.request_history[user_id].append(now)
        return True, ""

    def check_token_limit(
        self, user_id: str, estimated_tokens: int
    ) -> tuple[bool, str]:
        """
        日次トークン消費量制限をチェックする。
        Returns:
            (is_allowed, reason): 許可ならTrue・空文字、拒否ならFalse・理由
        """
        today = time.strftime("%Y-%m-%d")
        usage = self.token_usage[user_id]

        # 日付が変わったらリセット
        if usage["date"] != today:
            usage["date"] = today
            usage["tokens"] = 0

        # トークン数チェック
        if usage["tokens"] + estimated_tokens > MAX_TOKENS_PER_DAY:
            return False, (
                f"日次トークン制限超過: 本日の消費量"
                f"{usage['tokens']}トークン / 上限{MAX_TOKENS_PER_DAY}トークン"
            )

        # トークン消費を記録
        usage["tokens"] += estimated_tokens
        return True, ""

    def get_usage_stats(self, user_id: str) -> dict:
        """ユーザーの現在の使用状況を返す"""
        now = time.time()
        window_start = now - WINDOW_SECONDS
        recent_requests = [t for t in self.request_history[user_id] if t > window_start]
        today = time.strftime("%Y-%m-%d")
        usage = self.token_usage[user_id]
        tokens_today = usage["tokens"] if usage["date"] == today else 0

        return {
            "user_id": user_id,
            "requests_in_window": len(recent_requests),
            "tokens_today": tokens_today,
        }


if __name__ == "__main__":
    limiter = RateLimiter()
    user_id = "tanaka"

    print("=== レート制限テスト ===")
    for i in range(7):
        is_allowed, reason = limiter.check_rate_limit(user_id)
        status = "✅ 許可" if is_allowed else f"🚫 拒否: {reason}"
        print(f"リクエスト {i + 1}: {status}")

    print("\n=== トークン制限テスト ===")
    test_tokens = [3000, 3000, 3000, 2000]
    for i, tokens in enumerate(test_tokens):
        is_allowed, reason = limiter.check_token_limit(user_id, tokens)
        status = "✅ 許可" if is_allowed else f"🚫 拒否: {reason}"
        stats = limiter.get_usage_stats(user_id)
        print(f"リクエスト {i + 1} ({tokens}トークン): {status}")
        print(f"  → 本日の消費量: {stats['tokens_today']}トークン")
