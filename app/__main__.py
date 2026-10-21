import argparse
import getpass

import uvicorn
from dotenv import load_dotenv

from app.api import create_app
from app.config import ROOT, Settings
from app.store import Store


def main():
    parser = argparse.ArgumentParser(description="智能体开发框架")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--create-user", metavar="USERNAME")
    parser.add_argument("--admin", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    settings = Settings()
    if args.create_user:
        password = getpass.getpass("Password: ")
        if len(password) < 8:
            parser.error("请输入至少 8 位密码")
        if password != getpass.getpass("Confirm password: "):
            parser.error("两次密码不一致")
        Store(settings.data_dir).create_user(args.create_user, password, admin=args.admin)
        print("User created")
        return
    if settings.demo_account and args.host not in ("127.0.0.1", "localhost", "::1"):
        parser.error("默认体验账号仅允许本机访问；对外部署前请关闭 demo_account 并设置独立密码")
    uvicorn.run(create_app(settings), host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
