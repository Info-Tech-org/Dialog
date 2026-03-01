"""
检查最新的 utterances 并与当前检测结果对比
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from sqlmodel import Session, select
from models import Utterance, engine
from realtime.harmful_rules import is_harmful, get_harmful_keywords

with Session(engine) as db:
    # Get the latest utterances
    stmt = select(Utterance).order_by(Utterance.id.desc()).limit(10)
    utterances = list(db.exec(stmt).all())

    print('最新的 10 条 utterances:')
    print('=' * 120)

    mismatch_count = 0

    for utt in utterances:
        harmful_str = '有害' if utt.harmful_flag else '正常'
        print(f'ID: {utt.id} | Session: {utt.session_id} | Speaker: {utt.speaker} | [{harmful_str}]')
        print(f'  文本: {utt.text}')

        # Test with current keyword library
        current_result = is_harmful(utt.text)
        keywords = get_harmful_keywords(utt.text)

        if current_result != utt.harmful_flag:
            mismatch_count += 1
            current_str = '有害' if current_result else '正常'
            print(f'  ⚠️  不一致! 数据库: {harmful_str}, 当前检测: {current_str}')
            print(f'  ⚠️  匹配关键词: {keywords}')

        print()

    print('=' * 120)
    print(f'总计: {len(utterances)} 条, 不一致: {mismatch_count} 条')
