"""
测试实时语音识别 + 有害检测 WebSocket

这个脚本模拟设备端，发送PCM音频流到后端，并接收：
1. ASR 识别结果
2. 有害内容警告
"""

import asyncio
import websockets
import json
import struct
import numpy as np
import argparse
from pathlib import Path


def generate_test_pcm(duration_seconds=5.0, sample_rate=16000, frequency=440):
    """
    生成测试用的 PCM 音频数据（正弦波）

    Args:
        duration_seconds: 音频时长（秒）
        sample_rate: 采样率
        frequency: 频率（Hz）

    Returns:
        bytes: PCM 格式音频数据 (s16le)
    """
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), False)
    wave = np.sin(frequency * 2 * np.pi * t)

    # 转换为 16-bit PCM
    pcm_data = (wave * 32767).astype(np.int16)

    return pcm_data.tobytes()


def load_pcm_file(file_path: str) -> bytes:
    """
    加载 PCM 文件

    Args:
        file_path: PCM 文件路径

    Returns:
        bytes: PCM 数据
    """
    with open(file_path, 'rb') as f:
        return f.read()


async def test_realtime_detection(
    base_url: str,
    device_token: str = None,
    session_id: str = None,
    device_id: str = "test_device",
    use_test_audio: bool = True,
    pcm_file: str = None,
    chunk_size: int = 3200,  # 100ms at 16kHz, 16-bit
):
    """
    测试实时检测 WebSocket

    Args:
        base_url: WebSocket 基础 URL (如 ws://localhost:8000)
        device_token: 设备认证 token
        session_id: 会话 ID（可选，服务器会自动生成）
        device_id: 设备 ID
        use_test_audio: 是否使用测试音频（正弦波），否则需要提供 pcm_file
        pcm_file: PCM 文件路径（如果 use_test_audio=False）
        chunk_size: 每次发送的数据块大小（字节）
    """

    # 构建 WebSocket URL
    ws_url = f"{base_url}/ws/realtime/stream"
    params = []
    if device_token:
        params.append(f"device_token={device_token}")
    if session_id:
        params.append(f"session_id={session_id}")
    if device_id:
        params.append(f"device_id={device_id}")

    if params:
        ws_url += "?" + "&".join(params)

    print(f"🔗 连接到: {ws_url}")

    # 准备音频数据
    if use_test_audio:
        print("📢 使用测试音频（正弦波，5秒）")
        pcm_data = generate_test_pcm(duration_seconds=5.0)
    else:
        if not pcm_file or not Path(pcm_file).exists():
            print(f"❌ PCM 文件不存在: {pcm_file}")
            return
        print(f"📁 加载 PCM 文件: {pcm_file}")
        pcm_data = load_pcm_file(pcm_file)

    print(f"📊 音频数据大小: {len(pcm_data)} 字节 ({len(pcm_data) / 32000:.2f} 秒)")

    # 连接到 WebSocket
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket 连接成功")

            # 创建两个并发任务：发送音频 和 接收消息

            async def send_audio():
                """发送音频数据"""
                try:
                    total_chunks = len(pcm_data) // chunk_size + 1

                    for i in range(0, len(pcm_data), chunk_size):
                        chunk = pcm_data[i:i + chunk_size]
                        await websocket.send(chunk)

                        chunk_num = i // chunk_size + 1
                        print(f"📤 发送音频块 {chunk_num}/{total_chunks} ({len(chunk)} 字节)")

                        # 模拟实时流：每 100ms 发送一次
                        await asyncio.sleep(0.1)

                    print("✅ 音频发送完成")

                    # 发送完后等待一段时间让 ASR 处理完
                    await asyncio.sleep(2.0)

                except Exception as e:
                    print(f"❌ 发送音频时出错: {e}")

            async def receive_messages():
                """接收服务器消息"""
                try:
                    harmful_alerts = []
                    asr_results = []

                    async for message in websocket:
                        data = json.loads(message)
                        msg_type = data.get("type")

                        if msg_type == "status":
                            print(f"ℹ️  状态: {data.get('message')}")
                            print(f"   Session ID: {data.get('session_id')}")

                        elif msg_type == "asr":
                            text = data.get("text", "")
                            is_final = data.get("is_final", False)
                            start = data.get("start", 0)
                            end = data.get("end", 0)

                            asr_results.append(data)

                            final_mark = "✓" if is_final else "…"
                            print(f"🎤 ASR [{final_mark}]: '{text}' ({start:.2f}s - {end:.2f}s)")

                        elif msg_type == "harmful_alert":
                            text = data.get("text", "")
                            keywords = data.get("keywords", [])
                            severity = data.get("severity", 0)
                            method = data.get("method", "unknown")

                            harmful_alerts.append(data)

                            print(f"🚨 ⚠️  有害内容警告!")
                            print(f"   文本: '{text}'")
                            print(f"   关键词: {keywords}")
                            print(f"   严重度: {severity}/5")
                            print(f"   检测方法: {method}")

                        elif msg_type == "error":
                            print(f"❌ 错误: {data.get('message')}")

                        else:
                            print(f"❓ 未知消息类型: {msg_type}")
                            print(f"   数据: {data}")

                    # 汇总结果
                    print("\n" + "="*60)
                    print("📊 测试结果汇总")
                    print("="*60)
                    print(f"ASR 识别结果数: {len(asr_results)}")
                    print(f"有害内容警告数: {len(harmful_alerts)}")

                    if asr_results:
                        print("\n完整识别文本:")
                        full_text = " ".join([r.get("text", "") for r in asr_results if r.get("is_final")])
                        print(f"  {full_text}")

                    if harmful_alerts:
                        print("\n有害内容详情:")
                        for i, alert in enumerate(harmful_alerts, 1):
                            print(f"  {i}. '{alert.get('text')}' - 关键词: {alert.get('keywords')}")

                    print("="*60)

                except websockets.exceptions.ConnectionClosed:
                    print("ℹ️  连接已关闭")
                except Exception as e:
                    print(f"❌ 接收消息时出错: {e}")

            # 并发运行发送和接收
            await asyncio.gather(
                send_audio(),
                receive_messages(),
                return_exceptions=True
            )

    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket 连接失败: {e}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="测试实时语音识别 + 有害检测")
    parser.add_argument(
        "--url",
        default="ws://localhost:8000",
        help="WebSocket 基础 URL (默认: ws://localhost:8000)"
    )
    parser.add_argument(
        "--token",
        default=None,
        help="设备认证 token (可选)"
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="会话 ID (可选，服务器会自动生成)"
    )
    parser.add_argument(
        "--device-id",
        default="test_device",
        help="设备 ID (默认: test_device)"
    )
    parser.add_argument(
        "--pcm-file",
        default=None,
        help="PCM 文件路径 (可选，不提供则使用测试音频)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=3200,
        help="每次发送的数据块大小（字节，默认 3200 = 100ms）"
    )

    args = parser.parse_args()

    use_test_audio = args.pcm_file is None

    asyncio.run(test_realtime_detection(
        base_url=args.url,
        device_token=args.token,
        session_id=args.session_id,
        device_id=args.device_id,
        use_test_audio=use_test_audio,
        pcm_file=args.pcm_file,
        chunk_size=args.chunk_size,
    ))


if __name__ == "__main__":
    main()
