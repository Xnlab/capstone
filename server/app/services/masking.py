"""AI 전송 전 비식별화 (3주차 보안 설계 ②마스킹 / ③최소 전송)."""

import re

_RULES: list[tuple[str, re.Pattern, str]] = [
    ("주민등록번호", re.compile(r"\b\d{6}\s?-\s?[1-4]\d{6}\b"), "[주민번호]"),
    ("이메일", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[이메일]"),
    ("전화번호", re.compile(r"\b0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}\b"), "[전화번호]"),
    ("계좌번호", re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,8}(?:-\d{1,4})?\b"), "[계좌번호]"),
]


def mask_text(text: str) -> tuple[str, dict[str, int]]:
    """민감정보를 치환하고, 항목별 치환 건수를 함께 돌려준다."""
    counts: dict[str, int] = {}
    for name, pattern, repl in _RULES:
        text, n = pattern.subn(repl, text)
        if n:
            counts[name] = counts.get(name, 0) + n
    return text, counts
