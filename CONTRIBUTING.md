# 贡献指南

感谢你对 **Info-Tech 家庭情绪交互系统** 的关注！我们欢迎所有形式的贡献。

## 如何贡献

### 报告 Bug

如果你发现了 bug，请：

1. 在 [Issues](https://github.com/Info-Tech-org/info-tech/issues) 中查看是否已有相关报告
2. 若无，请新建 Issue，包含：
   - 清晰的标题和描述
   - 重现步骤
   - 期望行为 vs 实际行为
   - 环境信息（Python/Node 版本、操作系统等）
   - 相关日志或错误信息

### 提出新功能

如有功能建议：

1. 新建 Issue，标签选择 `enhancement`
2. 描述使用场景和价值
3. 如可能，提供实现思路或接口设计

### 提交代码

1. **Fork 本仓库**
   ```bash
   # 克隆你 fork 后的仓库
   git clone https://github.com/YOUR_USERNAME/info-tech.git
   cd info-tech
   ```

2. **创建特性分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或 fix/your-bugfix-name
   ```

3. **进行修改**
   - 遵循下方代码风格
   - 添加必要测试
   - 更新相关文档（API/协议变更需同步更新 `docs/` 与 README）

4. **提交**
   ```bash
   git add .
   git commit -m "feat: add your feature"
   ```

5. **推送到 GitHub 并创建 Pull Request**
   - 提供清晰的 PR 描述
   - 关联相关 Issue
   - 若涉及 UI，请附截图

## 代码风格

### Python

- 遵循 [PEP 8](https://pep8.org/)
- 4 空格缩进
- 函数/方法：`snake_case`；类：`PascalCase`；常量：`UPPER_CASE`
- 建议使用类型注解和 docstring（Google 风格）

### JavaScript / TypeScript

- 使用项目现有风格（ESLint/Prettier 若已配置）
- 组件与文件名：PascalCase 或 kebab-case 与现有一致

## 提交信息规范

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `style:` 代码格式（不影响行为）
- `refactor:` 重构
- `test:` 测试
- `chore:` 构建/工具变动

示例：

```
feat: add browser extension for live caption
fix: handle WebSocket reconnect in ingest
docs: add wearable bridge guide
```

## 文档与协议

- **API / 协议**：变更时请更新
  - 后端 API：`backend/` 内 docstring 及 `docs/` 中相关说明
  - PCM 上传：`info-tech/docs/PCM_INGEST_API.md`、`info-tech/docs/WS_PCM_STREAMING_PROTOCOL_v1.0.md`
  - BLE 绑定：`info-tech/docs/BLE_BINDING_PROTOCOL.md`
- **证据类文档**：`docs/EVIDENCE_*.md` 为交付/验证记录，功能变更可酌情更新或新增

## 安全

- **切勿**提交真实密码、密钥或敏感配置
- 新功能需考虑安全影响
- 安全问题请私下联系维护者，勿在公开 Issue 中披露

## 行为准则

- 尊重不同观点与经验
- 接受建设性批评
- 关注对社区最有利的决策
- 对其他参与者保持友善与同理心

## 需要帮助？

- **官网**：[https://infotech-launch.vercel.app/](https://infotech-launch.vercel.app/)
- 查看 [README.md](README.md) 了解项目结构与快速开始
- 查看 [Issues](https://github.com/Info-Tech-org/info-tech/issues) 与现有讨论
- 协议与架构见 `docs/` 与 `info-tech/docs/`

感谢你的贡献！
