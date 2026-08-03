# guardrails/client.py

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Optional

import boto3
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Decision(str, Enum):
    ALLOW = "ALLOW"  # 介入なし
    MASK = "MASK"  # 匿名化のみ。filtered_textを流してよい
    BLOCK = "BLOCK"  # ハードブロック
    ERROR = "ERROR"  # 呼び出し失敗 → Fail Closedで BLOCK 相当


_BLOCK_PATHS: tuple[tuple[str, str], ...] = (
    ("topicPolicy", "topics"),
    ("contentPolicy", "filters"),
    ("wordPolicy", "customWords"),
    ("wordPolicy", "managedWordLists"),
    ("sensitiveInformationPolicy", "piiEntities"),
    ("sensitiveInformationPolicy", "regexes"),
)


class GuardrailResult(BaseModel):
    decision: Decision
    passed: bool
    action: str
    filtered_text: Optional[str] = None
    blocked_reason: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


def _has_hard_block(assessments: list[dict[str, Any]]) -> Optional[str]:
    for assessment in assessments:
        for policy_key, list_key in _BLOCK_PATHS:
            items = assessment.get(policy_key, {}).get(list_key, []) or []
            for item in items:
                if item.get("action") == "BLOCKED":
                    label = (
                        item.get("type")
                        or item.get("name")
                        or item.get("match")
                        or policy_key
                    )
                    return f"{policy_key}:{label} によりブロック"
    return None


class BedrockGuardrailClient:
    def __init__(self):
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        self.guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID")
        self.guardrail_version = os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")

    def check(self, text: str, source: str = "INPUT") -> GuardrailResult:
        """
        source: "INPUT"（ユーザー入力チェック）または "OUTPUT"（Claude出力チェック）
        Fail Closed: guardrail_id未設定・呼び出し失敗はBLOCK相当（ERROR）にする
        """
        if not self.guardrail_id:
            return GuardrailResult(
                decision=Decision.ERROR,
                passed=False,
                action="GUARDRAIL_INTERVENED",
                blocked_reason="BEDROCK_GUARDRAIL_ID 未設定（Fail Closed）",
            )

        try:
            response = self.client.apply_guardrail(
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion=self.guardrail_version,
                source=source,
                content=[{"text": {"text": text}}],
            )
        except Exception as e:
            return GuardrailResult(
                decision=Decision.ERROR,
                passed=False,
                action="GUARDRAIL_INTERVENED",
                blocked_reason=f"Guardrail呼び出しエラー（Fail Closed）: {e}",
            )
        return self._interpret(response)

    @staticmethod
    def _interpret(response: dict[str, Any]) -> GuardrailResult:
        action = response.get("action", "NONE")
        assessments = response.get("assessments", []) or []
        outputs = response.get("outputs", []) or []
        masked_text = outputs[0].get("text") if outputs else None

        if action == "NONE":
            return GuardrailResult(
                decision=Decision.ALLOW, passed=True, action=action, raw=response
            )

        block_reason = _has_hard_block(assessments)
        if block_reason is not None:
            return GuardrailResult(
                decision=Decision.BLOCK,
                passed=False,
                action=action,
                blocked_reason=block_reason,
                filtered_text=masked_text,
                raw=response,
            )

        return GuardrailResult(
            decision=Decision.MASK,
            passed=True,
            action=action,
            filtered_text=masked_text,
            blocked_reason=response.get("actionReason"),
            raw=response,
        )
