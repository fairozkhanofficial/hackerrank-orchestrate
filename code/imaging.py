"""Prepare local images for a vision request.

Each image's longest edge is capped at config.IMAGE_MAX_EDGE before base64
encoding, which controls image-token cost and keeps the request under the API
size limit (some submissions reach ~47 megapixels). Pillow is used when
available; without it the original bytes are sent unchanged so the pipeline
still runs on a clean machine.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

import config

try:
    from PIL import Image
    _HAVE_PIL = True
except Exception:
    _HAVE_PIL = False


@dataclass
class PreparedImage:
    image_id: str
    mime_type: str
    b64: str
    orig_bytes: int
    sent_bytes: int
    width: int
    height: int
    downscaled: bool


def _mime_for(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def prepare_image(image_id, abs_path, max_edge=None, quality=None) -> "PreparedImage":
    abs_path = Path(abs_path)
    max_edge = max_edge or config.IMAGE_MAX_EDGE
    quality = quality or config.IMAGE_JPEG_QUALITY

    raw = abs_path.read_bytes()
    orig_bytes = len(raw)
    mime = _mime_for(abs_path)
    width = height = 0
    downscaled = False
    data = raw

    if _HAVE_PIL:
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im = im.convert("RGB")
                width, height = im.size
                longest = max(width, height)
                if longest > max_edge:
                    scale = max_edge / longest
                    im = im.resize(
                        (max(1, round(width * scale)), max(1, round(height * scale))),
                        Image.LANCZOS,
                    )
                    width, height = im.size
                    downscaled = True
                buffer = io.BytesIO()
                im.save(buffer, format="JPEG", quality=quality)
                data = buffer.getvalue()
                mime = "image/jpeg"
        except Exception:
            # Any decode error: fall back to the original bytes untouched.
            data = raw

    return PreparedImage(
        image_id=image_id,
        mime_type=mime,
        b64=base64.b64encode(data).decode("ascii"),
        orig_bytes=orig_bytes,
        sent_bytes=len(data),
        width=width,
        height=height,
        downscaled=downscaled,
    )


def prepare_images(image_refs, max_edge=None, quality=None) -> list:
    """Prepare every ingest.ImageRef that exists on disk."""
    return [
        prepare_image(ref.image_id, ref.abs_path, max_edge, quality)
        for ref in image_refs if getattr(ref, "exists", False)
    ]
