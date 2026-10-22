# 导入 GEOFlow MCP

`mcp.json` 已包含名为 `geoflow` 的 stdio 连接器，通过
`scripts/geoflow_mcp.py` 在 GEOFlow 项目目录启动 Laravel Boost MCP。

首次使用前，在 `agent-framework/.env` 中确认：

```dotenv
GEOFLOW_ROOT=D:\\Desktop\\各项目文件\\aicode\\GEOflow-zzr
GEOFLOW_PHP=php
```

如果 PHP 不在 PATH 中，把 `GEOFLOW_PHP` 改为 php.exe 的绝对路径。启动服务后，
管理员在 MCP 页面测试连接即可看到 GEOFlow 工具。

如果 GEOFlow 运行在已有的 Docker 容器中，无需在 Windows 安装 PHP。在 `.env` 中设置
`GEOFLOW_DOCKER_CONTAINER=geoflow-app`，并在连接器的 `env` 中增加
`"GEOFLOW_DOCKER_CONTAINER": "${GEOFLOW_DOCKER_CONTAINER}"`。
脚本通过 `docker exec -i` 转发 MCP 标准输入输出；容器必须已启动，后端进程必须有 Docker 访问权限。
配置容器后优先使用容器中的 PHP、项目目录和依赖；未配置时使用本机 PHP。
修改 `.env` 后应重启后端，使已存在的进程环境同步更新。

Laravel Boost 默认只在 local 环境或 debug 模式下注册。若容器中提示不存在 `boost` 命令，
可在 `.env` 设置 `GEOFLOW_ARTISAN_ENV=local`，并在连接器 `env` 中增加
`"GEOFLOW_ARTISAN_ENV": "${GEOFLOW_ARTISAN_ENV}"`。
这会为 MCP 的 Artisan 子进程添加 `--env=local`，不修改网站或容器的全局环境配置。
Boost 是开发工具服务，工具权限继承该子进程对 GEOFlow 的访问权限。

该连接继承智能体-framework 进程的用户权限。GEOFlow 鉴权与 Laravel Boost 工具限制
仍然有效；不要把 .env 或 API 密钥写入 mcp.json。
