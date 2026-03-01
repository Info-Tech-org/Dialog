# 腾讯云 COS 配置指南

## 为什么需要配置 COS？

腾讯云录音文件识别 API 要求音频文件必须是**公网可访问的 URL**。本地文件路径无法被腾讯云服务器访问，因此需要先将音频文件上传到对象存储（COS），获取公网 URL 后才能进行 ASR 识别。

**当前状态：**
- ❌ COS 未配置 → 使用占位数据（示例文本）
- ✅ COS 已配置 → 真实 ASR 识别 + 说话人分离

## 配置步骤

### 1. 开通腾讯云对象存储 (COS)

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 进入 [对象存储 COS 控制台](https://console.cloud.tencent.com/cos)
3. 点击"创建存储桶"

### 2. 创建存储桶

配置建议：
- **名称**: 自定义，例如 `audio-bucket`（系统会自动添加后缀）
- **所属地域**: 选择与 ASR 服务相同的地域（如 `广州 ap-guangzhou`）
- **访问权限**: 选择"公有读私有写"
- **其他配置**: 保持默认即可

创建完成后，记录完整的存储桶名称，格式如：`audio-bucket-1234567890`

### 3. 更新配置文件

编辑 `backend/config/settings.py`，填写以下配置：

```python
# Tencent Cloud COS (对象存储)
tencent_cos_region: Optional[str] = "ap-guangzhou"  # 您的 COS 地域
tencent_cos_bucket: Optional[str] = "audio-bucket-1234567890"  # 您的存储桶名称
```

### 4. 安装 COS SDK

```bash
cd backend
python -m pip install cos-python-sdk-v5==1.9.30
```

或直接：
```bash
cd backend
python -m pip install -r requirements.txt
```

### 5. 重启后端服务

配置完成后重启后端：
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 验证配置

上传音频文件后，查看后端日志：

**COS 配置成功：**
```
INFO - Local audio file detected, attempting COS upload: ./data/audio/...
INFO - Uploaded to COS: https://audio-bucket-xxx.cos.ap-guangzhou.myqcloud.com/...
INFO - Created ASR task: 123456789
INFO - ASR task completed successfully
INFO - Parsed 5 utterances from ASR result
```

**COS 未配置（使用占位数据）：**
```
WARNING - COS not configured, using placeholder data: ./data/audio/...
INFO - To enable real ASR processing, configure COS settings in backend/config/settings.py
```

## 注意事项

1. **费用说明**：
   - COS 存储费用：约 0.118 元/GB/月
   - 外网下行流量：约 0.50 元/GB
   - 请求费用：读请求 0.01 元/万次
   - 详细价格：https://cloud.tencent.com/document/product/436/6239

2. **存储桶权限**：
   - 确保存储桶设置为"公有读"，否则腾讯云 ASR 无法访问音频文件

3. **地域选择**：
   - 建议 COS 地域与 ASR 服务地域相同，减少延迟和跨地域流量费用

4. **安全建议**：
   - 不要将 Secret ID 和 Secret Key 提交到 Git
   - 生产环境建议使用环境变量或密钥管理服务

## 常见问题

### Q: 为什么不能直接上传本地文件？
A: 腾讯云录音文件识别是异步 API，服务器需要在后台下载音频文件进行处理。本地文件路径无法被腾讯云服务器访问。

### Q: 有没有不用 COS 的方案？
A: 可以使用腾讯云"一句话识别" API（`SentenceRecognition`），支持直接上传音频内容（base64编码），但仅适用于 60 秒以内的短音频，且不支持说话人分离。

### Q: 音频文件会一直保存在 COS 吗？
A: 是的。如果需要自动清理，可以配置 COS 生命周期规则，自动删除 N 天前的文件。

### Q: 配置后还是显示占位数据？
A: 检查：
1. 配置是否正确填写（存储桶名称、地域）
2. 存储桶权限是否为"公有读"
3. 后端是否重启
4. 查看后端日志的详细错误信息
