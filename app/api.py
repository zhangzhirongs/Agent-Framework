import asyncio
import json
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from urllib.parse import quote, urlsplit

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.config import ROOT, Settings
from app.files import extract_text, save_file
from app.runtime import Runtime
from app.skills import MAX_BYTES
from app.store import HASHER, Store, digest, new_id

COOKIE = "agent_session"


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)


class PasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=500)


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(default="", max_length=32000)
    file_ids: list[str] = Field(default_factory=list, max_length=8)
    skills: list[str] = Field(default_factory=list, max_length=4)


class MCPInput(BaseModel):
    mcpServers: dict


def create_app(settings=None, model=None):
    settings = settings or Settings()
    store = Store(settings.data_dir)
    if settings.demo_account:
        store.bootstrap_demo()
    if settings.deployment_mode == "production":
        from argon2.exceptions import VerificationError

        for account in store.query("SELECT password_hash FROM users WHERE username='admin'"):
            try:
                weak = HASHER.verify(account["password_hash"], "123")
            except VerificationError:
                weak = False
            if weak:
                raise ValueError("正式运行前必须修改默认 admin 密码")
    runtime = Runtime(settings, store, model=model)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await runtime.close()

    app = FastAPI(title="智能体", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.runtime = store, runtime

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(KeyError)
    async def missing(request, error):
        return JSONResponse({"detail": "资源不存在或没有权限"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({"detail": "请求无效，请检查文件或配置内容"}, status_code=422)

    def same_origin(request):
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "不允许跨站请求")
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.url.netloc:
            raise HTTPException(403, "不允许跨站请求")

    def authenticated(request: Request):
        same_origin(request)
        user = store.session(request.cookies.get(COOKIE))
        if not user:
            raise HTTPException(401, "请先登录")
        if request.method not in ("GET", "HEAD", "OPTIONS") and not secrets.compare_digest(
            user["csrf"], request.headers.get("X-CSRF-Token", "")
        ):
            raise HTTPException(403, "会话校验失败，请刷新")
        return user

    def administrator(user=Depends(authenticated)):
        if not user["is_admin"]:
            raise HTTPException(403, "此操作仅限管理员")
        return user

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/api/auth/login")
    def login(body: LoginInput, request: Request, response: Response):
        same_origin(request)
        try:
            token, profile = store.login(
                body.username, body.password, request.client.host if request.client else "unknown"
            )
        except PermissionError:
            raise HTTPException(429, "登录尝试过多，请稍后重试") from None
        except ValueError:
            raise HTTPException(401, "账号或密码错误") from None
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            secure=settings.secure_cookie,
            samesite="lax",
            max_age=43200,
            path="/",
        )
        return profile

    @app.get("/api/auth/me")
    def profile(user=Depends(authenticated)):
        return {
            "id": user["id"],
            "username": user["username"],
            "is_admin": bool(user["is_admin"]),
            "csrf_token": user["csrf"],
        }

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, user=Depends(authenticated)):
        with store.connect() as db:
            db.execute("DELETE FROM sessions WHERE token=?", (digest(request.cookies[COOKIE]),))
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.post("/api/auth/password")
    async def change_password(body: PasswordInput, response: Response, user=Depends(authenticated)):
        from argon2.exceptions import VerificationError

        row = store.query("SELECT password_hash FROM users WHERE id=?", (user["id"],))[0]
        try:
            HASHER.verify(row["password_hash"], body.current_password)
        except VerificationError:
            raise HTTPException(403, "原密码错误") from None
        hashed = HASHER.hash(body.new_password)
        with store.connect() as db:
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed, user["id"]))
            db.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
        active = store.query(
            "SELECT r.id FROM runs r JOIN threads t ON t.id=r.thread_id "
            "WHERE t.user_id=? AND r.status IN ('queued','running')",
            (user["id"],),
        )
        for run in active:
            if task := runtime.tasks.get(run["id"]):
                task.cancel()
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.get("/api/capabilities")
    def capabilities(user=Depends(authenticated)):
        return {
            "model_ready": runtime.model is not None,
            "vision": settings.vision_enabled,
            "search": settings.search_provider != "none",
            "demo": settings.demo_account,
            "max_upload_mb": settings.max_upload_mb,
        }

    @app.get("/api/threads")
    def threads(user=Depends(authenticated)):
        return store.query(
            "SELECT * FROM threads WHERE user_id=? ORDER BY created DESC,id DESC", (user["id"],)
        )

    @app.post("/api/threads", status_code=201)
    def create_thread(user=Depends(authenticated)):
        item = {"id": new_id(), "title": "新对话", "created": time.time()}
        with store.connect() as db:
            db.execute(
                "INSERT INTO threads VALUES(?,?,?,?)",
                (item["id"], user["id"], item["title"], item["created"]),
            )
        return item

    @app.get("/api/threads/{thread_id}")
    def thread_detail(thread_id: str, user=Depends(authenticated)):
        thread = store.own_thread(user["id"], thread_id)
        messages = store.query(
            "SELECT * FROM messages WHERE thread_id=? ORDER BY created,rowid", (thread_id,)
        )
        for item in messages:
            item["file_ids"] = json.loads(item["file_ids"])
            item["skills"] = json.loads(item["skills"])
        files = store.query(
            "SELECT id,name,media_type,created FROM files WHERE thread_id=?", (thread_id,)
        )
        runs = store.query(
            "SELECT * FROM runs WHERE thread_id=? ORDER BY created DESC", (thread_id,)
        )
        return {"thread": thread, "messages": messages, "files": files, "runs": runs}

    @app.delete("/api/threads/{thread_id}")
    async def delete_thread(thread_id: str, user=Depends(authenticated)):
        store.own_thread(user["id"], thread_id)
        if store.query(
            "SELECT 1 FROM runs WHERE thread_id=? AND status IN ('queued','running')", (thread_id,)
        ):
            raise HTTPException(409, "请先停止正在执行的任务")
        from agents import SQLiteSession

        await SQLiteSession(thread_id, settings.data_dir / "history.sqlite").clear_session()
        with store.connect() as db:
            db.execute(
                "DELETE FROM events WHERE run_id IN (SELECT id FROM runs WHERE thread_id=?)",
                (thread_id,),
            )
            for table in ("files", "messages", "runs", "threads"):
                field = "id" if table == "threads" else "thread_id"
                db.execute(f"DELETE FROM {table} WHERE {field}=?", (thread_id,))
        return {"ok": True}

    @app.post("/api/threads/{thread_id}/messages", status_code=202)
    async def send_message(thread_id: str, body: MessageInput, user=Depends(authenticated)):
        store.own_thread(user["id"], thread_id)
        if not body.content.strip() and not body.file_ids:
            raise HTTPException(422, "请输入内容或上传文件")
        if runtime.model is None:
            raise HTTPException(503, "请先在 .env 配置模型地址、模型名称和密钥并重启服务")
        if len(runtime.tasks) >= settings.max_concurrent_runs:
            raise HTTPException(429, "服务繁忙，请稍后重试")
        if store.query(
            "SELECT 1 FROM runs r JOIN threads t ON t.id=r.thread_id WHERE t.user_id=? "
            "AND r.status IN ('queued','running')",
            (user["id"],),
        ):
            raise HTTPException(409, "请等待当前任务完成或先停止任务")
        known = {item["name"] for item in runtime.skills.catalog()}
        if not set(body.skills) <= known or len(body.skills) != len(set(body.skills)):
            raise HTTPException(422, "所选技能已不可用")
        files = [store.file(thread_id, key) for key in dict.fromkeys(body.file_ids)]
        if any(f["media_type"].startswith("image/") for f in files) and not settings.vision_enabled:
            raise HTTPException(422, "当前模型未启用视觉，请配置 AGENT_VISION_ENABLED 后再发送图片")
        prompt = body.content.strip() or "请分析这些附件"
        run = {"id": new_id(), "thread_id": thread_id, "status": "queued", "created": time.time()}
        try:
            with store.connect() as db:
                db.execute(
                    "INSERT INTO runs(id,thread_id,status,created) VALUES(?,?,?,?)",
                    (run["id"], thread_id, "queued", run["created"]),
                )
                store.add_message(
                    thread_id, "user", prompt, body.file_ids, body.skills, connection=db
                )
                db.execute(
                    "UPDATE threads SET title=? WHERE id=? AND title='新对话'",
                    (prompt[:32], thread_id),
                )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "此对话已有任务正在执行") from None
        runtime.start(run, prompt, files, body.skills)
        return run

    def own_run(user_id, run_id):
        rows = store.query(
            "SELECT r.* FROM runs r JOIN threads t ON t.id=r.thread_id "
            "WHERE r.id=? AND t.user_id=?",
            (run_id, user_id),
        )
        if not rows:
            raise KeyError("任务不存在")
        return rows[0]

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str, user=Depends(authenticated)):
        own_run(user["id"], run_id)
        task = runtime.tasks.get(run_id)
        if task:
            task.cancel()
        return {"ok": True}

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str, request: Request, after: int = 0, user=Depends(authenticated)):
        own_run(user["id"], run_id)
        try:
            cursor = max(after, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise HTTPException(422, "事件游标无效") from None

        async def stream():
            nonlocal cursor
            ticks = 0
            while not await request.is_disconnected():
                if not store.session(request.cookies.get(COOKIE)):
                    return
                rows = store.query(
                    "SELECT * FROM events WHERE run_id=? AND id>? ORDER BY id LIMIT 100",
                    (run_id, cursor),
                )
                for row in rows:
                    cursor = row["id"]
                    yield f"id: {cursor}\nevent: {row['kind']}\ndata: {row['payload']}\n\n"
                run = own_run(user["id"], run_id)
                if run["status"] not in ("queued", "running"):
                    if rows and rows[-1]["kind"] == "done":
                        return
                    if not rows:
                        yield (
                            "event: done\ndata: "
                            + json.dumps({"status": run["status"], "error": run["error"]})
                            + "\n\n"
                        )
                        return
                ticks += 1
                if ticks % 40 == 0:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.25)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    @app.post("/api/threads/{thread_id}/files", status_code=201)
    async def upload(thread_id: str, file: UploadFile = File(), user=Depends(authenticated)):
        store.own_thread(user["id"], thread_id)
        limit = settings.max_upload_mb * 1024 * 1024
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise HTTPException(413, "文件超过大小限制")
        return save_file(store, thread_id, file.filename or "file.txt", content)

    def own_file(user_id, file_id):
        rows = store.query(
            "SELECT f.* FROM files f JOIN threads t ON t.id=f.thread_id "
            "WHERE f.id=? AND t.user_id=?",
            (file_id, user_id),
        )
        if not rows:
            raise KeyError("文件不存在")
        return rows[0]

    @app.get("/api/files/{file_id}/text")
    def file_text(file_id: str, user=Depends(authenticated)):
        return {"text": extract_text(own_file(user["id"], file_id))}

    @app.get("/api/files/{file_id}")
    def download(file_id: str, preview: bool = False, user=Depends(authenticated)):
        item = own_file(user["id"], file_id)
        disposition = "inline" if preview else "attachment"
        headers = {"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(item['name'])}"}
        if item["media_type"] in ("text/html", "application/xhtml+xml"):
            headers["Content-Security-Policy"] = (
                "sandbox; default-src 'none'; style-src 'unsafe-inline'"
            )
        return Response(item["content"], media_type=item["media_type"], headers=headers)

    @app.get("/api/skills")
    def skills(user=Depends(authenticated)):
        return runtime.skills.catalog()

    @app.get("/api/skills/{name}")
    def skill(name: str, user=Depends(authenticated)):
        return runtime.skills.detail(name)

    @app.post("/api/skills/import", status_code=201)
    async def import_skill(files: list[UploadFile] = File(), user=Depends(administrator)):
        if len(files) > 300:
            raise HTTPException(413, "技能文件数量过多")
        total, entries = 0, []
        for file in files:
            content = await file.read(MAX_BYTES - total + 1)
            total += len(content)
            if total > MAX_BYTES:
                raise HTTPException(413, "技能总大小超过 20 MB")
            entries.append((file.filename or "SKILL.md", content))
        if len(entries) == 1 and entries[0][0].lower().endswith(".zip"):
            import zipfile

            try:
                return runtime.skills.install_zip(entries[0][1])
            except zipfile.BadZipFile:
                raise HTTPException(422, "技能压缩包无效") from None
        return runtime.skills.install(entries)

    @app.delete("/api/skills/{name}")
    def remove_skill(name: str, user=Depends(administrator)):
        if runtime.tasks:
            raise HTTPException(409, "请等待当前任务完成后再移除技能")
        runtime.skills.remove(name)
        return {"ok": True}

    @app.get("/api/connectors")
    def connectors(user=Depends(authenticated)):
        return [
            {
                "name": name,
                "enabled": config.get("enabled", True),
                "transport": "stdio"
                if config.get("command")
                else config.get("type", "streamable_http"),
            }
            for name, config in runtime.connectors.configs().items()
        ]

    @app.get("/api/connectors/config")
    def connector_config(user=Depends(administrator)):
        return {"mcpServers": runtime.connectors.configs()}

    @app.put("/api/connectors/config")
    def save_connectors(body: MCPInput, user=Depends(administrator)):
        if runtime.tasks:
            raise HTTPException(409, "请等待当前任务完成后再修改 MCP")
        runtime.connectors.save(body.mcpServers)
        return {"ok": True}

    @app.post("/api/connectors/test")
    async def test_connectors(user=Depends(administrator)):
        try:
            async with runtime.connectors.connect() as servers:
                tools = [
                    {
                        "name": server.name,
                        "tools": [tool.name for tool in await server.list_tools()],
                    }
                    for server in servers
                ]
            return {"ok": True, "servers": tools}
        except Exception:
            raise HTTPException(502, "MCP 连接失败，请检查地址、依赖和环境变量") from None

    if (ROOT / "web" / "dist").is_dir():

        class ConsoleFiles(StaticFiles):
            async def get_response(self, path, scope):
                return await super().get_response("index.html" if path == "login" else path, scope)

        app.mount("/", ConsoleFiles(directory=ROOT / "web" / "dist", html=True))
    return app
