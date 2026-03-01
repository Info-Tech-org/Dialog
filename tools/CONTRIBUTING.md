# Tools 目录说明

本目录包含与 Info-Tech 主项目配套的脚本与工具（如测试脚本、远程执行器等）。  
**主项目的贡献指南请参见仓库根目录的 [CONTRIBUTING.md](../CONTRIBUTING.md)。**

以下为通用的贡献流程参考（若本目录下有独立子项目如 remote-executor，可沿用此规范）。

## 如何贡献

### 报告 Bug

如果你发现了 bug，请：

1. 检查 [Issues](https://github.com/your-username/remote-executor/issues) 看是否已有相关报告
2. 如果没有，创建一个新的 Issue，包含：
   - 清晰的标题和描述
   - 重现步骤
   - 期望行为 vs 实际行为
   - 你的环境信息（Python 版本、操作系统等）
   - 相关的日志或错误信息

### 提出新功能

如果你有功能建议：

1. 创建一个 Issue，标签选择 "enhancement"
2. 描述功能的用例和价值
3. 如果可能，提供实现思路

### 提交代码

1. **Fork 项目**
   ```bash
   git clone https://github.com/your-username/remote-executor.git
   cd remote-executor
   ```

2. **创建特性分支**
   ```bash
   git checkout -b feature/my-awesome-feature
   ```

3. **进行修改**
   - 遵循代码风格（见下文）
   - 添加必要的测试
   - 更新相关文档

4. **测试你的更改**
   ```bash
   python remote_exec.py test
   ```

5. **提交更改**
   ```bash
   git add .
   git commit -m "feat: add awesome feature"
   ```

6. **推送到 GitHub**
   ```bash
   git push origin feature/my-awesome-feature
   ```

7. **创建 Pull Request**
   - 提供清晰的 PR 描述
   - 关联相关的 Issue
   - 等待代码审查

## 代码风格

### Python 风格指南

- 遵循 [PEP 8](https://pep8.org/)
- 使用 4 个空格缩进
- 函数和方法使用 snake_case
- 类使用 PascalCase
- 常量使用 UPPER_CASE

### 文档字符串

使用 Google 风格的 docstrings：

```python
def example_function(param1: str, param2: int) -> bool:
    """
    简短描述函数的作用。

    详细说明函数的行为和用途。

    Args:
        param1: 第一个参数的说明
        param2: 第二个参数的说明

    Returns:
        返回值的说明

    Raises:
        ValueError: 何时会抛出此异常
    """
    pass
```

### 提交信息规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `style:` 代码格式（不影响代码运行）
- `refactor:` 重构
- `test:` 添加或修改测试
- `chore:` 构建过程或辅助工具的变动

示例：
```
feat: add support for SOCKS5 proxy
fix: handle connection timeout correctly
docs: update README with proxy examples
```

## 安全注意事项

- **永远不要**提交包含真实密码、密钥或其他敏感信息的代码
- 确保新功能不会引入安全漏洞
- 如果发现安全问题，请私下联系维护者，不要公开 Issue

## 测试

在提交 PR 之前，请确保：

- [ ] 代码通过基本测试（`python remote_exec.py test`）
- [ ] 新功能有相应的使用示例
- [ ] 更新了 README 和其他相关文档
- [ ] 遵循了代码风格指南

## 审查流程

1. 维护者会审查你的 PR
2. 可能会要求修改
3. 通过审查后会被合并
4. 你的贡献会在 CHANGELOG 中被记录

## 行为准则

### 我们的承诺

为了营造一个开放和友好的环境，我们承诺：

- 尊重不同的观点和经验
- 优雅地接受建设性批评
- 关注对社区最有利的事情
- 对其他社区成员表示同理心

### 不可接受的行为

- 使用性化的语言或图像
- 人身攻击
- 公开或私下骚扰
- 未经许可发布他人的私人信息
- 其他不道德或不专业的行为

## 需要帮助？

- 查看 [Issues](https://github.com/your-username/remote-executor/issues)
- 阅读 [README.md](README.md)
- 加入我们的讨论

## 致谢

感谢所有贡献者！你们的努力让这个项目变得更好。

---

再次感谢你的贡献！
