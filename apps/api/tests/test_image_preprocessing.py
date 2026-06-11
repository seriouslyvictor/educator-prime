from pathlib import Path

from PIL import Image
import pytest

from classroom_downloader.image_preprocessing import prepare_image_for_llm
from classroom_downloader.llm_errors import LlmCallError


def _save_image(path: Path, size: tuple[int, int], *, image_format: str, exif=None) -> None:
    image = Image.new("RGB", size, "red")
    kwargs = {"exif": exif} if exif is not None else {}
    image.save(path, format=image_format, **kwargs)


def test_prepare_image_strips_exif_metadata(tmp_path: Path) -> None:
    path = tmp_path / "with-gps.jpg"
    exif = Image.Exif()
    exif[274] = 1
    exif[34853] = {1: "N"}
    _save_image(path, (40, 30), image_format="JPEG", exif=exif)

    prepared = prepare_image_for_llm(path)
    output = tmp_path / "prepared.jpg"
    output.write_bytes(prepared.data)

    with Image.open(output) as image:
        assert image.getexif() == {}
        assert image.format == "JPEG"
    assert prepared.mime_type == "image/jpeg"


def test_prepare_image_applies_orientation(tmp_path: Path) -> None:
    path = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    _save_image(path, (40, 20), image_format="JPEG", exif=exif)

    prepared = prepare_image_for_llm(path)

    assert (prepared.width, prepared.height) == (20, 40)


def test_prepare_image_downscales_long_side(tmp_path: Path) -> None:
    path = tmp_path / "large.png"
    _save_image(path, (4000, 2000), image_format="PNG")

    prepared = prepare_image_for_llm(path)

    assert max(prepared.width, prepared.height) <= 1536
    assert (prepared.width, prepared.height) == (1536, 768)


@pytest.mark.parametrize(
    ("filename", "image_format"),
    [
        ("unsupported.tiff", "TIFF"),
        ("unsupported.heic", None),
    ],
)
def test_prepare_image_rejects_unsupported_formats(
    tmp_path: Path,
    filename: str,
    image_format: str | None,
) -> None:
    path = tmp_path / filename
    if image_format:
        _save_image(path, (10, 10), image_format=image_format)
    else:
        path.write_bytes(b"not a supported image")

    with pytest.raises(LlmCallError) as error:
        prepare_image_for_llm(path)

    assert error.value.code == "local_unsupported_image_format"
    assert error.value.retryable is False


def test_prepare_image_rejects_oversize_input(tmp_path: Path) -> None:
    path = tmp_path / "too-large.jpg"
    _save_image(path, (10, 10), image_format="JPEG")

    with pytest.raises(LlmCallError) as error:
        prepare_image_for_llm(path, max_input_bytes=1)

    assert error.value.code == "local_image_too_large"
    assert error.value.retryable is False
