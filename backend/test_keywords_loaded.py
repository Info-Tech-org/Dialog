"""
测试关键词库是否正确加载
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from realtime.harmful_rules import HARMFUL_KEYWORDS, is_harmful, get_harmful_keywords

print("=" * 80)
print("关键词库加载测试")
print("=" * 80)
print()

print(f"总关键词数: {len(HARMFUL_KEYWORDS)}")
print()

print("关键词列表:")
for i, keyword in enumerate(HARMFUL_KEYWORDS, 1):
    print(f"  {i}. {keyword}")

print()
print("=" * 80)
print("测试用例")
print("=" * 80)

test_texts = [
    "操你妈的沈阳快解放了都子啊",
    "操你妈你妈了个逼的沈阳快解放了吧？",
    "你真聪明",
]

for text in test_texts:
    is_harmful_result = is_harmful(text)
    keywords = get_harmful_keywords(text)
    print(f"\n文本: {text}")
    print(f"  结果: {'有害' if is_harmful_result else '正常'}")
    print(f"  匹配关键词: {keywords}")

print()
print("=" * 80)
