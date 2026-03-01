"""
测试音频上传和 ASR 处理完整流程
"""
import requests
import time

# API 配置
API_BASE = "http://localhost:8000"
AUDIO_FILE = r"e:\Innox-SZ\info-tech\录音.m4a"

def test_upload_and_process():
    """测试上传和处理流程"""

    # 1. 上传音频文件
    print("=" * 70)
    print("1. 上传音频文件...")
    print("=" * 70)

    with open(AUDIO_FILE, 'rb') as f:
        files = {'file': ('录音.m4a', f, 'audio/m4a')}
        response = requests.post(f"{API_BASE}/api/upload", files=files)

    if response.status_code != 200:
        print(f"❌ 上传失败: {response.status_code}")
        print(response.text)
        return

    result = response.json()
    session_id = result['session_id']
    print(f"✓ 上传成功!")
    print(f"  Session ID: {session_id}")
    print(f"  Device ID: {result['device_id']}")
    print(f"  Audio Path: {result['audio_path']}")

    # 2. 等待 ASR 处理完成
    print("\n" + "=" * 70)
    print("2. 等待 ASR 处理...")
    print("=" * 70)

    max_wait = 120  # 最多等待 2 分钟
    start_time = time.time()

    while time.time() - start_time < max_wait:
        # 查询 session 详情
        response = requests.get(f"{API_BASE}/api/sessions/{session_id}")

        if response.status_code != 200:
            print(f"❌ 查询失败: {response.status_code}")
            return

        data = response.json()
        utterance_count = len(data.get('utterances', []))

        if utterance_count > 0:
            # 检查是否是占位数据
            first_utterance = data['utterances'][0]
            if "示例文本" in first_utterance['text']:
                print(f"⏳ 仍在使用占位数据，等待真实处理...")
                time.sleep(3)
                continue
            else:
                print(f"✓ 处理完成! 识别出 {utterance_count} 段对话")
                break
        else:
            print(f"⏳ 等待处理中... ({int(time.time() - start_time)}s)")
            time.sleep(3)
    else:
        print(f"❌ 处理超时")
        return

    # 3. 显示识别结果
    print("\n" + "=" * 70)
    print("3. 识别结果:")
    print("=" * 70)

    session_data = data
    print(f"\n会话信息:")
    print(f"  ID: {session_data['session_id']}")
    print(f"  设备: {session_data['device_id']}")
    print(f"  时长: {session_data['duration_seconds']:.2f}s")
    print(f"  有害内容数: {session_data['harmful_count']}")

    print(f"\n对话内容:")
    for i, utt in enumerate(session_data['utterances'], 1):
        print(f"\n[{i}] 说话人 {utt['speaker']} ({utt['start']:.2f}s - {utt['end']:.2f}s)")
        print(f"    {utt['text']}")
        if utt.get('harmful_flag'):
            print(f"    ⚠️  检测到有害内容!")

    print("\n" + "=" * 70)
    print("✓ 测试完成!")
    print("=" * 70)

if __name__ == '__main__':
    test_upload_and_process()
