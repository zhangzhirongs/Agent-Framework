import io
import mimetypes
import re
import time
from pathlib import PurePosixPath

from docx import Document
from PIL import Image
from pypdf import PdfReader

from app.store import new_id

ALLOWED = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".html",
    ".htm",
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
}


def save_file(store, thread_id, name, content):
    name = PurePosixPath(name.replace("\\", "/")).name
    if not name or len(name) > 180 or re.search(r"[\x00-\x1f]", name):
        raise ValueError("文件名称无效")
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in ALLOWED:
        raise ValueError("暂不支持此文件类型")
    media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    if media_type.startswith("image/"):
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > 40_000_000:
                    raise ValueError("图片像素数量超过限制")
                image.verify()
                expected = {
                    ".png": "PNG",
                    ".jpg": "JPEG",
                    ".jpeg": "JPEG",
                    ".webp": "WEBP",
                    ".gif": "GIF",
                }
                if image.format != expected[suffix]:
                    raise ValueError("图片内容与后缀不一致")
        except (OSError, SyntaxError, Image.DecompressionBombError):
            raise ValueError("图片内容无效或过大") from None
    identity = new_id()
    with store.connect() as db:
        db.execute(
            "INSERT INTO files VALUES(?,?,?,?,?,?)",
            (identity, thread_id, name, media_type, content, time.time()),
        )
    return {"id": identity, "name": name, "media_type": media_type}


def extract_text(item):
    content = item["content"]
    name = item["name"].lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages[:80])[:100000]
    if name.endswith(".docx"):
        # Enforce a decompression budget before the document parser opens the archive.
        import zipfile

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 40 * 1024 * 1024:
                raise ValueError("文档解压大小超出限制")
        document = Document(io.BytesIO(content))
        paragraphs = [p.text for p in document.paragraphs]
        paragraphs += [
            "\t".join(cell.text for cell in row.cells)
            for table in document.tables
            for row in table.rows
        ]
        return "\n".join(paragraphs)[:100000]
    if item["media_type"].startswith("image/"):
        return "此文件为图片；启用视觉模型后可随消息分析。"
    return content.decode("utf-8", errors="replace")[:100000]
