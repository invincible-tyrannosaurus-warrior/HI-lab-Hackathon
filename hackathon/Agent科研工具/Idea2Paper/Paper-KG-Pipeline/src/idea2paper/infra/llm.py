import json
import re
import time
import warnings
from typing import Dict, Any, Optional

# 抑制 urllib3 的 OpenSSL 警告
warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

from idea2paper.config import (
    LLM_API_KEY,
    LLM_API_URL,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_ANTHROPIC_VERSION,
    LLM_EXTRA_HEADERS,
    LLM_EXTRA_BODY,
)
from idea2paper.infra.run_context import get_logger
from idea2paper.infra.llm_providers import (
    openai_compatible,
    openai_responses,
    anthropic,
    gemini,
)
from idea2paper.infra.llm_providers.common import parse_extra, redact_mapping

def _parse_extra_config(name: str, value, logger):
    data, error = parse_extra(value)
    if error:
        msg = f"⚠️  {name} parse failed: {error}"
        print(msg)
        if logger:
            logger.log_event("llm_extra_invalid", {"name": name, "error": error})
    return data

def call_llm(prompt: str, temperature: float = 0.7, max_tokens: int = 4096, timeout: int = 120) -> str:
    """
    调用 LLM API（支持重试和延长超时）

    Args:
        prompt: 提示文本
        temperature: 温度参数
        max_tokens: 最大 token 数
        timeout: 请求超时时间（秒），默认 120s
    """
    logger = get_logger()
    start_ts = time.time()

    if not LLM_API_KEY:
        print("⚠️  警告: LLM_API_KEY 未配置，使用模拟输出")
        simulated_text = f"[模拟LLM输出] Prompt: {prompt[:100]}..."
        if logger:
            logger.log_llm_call(
                request={
                    "provider": LLM_PROVIDER,
                    "model": LLM_MODEL,
                    "url": LLM_API_URL or LLM_BASE_URL,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "timeout": timeout,
                    "prompt": prompt,
                    "simulated": True
                },
                response={
                    "ok": False,
                    "text": simulated_text,
                    "latency_ms": int((time.time() - start_ts) * 1000),
                    "error": "LLM_API_KEY not configured"
                }
            )
        return simulated_text

    extra_headers = _parse_extra_config("LLM_EXTRA_HEADERS_JSON", LLM_EXTRA_HEADERS, logger)
    extra_body = _parse_extra_config("LLM_EXTRA_BODY_JSON", LLM_EXTRA_BODY, logger)
    provider = (LLM_PROVIDER or "openai_compatible_chat").strip().lower()

    try:
        if provider in ("openai_compatible_chat", "openai_compatible"):
            result = openai_compatible.call_openai_compatible_chat(
                prompt,
                model=LLM_MODEL,
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                api_url=LLM_API_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                extra_headers=extra_headers,
                extra_body=extra_body,
            )
        elif provider in ("openai_responses", "responses"):
            result = openai_responses.call_openai_responses(
                prompt,
                model=LLM_MODEL,
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                api_url=LLM_API_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                extra_headers=extra_headers,
                extra_body=extra_body,
            )
        elif provider == "anthropic":
            result = anthropic.call_anthropic(
                prompt,
                model=LLM_MODEL,
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                api_url=LLM_API_URL,
                anthropic_version=LLM_ANTHROPIC_VERSION,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                extra_headers=extra_headers,
                extra_body=extra_body,
            )
        elif provider == "gemini":
            result = gemini.call_gemini(
                prompt,
                model=LLM_MODEL,
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                api_url=LLM_API_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                extra_headers=extra_headers,
                extra_body=extra_body,
            )
        else:
            raise ValueError(f"unknown LLM_PROVIDER: {LLM_PROVIDER}")
    except Exception as e:
        if logger:
            logger.log_llm_call(
                request={
                    "provider": LLM_PROVIDER,
                    "model": LLM_MODEL,
                    "url": LLM_API_URL or LLM_BASE_URL,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "timeout": timeout,
                    "prompt": prompt,
                    "simulated": False,
                    "extra_headers": redact_mapping(extra_headers),
                    "extra_body": redact_mapping(extra_body),
                },
                response={
                    "ok": False,
                    "text": "",
                    "latency_ms": int((time.time() - start_ts) * 1000),
                    "error": str(e)
                }
            )
        print(f"❌ LLM 调用失败: {e}")
        return ""

    if logger:
        logger.log_llm_call(
            request={
                "provider": LLM_PROVIDER,
                "model": LLM_MODEL,
                "url": result.get("url") or (LLM_API_URL or LLM_BASE_URL),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": timeout,
                "prompt": prompt,
                "simulated": False,
                "extra_headers": redact_mapping(extra_headers),
                "extra_body": redact_mapping(extra_body),
            },
            response={
                "ok": bool(result.get("ok")),
                "text": result.get("text", ""),
                "latency_ms": int((time.time() - start_ts) * 1000),
                "error": result.get("error", "")
            }
        )

    if result.get("ok"):
        return result.get("text", "")
    print(f"❌ LLM 调用失败: {result.get('error')}")
    return ""

def clean_json_text(text: str) -> str:
    """清理 JSON 文本中的 Markdown 标记和非法字符"""
    clean_text = text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    return clean_text.strip()

def parse_json_from_llm(response: str) -> Optional[Dict[str, Any]]:
    """从 LLM 响应中解析 JSON，包含自动修复逻辑"""
    try:
        # 1. 基础清理
        clean_response = clean_json_text(response)

        # 2. 提取 JSON 部分 (寻找最外层的 {})
        start = clean_response.find('{')
        end = clean_response.rfind('}') + 1

        if start >= 0 and end > start:
            json_str = clean_response[start:end]

            # 2.1 预处理：处理非法控制字符
            def replace_control_chars(match):
                s = match.group(0)
                return s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')

            # 匹配双引号包裹的内容
            json_str = re.sub(r'"((?:[^"\\]|\\.)*)"', replace_control_chars, json_str, flags=re.DOTALL)

            # 2.2 尝试直接解析
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # 2.3 尝试修复常见的 JSON 错误
            repaired = json_str
            # 移除尾部逗号
            repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
            # 修复字段间缺失逗号 (如 "val" "key")
            repaired = re.sub(r'("\s*)\n?\s*"', r'\1,\n"', repaired)
            # 修复结构间缺失逗号 (如 } "key" 或 ] "key")
            repaired = re.sub(r'(}|])\s*\n?\s*"', r'\1,\n"', repaired)

            try:
                return json.loads(repaired)
            except:
                pass

        return None

    except Exception as e:
        print(f"   ⚠️  JSON 解析工具内部错误: {e}")
        return None

def compute_jaccard_similarity(text1: str, text2: str) -> float:
    """计算文本相似度（Jaccard）"""
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2

    return len(intersection) / len(union)
