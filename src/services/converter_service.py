import re
import subprocess
from pathlib import Path

from PIL import Image
import pypandoc

from src.core.logger import get_logger

logger = get_logger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".ico"}
_MEDIA_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".mp3", ".wav", ".ogg", ".flac", ".aac"}
_DOCUMENT_EXTS = {".docx", ".md", ".rst", ".html", ".epub", ".odt", ".pdf", ".txt"}
_SAFE_EXTENSION = re.compile(r"^[a-z0-9]{1,12}$")


def normalize_output_extension(raw_format: str) -> str:
    """Returns a safe dot-prefixed extension for converter output paths."""
    fmt = (raw_format or "").strip().lower().lstrip(".")
    if not _SAFE_EXTENSION.fullmatch(fmt):
        raise ValueError("Formato de salida no permitido.")
    ext = f".{fmt}"
    if ext not in (_IMAGE_EXTS | _MEDIA_EXTS | _DOCUMENT_EXTS):
        raise ValueError("Formato de salida no soportado.")
    return ext


def get_file_type(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _MEDIA_EXTS:
        return "media"
    if ext in _DOCUMENT_EXTS:
        return "document"
    return "unknown"


def convert_image(input_path: str, output_path: str) -> bool:
    try:
        with Image.open(input_path) as img:
            # JPEG does not support alpha/palette channels.
            if output_path.lower().endswith((".jpg", ".jpeg")) and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path)
        return True
    except Exception as e:
        logger.warning("Image conversion failed: %s", e)
        return False


def convert_media(input_path: str, output_path: str) -> bool:
    try:
        command = ["ffmpeg", "-nostdin", "-y", "-i", input_path, output_path]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            logger.warning("FFmpeg conversion failed: %s", (result.stderr or "").strip()[:1000])
            return False
        return True
    except Exception as e:
        logger.warning("Media conversion failed: %s", e)
        return False


def convert_document(input_path: str, output_path: str) -> bool:
    try:
        in_ext = Path(input_path).suffix.lower()
        out_ext = Path(output_path).suffix.lower()

        if in_ext == ".pdf" and out_ext == ".docx":
            from pdf2docx import parse

            parse(input_path, output_path)
            return True

        pypandoc.convert_file(input_path, to=out_ext.lstrip("."), outputfile=output_path)
        return True
    except Exception as e:
        logger.warning("Document conversion failed: %s", e)
        return False


def run_conversion(input_path: str, output_path: str) -> bool:
    file_type = get_file_type(input_path)
    try:
        output_ext = normalize_output_extension(Path(output_path).suffix)
    except ValueError as exc:
        logger.warning("Conversion rejected for unsafe output path %r: %s", output_path, exc)
        return False

    if file_type == "unknown":
        logger.warning("Conversion rejected for unsupported input type: %s", input_path)
        return False
    if output_ext not in (_IMAGE_EXTS | _MEDIA_EXTS | _DOCUMENT_EXTS):
        return False

    if file_type == "image":
        return convert_image(input_path, output_path)
    if file_type == "media":
        return convert_media(input_path, output_path)
    if file_type == "document":
        return convert_document(input_path, output_path)
    return False
