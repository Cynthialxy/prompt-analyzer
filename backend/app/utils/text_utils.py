"""Text processing utilities for prompt analysis."""

import re


def clean_prompt(text: str) -> str:
    """Basic text cleaning."""
    if not text:
        return ""
    text = text.strip()
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


def is_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def word_count(text: str) -> int:
    """Count words (handles both English and Chinese)."""
    if not text:
        return 0
    if is_chinese(text):
        # For Chinese, count characters as a proxy
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words
    return len(text.split())


def char_count(text: str) -> int:
    return len(text) if text else 0
