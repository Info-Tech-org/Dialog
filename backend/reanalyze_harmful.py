"""
重新分析数据库中的所有对话，更新有害标记
使用扩充的关键词库 + LLM 智能检测
"""
import asyncio
import sys
import io

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from sqlmodel import Session as DBSession, select
from models import Utterance, Session, engine
from realtime.harmful_rules import is_harmful_advanced


async def reanalyze_all_utterances():
    """重新分析所有 utterances"""

    print("=" * 80)
    print("重新分析数据库中的有害语句")
    print("=" * 80)
    print()

    with DBSession(engine) as db:
        # 获取所有 utterances
        stmt = select(Utterance)
        utterances = list(db.exec(stmt).all())

        print(f"共找到 {len(utterances)} 条对话记录")
        print()

        updated_count = 0
        harmful_count = 0

        for i, utt in enumerate(utterances, 1):
            # 使用高级检测
            is_harmful_result, details = await is_harmful_advanced(utt.text, use_llm=True)

            # 如果标记发生变化
            if is_harmful_result != utt.harmful_flag:
                old_status = "有害" if utt.harmful_flag else "正常"
                new_status = "有害" if is_harmful_result else "正常"

                print(f"[{i}/{len(utterances)}] 更新: {old_status} → {new_status}")
                print(f"  文本: {utt.text}")
                print(f"  方法: {details.get('method')}")
                if details.get('method') == 'keyword':
                    print(f"  关键词: {details.get('keywords', [])}")
                elif details.get('method') == 'llm':
                    print(f"  严重度: {details.get('severity')}/5, 类别: {details.get('category')}")
                print()

                # 更新数据库
                utt.harmful_flag = is_harmful_result
                db.add(utt)
                updated_count += 1

            if is_harmful_result:
                harmful_count += 1

        # 提交所有更改
        db.commit()

        # 更新所有 sessions 的 harmful_count
        print("-" * 80)
        print("更新会话统计...")
        sessions = db.exec(select(Session)).all()
        for session in sessions:
            stmt = select(Utterance).where(
                Utterance.session_id == session.session_id,
                Utterance.harmful_flag == True
            )
            harmful_in_session = len(list(db.exec(stmt).all()))
            session.harmful_count = harmful_in_session
            db.add(session)

        db.commit()

        print()
        print("=" * 80)
        print(f"分析完成!")
        print(f"  总对话数: {len(utterances)}")
        print(f"  更新数量: {updated_count}")
        print(f"  有害对话: {harmful_count}")
        print(f"  正常对话: {len(utterances) - harmful_count}")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(reanalyze_all_utterances())
