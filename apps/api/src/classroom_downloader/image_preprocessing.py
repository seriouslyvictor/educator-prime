from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from .llm_errors import LlmCallError


SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
UNSUPPORTED_IMAGE_SUFFIXES = {".gif", ".heic", ".heif", ".svg", ".tif", ".tiff"}


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime_type: str
    width: int
    height: int


def prepare_image_for_llm(
    path: Path,
    *,
    max_dimension: int = 1536,
    max_input_bytes: int = 15_000_000,
) -> PreparedImage:
    if path.stat().st_size > max_input_bytes:
        raise LlmCallError("local_image_too_large", False, str(path))
    if path.suffix.lower() in UNSUPPORTED_IMAGE_SUFFIXES:
        raise LlmCallError("local_unsupported_image_format", False, path.suffix.lower())

    try:
        with Image.open(path) as raw_image:
            if (raw_image.format or "").upper() not in SUPPORTED_IMAGE_FORMATS:
                raise LlmCallError(
                    "local_unsupported_image_format",
                    False,
                    raw_image.format,
                )
            image = ImageOps.exif_transpose(raw_image)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
    except LlmCallError:
        raise
    except (OSError, UnidentifiedImageError) as exc:
        raise LlmCallError("local_preprocessing_failed", False, str(exc)) from exc

    return PreparedImage(
        data=output.getvalue(),
        mime_type="image/jpeg",
        width=image.width,
        height=image.height,
    )
