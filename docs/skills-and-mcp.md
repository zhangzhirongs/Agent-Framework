# 技能与 MCP

## 技能标准

```text
skills/
  your-skill/
    SKILL.md
    references/
    scripts/
    assets/
```

只要求根目录有 `SKILL.md`，其余目录按技能需要提供，不再加分类目录。

```markdown
---
name: your-skill
description: 说明什么时候应该使用此技能，以及能帮助完成什么工作。
metadata:
  author: 作者或项目名称
---

# 技能说明

在这里编写步骤、约束和资源引用。
```

名称使用小写英文、数字和短横线，并与技能文件夹名称一致。作者从 `metadata.author` 或 `author` 读取；未声明时明确显示“未标注”。框架附带 `example-note` 示例，可按同一格式添加其他技能。

管理员可以在技能页面导入单个 `SKILL.md`、完整目录或一个技能 ZIP。一次最多 300 个文件、20 MB，总包必须包含根级 `SKILL.md`；压缩包可以带一层目录。同名技能不会被静默覆盖。路径穿越、隐藏文件和符号链接会被拒绝。

所有已安装技能可供本地平台用户使用。输入框加号菜单可选择本轮技能；智能体也能按任务自行调用 `load_skill`。发送成功后清空本轮选择；技能名称随用户消息保留。`read_skill_resource` 按需读取技能内 UTF-8 资源，`scripts/` 可保留但不会自动执行。

## MCP 标准

支持通用 `mcpServers` 对象，示例见根目录 `mcp.example.json`。默认注册表为空，不自动安装或连接第三方服务。

```json
{
  "mcpServers": {
    "your-server": {
      "type": "streamable_http",
      "url": "https://your-server.example/mcp",
      "headers": {"Authorization": "${YOUR_MCP_AUTHORIZATION}"},
      "allowed_tools": ["search"],
      "enabled": true
    }
  }
}
```

- stdio 使用 `command`、`args`、`env`。
- HTTP 使用 `type: streamable_http`，SSE 使用 `type: sse`。
- `allowed_tools` 限制可见工具；空数组不开放工具，省略时开放服务提供的全部工具。
- 管理员保存后可以手动测试连接，显示服务和工具名称。
- `env` 和 `headers` 必须引用环境变量，实际值不会出现在注册表中。
- 连接由任务创建和清理；任一已启用服务连接失败时，本次任务会报告异常，不假装已成功执行。

stdio 服务是本机程序，以后端进程用户的权限运行；MCP 不是自动沙箱。仅管理员可配置服务和导入技能。接入来源、工具副作用、第三方许可及费用需由部署者确认。

本地 MCP 示例可以配置 `command` 为本环境 Python 可执行文件，`args` 为 `examples/echo_mcp.py` 的路径，工具白名单为 `ping`。这只用于连通性测试，没有外部账号或业务信息。
