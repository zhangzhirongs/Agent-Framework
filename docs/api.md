# 接口

开发环境启动后，完整参数见 <http://127.0.0.1:8787/docs>。页面和接口使用同源 Cookie，不把模型密钥交给前端。

## 登录和对话

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/auth/login` | `{username,password}`，返回用户和 `csrf_token` |
| GET | `/api/auth/me` | 当前登录信息 |
| POST | `/api/auth/logout` | 注销当前登录 |
| POST | `/api/auth/password` | 修改密码、撤销现有登录 |
| GET | `/api/capabilities` | 配置是否就绪，不返回模型 ID、地址或密钥 |
| GET / POST | `/api/threads` | 列表 / 创建对话 |
| GET / DELETE | `/api/threads/{id}` | 消息、文件、任务 / 删除对话 |
| POST | `/api/threads/{id}/messages` | 发送消息，返回 202 和任务 ID |
| GET | `/api/runs/{id}/events` | SSE，支持 `after`、`Last-Event-ID` |
| POST | `/api/runs/{id}/cancel` | 停止任务 |

除登录外的写请求要求 `X-CSRF-Token`，值来自登录结果。所有对话、任务、附件均按登录用户校验所有权。

发送消息示例：

```json
{
  "content": "请整理这些资料",
  "file_ids": [],
  "skills": ["example-note"]
}
```

SSE 事件为 `delta`、`activity`、`done`。网络恢复后可从事件 ID 继续读取，服务器不会因为重连而再次发起模型请求。失败或服务重启时，不自动重发可能产生费用的任务。

## 附件与扩展

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/threads/{id}/files` | multipart `file` 上传 |
| GET | `/api/files/{id}` | 下载；`?preview=true` 内联预览 |
| GET | `/api/files/{id}/text` | 文本提取 |
| GET | `/api/skills` | 技能目录 |
| GET | `/api/skills/{name}` | 正文与资源目录 |
| POST | `/api/skills/import` | 管理员 multipart `files` 导入 |
| DELETE | `/api/skills/{name}` | 管理员移除技能 |
| GET | `/api/connectors` | 连接器概览 |
| GET / PUT | `/api/connectors/config` | 管理员查看 / 保存注册表 |
| POST | `/api/connectors/test` | 管理员主动连接测试 |

接口可用于单体项目集成，并在现有鉴权和所有权校验基础上扩展。
