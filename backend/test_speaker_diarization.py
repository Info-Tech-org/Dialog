"""
测试不同参数对说话人分离的影响
"""
import sys
import io
import json
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from qcloud_cos import CosConfig, CosS3Client
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.asr.v20190614 import asr_client, models
from config import settings


def test_speaker_diarization_params():
    """测试不同参数对说话人分离的影响"""

    print("=" * 80)
    print("说话人分离参数测试")
    print("=" * 80)
    print()

    # 1. 上传音频到 COS
    config = CosConfig(
        Region=settings.tencent_cos_region,
        SecretId=settings.tencent_secret_id,
        SecretKey=settings.tencent_secret_key,
        Scheme='https'
    )
    cos_client = CosS3Client(config)

    audio_file = r'e:\Innox-SZ\info-tech\录音.m4a'
    cos_key = "audio/test_speaker_diarization.m4a"

    print("上传音频到 COS...")
    with open(audio_file, 'rb') as fp:
        cos_client.put_object(
            Bucket=settings.tencent_cos_bucket,
            Body=fp,
            Key=cos_key,
            ContentType='audio/m4a'
        )

    audio_url = cos_client.get_presigned_download_url(
        Bucket=settings.tencent_cos_bucket,
        Key=cos_key,
        Expired=86400
    )
    print(f"✓ 上传完成")
    print()

    # 2. 创建 ASR 客户端
    cred = credential.Credential(
        settings.tencent_secret_id,
        settings.tencent_secret_key
    )
    http_profile = HttpProfile()
    http_profile.endpoint = "asr.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = asr_client.AsrClient(cred, settings.tencent_asr_region, client_profile)

    # 3. 测试不同的参数组合
    test_cases = [
        {
            "name": "方案1: 基础配置 (SpeakerNumber=0 自动检测)",
            "params": {
                "EngineModelType": "16k_zh",
                "ChannelNum": 1,
                "ResTextFormat": 0,
                "SourceType": 0,
                "Url": audio_url,
                "SpeakerDiarization": 1,
                "SpeakerNumber": 0,  # 自动检测
                "FilterDirty": 0,
                "FilterModal": 0,
                "ConvertNumMode": 1,
            }
        },
        {
            "name": "方案2: 明确指定2个说话人",
            "params": {
                "EngineModelType": "16k_zh",
                "ChannelNum": 1,
                "ResTextFormat": 0,
                "SourceType": 0,
                "Url": audio_url,
                "SpeakerDiarization": 1,
                "SpeakerNumber": 2,  # 明确指定2人
                "FilterDirty": 0,
                "FilterModal": 0,
                "ConvertNumMode": 1,
            }
        },
        {
            "name": "方案3: 使用方言模型",
            "params": {
                "EngineModelType": "16k_zh_dialect",  # 方言模型
                "ChannelNum": 1,
                "ResTextFormat": 0,
                "SourceType": 0,
                "Url": audio_url,
                "SpeakerDiarization": 1,
                "SpeakerNumber": 2,
                "FilterDirty": 0,
                "FilterModal": 0,
                "ConvertNumMode": 1,
            }
        },
        {
            "name": "方案4: 详细格式 + 说话人分离",
            "params": {
                "EngineModelType": "16k_zh",
                "ChannelNum": 1,
                "ResTextFormat": 2,  # 详细格式
                "SourceType": 0,
                "Url": audio_url,
                "SpeakerDiarization": 1,
                "SpeakerNumber": 2,
                "FilterDirty": 0,
                "FilterModal": 0,
                "ConvertNumMode": 1,
            }
        },
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试 {i}/4: {test_case['name']}")
        print('='*80)

        # 创建任务
        req = models.CreateRecTaskRequest()
        req.from_json_string(json.dumps(test_case['params']))
        resp = client.CreateRecTask(req)
        result = json.loads(resp.to_json_string())
        task_id = result['Data']['TaskId']
        print(f"任务 ID: {task_id}")

        # 等待完成
        print("等待识别完成...", end='', flush=True)
        while True:
            req = models.DescribeTaskStatusRequest()
            req.from_json_string(json.dumps({"TaskId": task_id}))
            resp = client.DescribeTaskStatus(req)
            result = json.loads(resp.to_json_string())
            data = result['Data']
            status = data.get('Status', 0)

            if status == 2:
                print(" ✓ 完成")
                break
            elif status == 3:
                print(f" ✗ 失败: {data.get('ErrorMsg')}")
                break
            else:
                print(".", end='', flush=True)
                time.sleep(3)

        if status != 2:
            continue

        # 分析结果
        result_text = data.get('Result', '')
        result_detail = data.get('ResultDetail')

        # 统计说话人分布
        speaker_stats = {}

        if result_text:
            import re
            pattern = r'\[0:([\d.]+),0:([\d.]+),(\d+)\]\s+(.+?)(?=\n\[|$)'
            matches = re.findall(pattern, result_text, re.DOTALL)

            for match in matches:
                speaker_id = int(match[2])
                speaker = chr(65 + speaker_id)
                if speaker not in speaker_stats:
                    speaker_stats[speaker] = 0
                speaker_stats[speaker] += 1

        elif result_detail and isinstance(result_detail, list):
            for item in result_detail:
                speaker_id = item.get('SpeakerId', 0)
                speaker = chr(65 + speaker_id)
                if speaker not in speaker_stats:
                    speaker_stats[speaker] = 0
                speaker_stats[speaker] += 1

        # 显示结果
        print(f"\n结果分析:")
        print(f"  识别段数: {len(matches) if result_text else len(result_detail) if result_detail else 0}")
        print(f"  说话人分布: {speaker_stats}")

        if len(speaker_stats) > 1:
            print(f"  ✓ 成功识别出 {len(speaker_stats)} 个说话人")
        else:
            print(f"  ✗ 所有语音被识别为同一说话人")

        # 显示详细内容
        if result_text:
            print(f"\n  详细内容:")
            for j, match in enumerate(matches, 1):
                speaker_id = int(match[2])
                speaker = chr(65 + speaker_id)
                text = match[3].strip()
                print(f"    [{j}] 说话人{speaker}: {text}")

        results.append({
            "name": test_case['name'],
            "speakers": len(speaker_stats),
            "segments": len(matches) if result_text else len(result_detail) if result_detail else 0,
            "distribution": speaker_stats
        })

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    for i, res in enumerate(results, 1):
        success = "✓" if res['speakers'] > 1 else "✗"
        print(f"{success} {res['name']}")
        print(f"   说话人数: {res['speakers']}, 识别段数: {res['segments']}")
        print(f"   分布: {res['distribution']}")
        print()

    # 结论
    print("=" * 80)
    print("结论:")
    if any(r['speakers'] > 1 for r in results):
        print("✓ 找到可以识别多个说话人的配置")
        best = max(results, key=lambda x: x['speakers'])
        print(f"   推荐配置: {best['name']}")
    else:
        print("✗ 所有配置都无法区分说话人")
        print("   可能原因:")
        print("   1. 录音中确实只有一个人的声音")
        print("   2. 两个人声音特征太相似 (如性别、年龄、音色相近)")
        print("   3. 音频质量问题 (噪音、混响等)")
        print("\n   建议:")
        print("   - 使用声音特征差异更明显的测试音频")
        print("   - 确保录音质量清晰、背景噪音低")
        print("   - 说话人之间保持适当停顿")
    print("=" * 80)


if __name__ == "__main__":
    test_speaker_diarization_params()
