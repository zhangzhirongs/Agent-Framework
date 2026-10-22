import argparse
import getpass

import uvicorn
from dotenv import load_dotenv

from app.api import create_app
from app.config import ROOT, Settings
from app.store import Store


def main():
    parser = argparse.ArgumentParser(description="智能体开发框架")
    parser.add_argument("--host", help="监听地址；局域网访问可使用 0.0.0.0")
    parser.add_argument("--port", type=int, help="监听端口")
    parser.add_argument("--create-user", metavar="USERNAME")
    parser.add_argument("--admin", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    settings = Settings()
    host = args.host or settings.host
    port = args.port or settings.port
    if args.create_user:
        password = getpass.getpass("Password: ")
        if len(password) < 8:
            parser.error("请输入至少 8 位密码")
        if password != getpass.getpass("Confirm password: "):
            parser.error("两次密码不一致")
        Store(settings.data_dir).create_user(args.create_user, password, admin=args.admin)
        print("User created")
        return
    if settings.demo_account and host not in ("127.0.0.1", "localhost", "::1"):
        parser.error(
            "当前启用了默认体验账号，不能监听局域网；请先设置 "
            "AGENT_DEMO_ACCOUNT=false、AGENT_DEPLOYMENT_MODE=production、"
            "AGENT_SECURE_COOKIE=true，并创建至少 8 位的管理员账号"
        )
    uvicorn.run(create_app(settings), host=host, port=port, workers=1)


if __name__ == "__main__":
    main()
