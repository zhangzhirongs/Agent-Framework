"""Forward MCP stdio to Laravel Boost using local PHP or an existing container."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def command(environment):
    artisan = ["artisan", "boost:mcp"]
    artisan_env = environment.get("GEOFLOW_ARTISAN_ENV", "")
    if artisan_env:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", artisan_env):
            raise ValueError("GEOFLOW_ARTISAN_ENV 不是有效的环境名称")
        artisan.append(f"--env={artisan_env}")
    container = environment.get("GEOFLOW_DOCKER_CONTAINER", "")
    if container:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", container):
            raise ValueError("GEOFLOW_DOCKER_CONTAINER 不是有效的容器名称")
        docker = shutil.which("docker")
        if not docker:
            raise ValueError("找不到 Docker，请安装 Docker 或配置本机 GEOFLOW_PHP")
        return [docker, "exec", "-i", container, "php", *artisan], None

    root = Path(environment.get("GEOFLOW_ROOT", "")).expanduser()
    if not environment.get("GEOFLOW_ROOT") or not (root / "artisan").is_file():
        raise ValueError("GEOFLOW_ROOT 必须指向包含 artisan 的 GEOFlow 项目目录")
    if not (root / "vendor" / "autoload.php").is_file():
        raise ValueError("GEOFlow 缺少 Composer 依赖，请先安装项目依赖")
    php = shutil.which(environment.get("GEOFLOW_PHP", "php"))
    if not php:
        raise ValueError("找不到 PHP，请设置 GEOFLOW_PHP 绝对路径或 GEOFLOW_DOCKER_CONTAINER")
    return [php, *artisan], str(root)


def main():
    try:
        args, cwd = command(os.environ)
        # Keep stdout exclusively for the MCP protocol. Never allocate a Docker TTY.
        return subprocess.call(args, cwd=cwd)
    except (ValueError, OSError) as error:
        print(f"GEOFlow MCP 启动失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
