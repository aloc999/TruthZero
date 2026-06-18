import base64
import mimetypes
import os
from pathlib import Path
from typing import Optional


SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


class VisionInput:
    @staticmethod
    def is_image(path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in SUPPORTED_FORMATS

    @staticmethod
    def encode_image(path: str) -> dict:
        filepath = Path(path).expanduser().resolve()
        if not filepath.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        ext = filepath.suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported image format: {ext}")
        mime = mimetypes.guess_type(str(filepath))[0] or "image/png"
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{data}"},
        }

    @staticmethod
    def encode_url(url: str) -> dict:
        return {
            "type": "image_url",
            "image_url": {"url": url},
        }

    @staticmethod
    def build_message_with_images(text: str, images: list[str]) -> dict:
        content = [{"type": "text", "text": text}]
        for img in images:
            if img.startswith(("http://", "https://")):
                content.append(VisionInput.encode_url(img))
            elif os.path.exists(os.path.expanduser(img)):
                content.append(VisionInput.encode_image(img))
        return {"role": "user", "content": content}

    @staticmethod
    def extract_images_from_text(text: str) -> tuple[str, list[str]]:
        import re
        pattern = r'!\[.*?\]\((.*?)\)|(?:^|\s)((?:/|~|\.\.?/)\S+\.(?:png|jpg|jpeg|gif|webp))'
        images = []
        clean_text = text
        for match in re.finditer(pattern, text):
            img_path = match.group(1) or match.group(2)
            if img_path:
                images.append(img_path.strip())
                clean_text = clean_text.replace(match.group(0), "").strip()
        return clean_text, images

    @staticmethod
    def supports_vision(model: str) -> bool:
        vision_models = {
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
            "claude-sonnet-4-20250514", "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
            "deepseek-chat", "deepseek-v4-pro",
        }
        return any(m in model for m in vision_models)
