import io
import zipfile

import pytest

from app.config import Settings
from app.skills import Skills
from tests.conftest import browser, login


async def test_auth_csrf_and_user_file_isolation(platform):
    app, _ = platform
    app.state.store.create_user("member", "member-test-password")
    async with browser(app) as admin, browser(app) as member, browser(app) as anonymous:
        assert (await anonymous.get("/api/threads")).status_code == 401
        await login(admin)
        await login(member, "member", "member-test-password")
        assert (await admin.post("/api/threads", headers={"X-CSRF-Token": ""})).status_code == 403
        assert (
            await admin.get("/api/threads", headers={"Origin": "https://foreign.example"})
        ).status_code == 403
        thread = (await admin.post("/api/threads")).json()["id"]
        file = (
            await admin.post(
                f"/api/threads/{thread}/files", files={"file": ("note.txt", b"private")}
            )
        ).json()
        assert (await member.get(f"/api/threads/{thread}")).status_code == 404
        assert (await member.get(f"/api/files/{file['id']}")).status_code == 404
        assert (await member.get("/api/connectors/config")).status_code == 403
        assert (
            await member.put("/api/connectors/config", json={"mcpServers": {}})
        ).status_code == 403
        assert (
            await member.post("/api/skills/import", files={"files": ("SKILL.md", b"bad")})
        ).status_code == 403
        assert (await admin.get(f"/api/files/{file['id']}/text")).json() == {"text": "private"}


async def test_password_change_revokes_sessions_and_demo_is_not_reset(platform, settings):
    app, _ = platform
    async with browser(app) as client, browser(app) as other:
        await login(client)
        await login(other)
        response = await client.post(
            "/api/auth/password",
            json={"current_password": "123", "new_password": "updated-test-password"},
        )
        assert response.status_code == 200
        assert (await other.get("/api/auth/me")).status_code == 401
        app.state.store.bootstrap_demo()
        assert (
            await client.post("/api/auth/login", json={"username": "admin", "password": "123"})
        ).status_code == 401
        await login(client, password="updated-test-password")


async def test_html_preview_is_sandboxed_and_file_types_are_checked(platform):
    app, _ = platform
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        invalid = await client.post(
            f"/api/threads/{thread}/files", files={"file": ("app.exe", b"invalid")}
        )
        assert invalid.status_code == 422
        invalid_image = await client.post(
            f"/api/threads/{thread}/files", files={"file": ("image.png", b"not an image")}
        )
        assert invalid_image.status_code == 422
        html = (
            await client.post(
                f"/api/threads/{thread}/files",
                files={"file": ("index.html", b"<h1>Hi</h1><script>alert(1)</script>")},
            )
        ).json()
        preview = await client.get(f"/api/files/{html['id']}?preview=true")
        assert "sandbox" in preview.headers["content-security-policy"]
        assert preview.headers["x-content-type-options"] == "nosniff"


async def test_docx_rich_preview_preserves_headings_runs_and_tables(platform):
    import io

    from docx import Document

    from tests.conftest import browser, login

    app, _ = platform
    document = Document()
    document.add_heading("Quarterly report", level=1)
    paragraph = document.add_paragraph()
    paragraph.add_run("Important").bold = True
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Metric"
    table.rows[0].cells[1].text = "Value"
    output = io.BytesIO()
    document.save(output)

    async with browser(app) as client:
        await login(client)
        thread = await client.post("/api/threads")
        uploaded = await client.post(
            f"/api/threads/{thread.json()['id']}/files",
            files={
                "file": (
                    "report.docx",
                    output.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        preview = await client.get(f"/api/files/{uploaded.json()['id']}/preview")

    assert preview.status_code == 200
    assert "<h1" in preview.json()["html"]
    assert "<strong>Important</strong>" in preview.json()["html"]
    assert "<table>" in preview.json()["html"]


def test_production_forbids_demo_password_and_requires_secure_cookie():
    with pytest.raises(ValueError):
        Settings(_env_file=None, deployment_mode="production")
    Settings(_env_file=None, deployment_mode="production", demo_account=False, secure_cookie=True)


async def test_production_rejects_an_existing_default_password(settings):
    from app.api import create_app
    from app.store import Store

    store = Store(settings.data_dir)
    store.bootstrap_demo()
    settings.deployment_mode = "production"
    settings.demo_account = False
    settings.secure_cookie = True
    with pytest.raises(ValueError, match="admin"):
        create_app(settings)


@pytest.mark.parametrize(
    "config",
    [
        {"url": 123},
        {"command": "example", "args": [123]},
        {"url": "https://example.test/mcp", "enabled": "false"},
        {"command": "example", "allowed_tools": "all"},
        {"command": "example", "env": {"KEY": "inline-secret"}},
    ],
)
def test_mcp_rejects_invalid_configuration_without_saving(tmp_path, config):
    from app.connectors import Connectors

    registry = Connectors(tmp_path / "mcp.json")
    with pytest.raises(ValueError):
        registry.save({"example": config})
    assert not registry.path.exists()


def test_skills_standard_format_resources_and_path_traversal(tmp_path):
    skills = Skills(tmp_path / "skills")
    content = (
        b"---\nname: sample\ndescription: sample description\nmetadata:\n"
        b"  author: Example Author\n---\nInstructions"
    )
    skills.install([("sample/SKILL.md", content), ("sample/references/note.md", b"resource")])
    assert skills.catalog()[0]["author"] == "Example Author"
    assert skills.resource("sample", "references/note.md") == "resource"
    assert skills.detail("sample")["resources"] == ["SKILL.md", "references/note.md"]
    with pytest.raises((KeyError, ValueError)):
        skills.resource("sample", "../../outside.txt")
    with pytest.raises(ValueError):
        skills.install([("../SKILL.md", content)])
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as zipped:
        zipped.writestr("../SKILL.md", content)
    with pytest.raises(ValueError):
        skills.install_zip(stream.getvalue())
    skills.remove("sample")
    assert skills.catalog() == []


async def test_unconfigured_model_fails_before_accepting_message(settings):
    from app.api import create_app

    app = create_app(settings)
    async with browser(app) as client:
        await login(client)
        thread = (await client.post("/api/threads")).json()["id"]
        response = await client.post(f"/api/threads/{thread}/messages", json={"content": "hello"})
        assert response.status_code == 503
        assert not app.state.store.query("SELECT * FROM runs")
    await app.state.runtime.close()
