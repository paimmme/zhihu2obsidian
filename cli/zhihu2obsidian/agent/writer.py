"""AI 写作助手 — DeepSeek API."""

from __future__ import annotations

from typing import Optional


DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"

SYSTEM_PROMPT = """你是一位知乎答主，根据参考素材生成知乎回答。

要求：
- 风格自然、接地气，像真人写的，不是AI文风
- 融入你自己的观点和经历（如果有提供的话）
- 可以引用素材中的观点和数据，但不要大段照搬
- 用中文写，口语化但逻辑清晰
- 适当用 **粗体** 强调核心观点
- 不要打官腔、不要堆砌空洞的词汇
- 如果是给特定问题的回答，开头直接切入主题
- 如果用户提供了个人观点，一定要融入进去

输出格式：
- 标题：无需（知乎回答没有标题）
- 正文：直接是回答内容

注意：你不是在做内容总结，而是在创作一篇原创风格的知乎回答。"""

WRITE_PROMPT = """## 问题/主题
{question}

## 参考素材（摘自个人知识库）
{context}

## 你的个人观点（可选）
{personal_take}

请根据以上内容，生成一篇原创风格的知乎回答。"""


class Writer:
    """AI 写作助手 — 调用 DeepSeek API 生成知乎回答."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self.api_key = api_key
        self.model = model

    def write_answer(
        self,
        question: str,
        context: str,
        personal_take: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """生成知乎回答."""
        import requests

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": WRITE_PROMPT.format(
                question=question,
                context=context,
                personal_take=personal_take or "（无）",
            )},
        ]

        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
            timeout=60,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"DeepSeek API 请求失败: HTTP {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def write_with_retrieval(
        self,
        question: str,
        context_chunks: list[dict],
        personal_take: str = "",
        temperature: float = 0.7,
    ) -> str:
        """从检索结果自动构建上下文，然后生成回答."""
        # Build context string from chunks
        context_parts = []
        seen_sources: set = set()

        for group in context_chunks:
            for chunk in group.get("chunks", []):
                source = chunk["metadata"].get("content_id", "")
                if source and source not in seen_sources:
                    seen_sources.add(source)
                    title = chunk["metadata"].get("title", "")
                    author = chunk["metadata"].get("author", "")
                    section = chunk["metadata"].get("section", "")
                    header = f"来源: {title}" if title else f"来源: {source}"
                    if author:
                        header += f" (作者: {author})"
                    if section:
                        header += f" → {section}"
                    context_parts.append(f"\n### {header}")
                    context_parts.append(chunk["text"])

        context = "\n".join(context_parts)

        return self.write_answer(
            question=question,
            context=context,
            personal_take=personal_take,
            temperature=temperature,
        )
