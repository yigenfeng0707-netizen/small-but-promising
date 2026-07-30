"""识别 Agent：调用 Qwen-VL 多模态模型识别化学品包装/标签。

输入一张化学品包装图片 URL，输出化学品名、品牌、类别、成分表文字、原始 OCR 文本。
"""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

from services.qwen_client import call_qwen3, call_qwen_vl


# ---------- 输入/输出 schema ----------

class RecognizerInput(BaseModel):
    image_url: str = Field(..., description="化学品包装图片的可访问 URL")


class RecognizerOutput(BaseModel):
    chemical_name: str = Field("", description="化学品名称")
    brand: str = Field("", description="品牌")
    category: str = Field("", description="类别（清洁剂/消毒剂/农药/药品/化妆品/涂料/其他）")
    ingredients_text: str = Field("", description="包装上标注的成分表文字")
    raw_ocr: str = Field("", description="对包装文字的完整 OCR 结果")


# ---------- Agent ----------

class RecognizerAgent:
    """识别 Agent：调 Qwen-VL 识别化学品包装。"""

    def __init__(
        self,
        qwen_caller: Callable[..., Awaitable[str]] = call_qwen3,
        qwen_vl_caller: Callable[..., Awaitable[str]] = call_qwen_vl,
        retriever: Optional[Any] = None,
    ) -> None:
        self.qwen_caller = qwen_caller
        self.qwen_vl_caller = qwen_vl_caller
        self.retriever = retriever

    async def run(self, image_url: str, **kwargs: Any) -> dict:
        """识别化学品包装。

        Args:
            image_url: 化学品包装图片 URL。

        Returns:
            dict 形式的 RecognizerOutput，包含 chemical_name/brand/category/
            ingredients_text/raw_ocr 五个字段。
        """
        prompt = self._build_prompt()
        raw_text = await self.qwen_vl_caller(image_url, prompt)
        parsed = self._parse_json(raw_text)
        # raw_ocr 兜底链：模型返回的 raw_ocr → 解析失败时的 raw_text → 原始模型文本
        raw_ocr_value = (
            parsed.get("raw_ocr")
            or parsed.get("raw_text")
            or raw_text
        )
        # 用 schema 做字段兜底，缺字段填空串
        out = RecognizerOutput(
            chemical_name=str(parsed.get("chemical_name", "")),
            brand=str(parsed.get("brand", "")),
            category=str(parsed.get("category", "")),
            ingredients_text=str(parsed.get("ingredients_text", "")),
            raw_ocr=str(raw_ocr_value),
        )
        return out.model_dump()

    def _build_prompt(self) -> str:
        """构造 Qwen-VL 提示词。"""
        return (
            "你是一名家庭化学品识别专家。请仔细查看图片中的化学品包装/标签，识别以下信息并以 JSON 格式返回：\n"
            "1. chemical_name: 化学品名称（如\"洁厕灵\"、\"84消毒液\"、\"管道疏通剂\"）\n"
            "2. brand: 品牌（如\"蓝月亮\"、\"威猛先生\"，无法识别则填\"未知\"）\n"
            "3. category: 类别，必须从以下选项中选择其一：清洁剂、消毒剂、农药、药品、化妆品、涂料、其他\n"
            "4. ingredients_text: 包装上标注的成分表文字（保留原文，无法识别则填\"未标注\"）\n"
            "5. raw_ocr: 你对包装上所有可见文字的完整 OCR 结果\n\n"
            "要求：\n"
            "- 仅返回 JSON，使用 ```json 代码块包裹\n"
            "- 字段名严格使用上述英文键名\n"
            "- 若图片不是化学品包装或无法识别，所有字段填\"未知\"或\"未标注\"\n"
            "- 输出示例：\n"
            "```json\n"
            "{\n"
            "  \"chemical_name\": \"洁厕灵\",\n"
            "  \"brand\": \"威猛先生\",\n"
            "  \"category\": \"清洁剂\",\n"
            "  \"ingredients_text\": \"盐酸、表面活性剂、缓蚀剂\",\n"
            "  \"raw_ocr\": \"威猛先生洁厕灵 含盐酸...\"\n"
            "}\n"
            "```"
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        """稳健解析模型返回的 JSON。

        顺序：直接 json.loads → 提取 ```json...``` 块 → 提取首个 {...} → 包在 raw_text 里。
        """
        if not text:
            return {}
        text = text.strip()
        # 1. 直接 json.loads
        try:
            return json.loads(text)
        except Exception:
            pass
        # 2. 提取 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # 3. 提取首个 {...} 块（贪婪到末尾）
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        # 4. 失败兜底
        return {"raw_text": text}
