# 运行与维护

## 本地体验

默认只监听 `127.0.0.1`，因此 `http://本机局域网IP:8787` 默认无法访问。新数据库自动创建 `admin / 123`，已有账号不会被覆盖或重置。可以使用左下角修改密码入口更改密码，之后全部登录会失效。

## 局域网访问

体验账号不能随服务暴露到局域网。若通过 HTTPS 反向代理访问，先在 `.env` 设置：

```dotenv
AGENT_HOST=0.0.0.0
AGENT_PORT=8787
AGENT_DEMO_ACCOUNT=false
AGENT_DEPLOYMENT_MODE=production
AGENT_SECURE_COOKIE=true
```

然后创建管理员账号并启动：

```powershell
uv run python -m app --create-user admin --admin
uv run python -m app
```

生产模式必须通过 HTTPS 访问，例如 `https://你的域名`。`AGENT_SECURE_COOKIE=true` 时，直接使用 `http://192.168.x.x:8787` 会导致登录后的会话 Cookie 不会被浏览器发送，随后 `/api/threads`、`/api/skills` 等接口会返回 `401`。

如果只是可信局域网内临时测试、暂时没有 HTTPS，可使用开发配置：

```dotenv
AGENT_HOST=0.0.0.0
AGENT_PORT=8787
AGENT_DEMO_ACCOUNT=false
AGENT_DEPLOYMENT_MODE=development
AGENT_SECURE_COOKIE=false
```

然后在同一局域网的设备上打开 `http://这台电脑的局域网IP:8787`。Windows 防火墙还必须允许 TCP `8787` 入站；可以使用 `ipconfig` 查看本机 IPv4 地址。改完 `.env` 后必须重启后端，并清除浏览器中该 IP 的旧 Cookie 后重新登录。若只想临时指定地址，也可以使用 `uv run python -m app --host 0.0.0.0 --port 8787`，但 `AGENT_SECURE_COOKIE` 必须与实际访问协议匹配。

需要其他账号时，在项目根目录运行，密码通过交互输入，不写入命令行：

```sh
uv run python -m app --create-user developer
uv run python -m app --create-user another-admin --admin
```

## 正式运行

1. 创建独立管理账号或修改默认密码。
2. 设置 `AGENT_DEMO_ACCOUNT=false`、`AGENT_DEPLOYMENT_MODE=production`、`AGENT_SECURE_COOKIE=true`。
3. 配置 HTTPS、反向代理和进程管理。
4. 反向代理保留同源 Cookie 和 SSE 流，避免缓冲流式响应；设置上传大小、连接数和请求速率限制。
5. 使用单个 API 进程，不能直接扩为多个 Worker。需要多实例时由开发者接入共享队列、分布式锁和数据库。

默认体验账号启用时，命令入口会拒绝监听非本机地址。不要通过另一个服务入口绕过该约束，也不要将未修改的默认密码用于公开服务。
正式模式还会拒绝使用仍保留 `admin / 123` 的数据库，避免仅关闭体验账号开关后误用旧密码。

## 数据

`data/agent.sqlite` 存放账号哈希、登录会话、对话、任务事件和附件；`data/history.sqlite` 存放 SDK 模型与工具历史。文件在磁盘数据库内保存，不会永久常驻内存。数据库、日志、导出文件和 `.env` 都不随源码交付。

删除对话会删除其消息、任务事件、附件和 SDK 会话；正在执行的任务必须先停止。使用方需要设置磁盘备份、保留周期及容量告警，定期检查 `data/`，不要在服务运行时直接删除数据库。

## 边界

- 模型、联网、第三方 MCP 都可能产生费用，使用方应设置服务预算并监控用量。
- SDK 轮数、请求超时和并发限制仍保留；没有额外的整任务总时长限制。
- 默认不自动重试付费请求。服务重启将未结束任务标为中断，不静默重复执行工具。
- 技能导入是说明文档导入，不承诺任意外部技能所需的软件都已安装。
- MCP stdio 不是沙箱，服务继承运行进程权限，应使用受限操作系统账号。
- 当前 Word 预览采用文字提取，不还原复杂版式；PDF 依赖浏览器自带阅读器；HTML 禁止脚本和外部资源；扫描 PDF 不含 OCR。
- 使用视觉模型需要开启配置；未启用时发送图片会明确拒绝，不会假装已经分析参考图。
- 模型输出需要根据使用场景核验，第三方服务的可用性由相应服务方保障。
