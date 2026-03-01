# 生产服务器 SSH 验证证据

**服务器**: ubuntu@43.142.49.126  
**执行时间**: （请填写）  
**执行人**: 本机

---

## 1️⃣ 基本确认

```
(执行 whoami / hostname / pwd 的输出)
```

---

## 2️⃣ 后端健康检查

### HTTP 头
```
(curl -sS -D - http://127.0.0.1:9000/api/health 的输出)
```

### 响应体
```
(curl -sS http://127.0.0.1:9000/api/health 的输出)
```

---

## 3️⃣ Docker 状态

```
(sudo docker ps --format "table ..." 的输出)
```

---

## 4️⃣ Backend 最近日志

```
(sudo docker logs ... --tail 200 的输出)
```

---

## 5️⃣ Ingest Token（打码）

```
(DEVICE_INGEST_TOKEN 的值，中间6位用 ****** 替代)
```

---

## 备注

- 无 rebuild / 无改文件 / 无重启容器 / 无上传代码
- 仅执行只读验证命令
