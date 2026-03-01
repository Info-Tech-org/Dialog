"""
诊断 ASR 识别完整性
检查是否有遗漏的对话内容
"""
import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from qcloud_cos import CosConfig, CosS3Client
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.asr.v20190614 import asr_client, models
from config import settings
import time


def test_asr_completeness():
    """测试 ASR 识别完整性"""

    print("=" * 80)
    print("ASR 识别完整性诊断")
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
    cos_key = "audio/test_diagnose.m4a"

    print("上传音频到 COS...")
    with open(audio_file, 'rb') as fp:
        cos_client.put_object(
            Bucket=settings.tencent_cos_bucket,
            Body=fp,
            Key=cos_key,
            ContentType='audio/m4a'
        )

    # 生成预签名 URL
    audio_url = cos_client.get_presigned_download_url(
        Bucket=settings.tencent_cos_bucket,
        Key=cos_key,
        Expired=86400
    )
    print(f"音频 URL: {audio_url[:80]}...")
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
            "name": "当前配置 (ResTextFormat=0, 说话人分离)",
            "params": {
                "EngineModelType": "16k_zh",
                "ChannelNum": 1,
                "ResTextFormat": 0,
                "SourceType": 0,
                "Url": audio_url,
                "SpeakerDiarization": 1,
                "SpeakerNumber": 0,
                "FilterDirty": 0,
                "FilterModal": 0,
                "FilterPunc": 0,
                "ConvertNumMode": 1,
            }
        },
        {
            "name": "详细格式 (ResTextFormat=2, 无说话人分离)",
            "params": {
                "EngineModelType": "16k_zh",
                "ChannelNum": 1,
                "ResTextFormat": 2,
                "SourceType": 0,
                "Url": audio_url,
                "SpeakerDiarization": 0,
                "FilterDirty": 0,
                "FilterModal": 0,
                "FilterPunc": 0,
                "ConvertNumMode": 1,
            }
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试 {i}: {test_case['name']}")
        print('='*80)

        # 创建任务
        req = models.CreateRecTaskRequest()
        req.from_json_string(json.dumps(test_case['params']))
        resp = client.CreateRecTask(req)
        result = json.loads(resp.to_json_string())
        task_id = result['Data']['TaskId']
        print(f"任务 ID: {task_id}")

        # 等待完成
        print("等待识别完成...")
        while True:
            req = models.DescribeTaskStatusRequest()
            req.from_json_string(json.dumps({"TaskId": task_id}))
            resp = client.DescribeTaskStatus(req)
            result = json.loads(resp.to_json_string())
            data = result['Data']
            status = data.get('Status', 0)

            if status == 2:
                print("✓ 识别完成")
                break
            elif status == 3:
                print(f"✗ 识别失败: {data.get('ErrorMsg')}")
                continue
            else:
                print(f"  进行中... status={status}")
                time.sleep(3)

        # 显示结果
        print(f"\n结果统计:")
        print(f"  音频时长: {data.get('AudioDuration', 0)} 秒")

        result_text = data.get('Result', '')
        result_detail = data.get('ResultDetail')

        # 统计 Result 字段
        if result_text:
            import re
            pattern = r'\[0:([\d.]+),0:([\d.]+),(\d+)\]\s+(.+?)(?=\n\[|$)'
            matches = re.findall(pattern, result_text, re.DOTALL)
            print(f"  Result 段数: {len(matches)}")
            print(f"\n  Result 内容:")
            for j, match in enumerate(matches, 1):
                speaker_id = int(match[2])
                speaker = chr(65 + speaker_id)
                print(f"    [{j}] {match[0]}s-{match[1]}s 说话人{speaker}: {match[3][:50]}...")

        # 统计 ResultDetail 字段
        if result_detail:
            if isinstance(result_detail, list):
                print(f"\n  ResultDetail 段数: {len(result_detail)}")
                print(f"\n  ResultDetail 内容:")
                for j, item in enumerate(result_detail, 1):
                    speaker_id = item.get('SpeakerId', 0)
                    speaker = chr(65 + speaker_id)
                    start = item.get('StartMs', 0) / 1000
                    end = item.get('EndMs', 0) / 1000
                    text = item.get('FinalSentence', '')
                    print(f"    [{j}] {start:.2f}s-{end:.2f}s 说话人{speaker}: {text[:50]}...")
        else:
            print(f"  ResultDetail: None")

        print()

    print("=" * 80)
    print("诊断完成")
    print("=" * 80)


if __name__ == "__main__":
    test_asr_completeness()
