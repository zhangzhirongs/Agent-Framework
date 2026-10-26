# 205 服务器部署

部署日期：2026-10-22。

- 访问地址：<https://192.168.169.205:18788>。
- 端口 `18788` 在部署前检查为空闲，仅监听服务器的局域网地址。
- 使用自签名 HTTPS 证书，有效期一年；浏览器首次访问会提示证书不受信任。
- 管理员用户名为 `admin`，随机密码保存在本地被 Git 忽略的 `.env.deploy` 的 `DEPLOY_ADMIN_PASSWORD` 中。
- 关闭体验账号，启用生产模式和 Secure 会话 Cookie。

## 服务与文件

服务以独立系统用户 `agent-framework` 运行，由 systemd 管理并开机自启。

```sh
systemctl status agent-framework
systemctl restart agent-framework
journalctl -u agent-framework -n 100 --no-pager
curl --cacert /opt/agent-framework/shared/tls/server.crt https://192.168.169.205:18788/health
```

| 用途 | 服务器路径 |
| --- | --- |
| 当前版本链接 | `/opt/agent-framework/current` |
| 本次发布 | `/opt/agent-framework/releases/20261022` |
| 服务配置 | `/etc/systemd/system/agent-framework.service` |
| 环境配置 | `/opt/agent-framework/shared/.env` |
| 持久化数据库 | `/opt/agent-framework/shared/data` |
| MCP 配置 | `/opt/agent-framework/shared/mcp.json` |
| TLS 证书和私钥 | `/opt/agent-framework/shared/tls` |
| Python 与 uv | `/opt/agent-framework/python`、`/opt/agent-framework/tools` |

环境配置和私钥仅允许服务账号读取。管理员初始化后，服务器环境配置中的初始明文密码已移除；数据库保存密码哈希。
后续更新前备份持久化数据和配置，并保留当前版本。技能目前保存在当前发布目录的 `skills` 中，更新时也应备份、迁移管理员导入的技能。

## GEOFlow MCP

205 使用的容器名是 `geoflow-app-prod`。检查时其未安装 Laravel Boost，未提供 `boost:mcp`，因此本次部署保留连接器配置并设置 `enabled: false`。
未修改已有 GEOFlow 容器及其他服务。后续需先准备提供 Boost 的 MCP 运行环境，并授予服务账号相应访问权限，再启用连接器。

## 验证

发布前通过 `uv run pytest -q`（36 项）、`uv run ruff check app tests scripts`、`web` 中的 `npm run build` 和 `npm test`（2 项）。

部署后从本机验证首页与健康检查、管理员登录、Secure Cookie、受保护接口、会话创建与删除、无 CSRF 请求被拒绝；模型配置显示已就绪。未发起付费模型调用。
MCP 测试在无已启用连接器时返回成功，不代表 GEOFlow MCP 已接通。
