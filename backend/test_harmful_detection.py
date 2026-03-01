"""
测试有害语检测功能（关键词 + LLM）
"""
import asyncio
import sys
import io

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from realtime.harmful_rules import is_harmful, is_harmful_advanced


async def test_harmful_detection():
    """测试有害语检测"""

    test_cases = [
        # (文本, 预期结果, 说明)
        ("你真聪明", False, "正常称赞"),
        ("你真是个废物", True, "侮辱性词汇"),
        ("操你妈", True, "脏话粗口"),
        ("再这样就不要你了", True, "威胁性语言"),
        ("我就问你，你还是人吗啊", True, "质疑性语言（需要LLM）"),
        ("你怎么这么没用", True, "否定贬低"),
        ("今天天气真好", False, "正常对话"),
        ("你为什么总是这么让人失望", True, "情感伤害（需要LLM）"),
    ]

    print("=" * 80)
    print("有害语检测测试")
    print("=" * 80)
    print()

    # 测试简单关键词检测
    print("1. 简单关键词检测:")
    print("-" * 80)
    for text, expected, desc in test_cases:
        result = is_harmful(text)
        status = "✓" if result == expected else "✗"
        harmful_str = "有害" if result else "正常"
        print(f"{status} [{harmful_str}] {text}")
        print(f"   ({desc})")
        print()

    # 测试高级检测（关键词 + LLM）
    print("\n2. 高级检测（关键词 + LLM）:")
    print("-" * 80)
    for text, expected, desc in test_cases:
        is_harmful_result, details = await is_harmful_advanced(text, use_llm=True)

        status = "✓" if is_harmful_result == expected else "✗"
        harmful_str = "有害" if is_harmful_result else "正常"
        method = details.get("method", "unknown")

        print(f"{status} [{harmful_str}] {text}")
        print(f"   ({desc})")
        print(f"   检测方法: {method}")

        if method == "keyword":
            print(f"   关键词: {details.get('keywords', [])}")
        elif method == "llm":
            print(f"   严重度: {details.get('severity', 0)}/5")
            print(f"   类别: {details.get('category', 'unknown')}")
            print(f"   分析: {details.get('explanation', '')}")

        print()

    print("=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_harmful_detection())
