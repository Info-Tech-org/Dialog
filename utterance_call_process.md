# 会话记录调用过程

目标：获取会话 `69239859-c9ec-4dbc-a5d4-68444795628e` 的完整对话记录（utterances）。

## 1) 调用 API

命令：
```bash
curl.exe -sS "http://47.236.106.225:9000/api/sessions/69239859-c9ec-4dbc-a5d4-68444795628e"
```

## 2) 关键返回字段

响应中包含以下关键字段（节选）：
```json
{
  "session_id": "69239859-c9ec-4dbc-a5d4-68444795628e",
  "device_id": "web_upload",
  "start_time": "2025-12-06T06:12:09.508671",
  "end_time": "2025-12-06T06:12:17.227547",
  "audio_url": "http://47.236.106.225:9000/media/69239859-c9ec-4dbc-a5d4-68444795628e_20251206_061209.mp3",
  "harmful_count": 5,
  "duration_seconds": 7.718876,
  "utterances": [
    {
      "speaker": "A",
      "start": 0.0,
      "end": 2.445,
      "text": "就倒了吗？他他也。",
      "harmful_flag": false
    },
    {
      "speaker": "B",
      "start": 2.445,
      "end": 6.33,
      "text": "没动，来来来来，这是什么物业？看一下鸡巴物业是什么？",
      "harmful_flag": false
    },
    {
      "speaker": "A",
      "start": 6.33,
      "end": 7.67,
      "text": "物业，鸡巴物业。",
      "harmful_flag": false
    },
    {
      "speaker": "B",
      "start": 7.67,
      "end": 9.5,
      "text": "鸡巴物业骂的真他妈。",
      "harmful_flag": false
    },
    {
      "speaker": "A",
      "start": 9.5,
      "end": 15.375,
      "text": "鸡妈的操你妈，鸡巴操你妈，鸡巴巴操你妈，鸡巴操你妈，操你妈，你你妈。",
      "harmful_flag": true
    },
    {
      "speaker": "C",
      "start": 15.375,
      "end": 22.5,
      "text": "操你妈，操操，操你妈，操你妈，操你妈，操你妈。",
      "harmful_flag": true
    },
    {
      "speaker": "B",
      "start": 24.5,
      "end": 28.5,
      "text": "来，再来一句，操你妈新年好啊。",
      "harmful_flag": true
    },
    {
      "speaker": "C",
      "start": 28.5,
      "end": 30.5,
      "text": "新年好，操你妈。",
      "harmful_flag": true
    },
    {
      "speaker": "D",
      "start": 30.5,
      "end": 38.415,
      "text": "你妈了个逼的，沈阳快解放了吧，操你妈的沈阳快解放了都子啊，抽人全麦视。",
      "harmful_flag": true
    },
    {
      "speaker": "E",
      "start": 38.415,
      "end": 44.5,
      "text": "谁啊？你们这帮小逼崽子认不认识我啊？我是神鹰哥，敢不敢跟我比划比划？",
      "harmful_flag": false
    }
  ]
}
```

## 3) 结果说明

- 会话详情已成功返回，包含 `utterances` 数组。
- 记录包含多 speaker（A/B/C/D/E）以及 harmful 标记。


