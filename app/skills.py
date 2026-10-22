"""Standard SKILL.md packages; packages are instructions, never auto-executed code."""

import io
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import yaml

NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_BYTES = 20 * 1024 * 1024
MAX_FILES = 300


def relative_path(value):
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or ".." in path.parts
        or ":" in value
        or any(p.startswith(".") for p in path.parts)
    ):
        raise ValueError("技能资源路径无效")
    return path


def metadata(text):
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    if not match:
        raise ValueError("SKILL.md 必须包含 YAML frontmatter")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict) or not NAME.fullmatch(str(data.get("name", ""))):
        raise ValueError("技能 name 需为小写字母、数字或短横线")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        raise ValueError("技能缺少 description")
    details = data.get("metadata")
    author = details.get("author", "") if isinstance(details, dict) else ""
    display_name = details.get("display_name", "") if isinstance(details, dict) else ""
    heading = re.search(r"^#\s+(.+)$", text[match.end():], re.M)
    if not isinstance(display_name, str) or not display_name.strip():
        display_name = heading.group(1).strip() if heading else data["name"]
    return {
        "name": data["name"],
        "display_name": display_name.strip()[:200],
        "description": data["description"][:2000],
        "author": str(author or data.get("author", "未标注"))[:200],
    }


class Skills:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    def path(self, name):
        if not NAME.fullmatch(name):
            raise KeyError("技能不存在")
        path = self.directory / name
        if path.is_symlink() or not (path / "SKILL.md").is_file():
            raise KeyError("技能不存在")
        return path

    def catalog(self):
        result = []
        for path in sorted(self.directory.iterdir()):
            if not path.is_dir() or path.is_symlink() or not NAME.fullmatch(path.name):
                continue
            try:
                item = metadata(self.resource(path.name, "SKILL.md"))
                if item["name"] != path.name:
                    continue
                result.append(item)
            except (ValueError, KeyError, UnicodeError, OSError, yaml.YAMLError):
                continue
        return result

    def resource(self, name, resource):
        root = self.path(name).resolve()
        relative = relative_path(resource)
        path = root / relative
        if (
            not path.resolve().is_relative_to(root)
            or any(part.is_symlink() for part in [path, *path.parents] if part != root)
            or not path.is_file()
            or path.stat().st_size > MAX_BYTES
        ):
            raise KeyError("资源不存在或无法读取")
        return path.read_text("utf-8")[:100000]

    def detail(self, name):
        root = self.path(name)
        item = metadata(self.resource(name, "SKILL.md"))
        item["content"] = self.resource(name, "SKILL.md")
        resources = [
            p.relative_to(root).as_posix()
            for p in root.rglob("*")
            if p.is_file()
            and not p.is_symlink()
            and not any(x.startswith(".") for x in p.relative_to(root).parts)
        ]
        item["resources"] = ["SKILL.md"] + sorted(
            resource for resource in resources if resource != "SKILL.md"
        )
        return item

    def install(self, files):
        if not files or len(files) > MAX_FILES or sum(len(b) for _, b in files) > MAX_BYTES:
            raise ValueError("每个技能最多 300 个文件，总大小不超过 20 MB")
        paths = [(relative_path(name), content) for name, content in files]
        if all(len(p.parts) > 1 for p, _ in paths) and len({p.parts[0] for p, _ in paths}) == 1:
            paths = [(PurePosixPath(*p.parts[1:]), b) for p, b in paths]
        names = [p.as_posix() for p, _ in paths]
        if len(names) != len(set(names)) or "SKILL.md" not in names:
            raise ValueError("请导入单个技能目录，根目录必须有 SKILL.md，且不能包含重名文件")
        info = metadata(dict((p.as_posix(), b) for p, b in paths)["SKILL.md"].decode("utf-8"))
        destination = self.directory / info["name"]
        if destination.exists():
            raise ValueError("同名技能已存在，请先移除或修改名称")
        with tempfile.TemporaryDirectory(prefix="skill-", dir=self.directory) as temp:
            staging = Path(temp) / "package"
            for path, content in paths:
                target = staging / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            try:
                staging.rename(destination)
            except OSError:
                raise ValueError("技能已存在或目录无法写入") from None
        return info

    def install_zip(self, content):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = [item for item in archive.infolist() if not item.is_dir()]
            if (
                len(infos) > MAX_FILES
                or sum(item.file_size for item in infos) > MAX_BYTES
                or any((item.external_attr >> 16) & 0o170000 == 0o120000 for item in infos)
            ):
                raise ValueError("技能压缩包过大或包含符号链接")
            return self.install([(item.filename, archive.read(item)) for item in infos])

    def remove(self, name):
        shutil.rmtree(self.path(name))
