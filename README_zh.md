# Dialog-OS（语镜）— 中文说明

本文档为中文简要说明，完整英文文档见 [README.md](README.md)。

---

<div align="center">

<div style="background:#2b2a24;padding:16px 24px;border-radius:12px;display:inline-block;">
  <a href="https://infotech-launch.vercel.app/"><img src="assert/1NF0TECH_LOGO.svg" alt="Info-Tech 语镜" width="280" /></a>
</div>

**语镜 · Dialog Safety Infra** — 家庭场景下的实时有害语检测与沟通改进平台

[官网](https://infotech-launch.vercel.app/) · [功能特性](README.md#features) · [快速开始](README.md#quick-start) · [架构](README.md#architecture)

</div>

---

## 简介

面向家庭沟通场景：**实时语音识别 + 有害语检测 + 智能反馈**，支持 ESP32、Web、浏览器扩展；检测管道为 **绝对关键词 → 语义向量召回 → LLM 筛选**。

## 快速开始

1. 克隆：`git clone https://github.com/Info-Tech-org/Dialog-OS.git`
2. 配置本地密钥：复制 `backend/.env.example` 为 `backend/.env` 并填入腾讯云 ASR、OpenRouter 等密钥；或运行 `python scripts/setup_local_env.py` 按提示填写。
3. 启动后端：`cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
4. 启动前端：`cd frontend && npm run dev`

详见 [README.md](README.md) 中的 Quick Start 与 Local development (secrets)。
