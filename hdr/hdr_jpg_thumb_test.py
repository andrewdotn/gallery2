import io
import subprocess
from contextlib import closing
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from einops import rearrange

from .hdr_jpg_thumb import (
    ULTRAHDR_APP_MODE_DECODE,
    ULTRAHDR_APP_OUTPUT_TRANSFER_FUNCTION_LINEAR,
    ULTRAHDR_APP_OUTPUT_COLOR_FORMAT_RGBAHALFFLOAT,
    HdrSourceImage,
)

TEST_DATA_DIR = Path(__file__).parent

SAMPLE_HEIC_PATH = TEST_DATA_DIR / "sample-apple-image.heic"
SAMPLE_JPEG_PATH = TEST_DATA_DIR / "sample-hdr.jpg"


@pytest.fixture
def jpeg_sample_image():
    with closing(HdrSourceImage(SAMPLE_JPEG_PATH)) as im:
        yield im


@pytest.fixture
def heic_sample_image():
    with closing(HdrSourceImage(SAMPLE_HEIC_PATH)) as im:
        yield im


def test_image_size(heic_sample_image):
    assert heic_sample_image.width == 640
    assert heic_sample_image.height == 480
    assert heic_sample_image.mode == "RGB"


def test_load_aux_image(heic_sample_image):
    # This looks like a bug in Photos.app, that the exported smaller-size image
    # has the original gain map, 1/2 the horizontal resolution of the original
    # image
    assert heic_sample_image.gain_map().width == 2016
    assert heic_sample_image.gain_map().mode == "L"  # grayscale


def test_load_hdr_gain_info(heic_sample_image):
    # The number comes from the inspector in Preview.app
    assert heic_sample_image.get_headroom() == pytest.approx(3.445, 0.001)


def test_hdr_encode_decode_fraction_heic(heic_sample_image, tmp_path):
    """Thumbnail an HDR heic file to an ultrahdr jpeg, decode it as floats, and
    look for >100% brightness pixels.
    """
    assert heic_sample_image.file_is_supported()
    jpeg_data = heic_sample_image.to_jpeg(max_size=400)
    with Image.open(io.BytesIO(jpeg_data)) as jpeg_im:
        assert jpeg_im.width == 400
        assert jpeg_im.height == 300

        jpeg_file = tmp_path / "out.jpeg"
        jpeg_file.write_bytes(jpeg_data)

        rgb = decode_jpeg_to_raw(jpeg_file, tmp_path, jpeg_im.height, jpeg_im.width, 4)

    # I guess about 0.19% of RGB values are > 1.0?
    assert np.sum(rgb >= 1.0) / np.size(rgb) * 100 == pytest.approx(0.19, 0.01)


def test_hdr_decode_fraction2(jpeg_sample_image, tmp_path):
    assert jpeg_sample_image.file_is_supported()
    jpeg_data = jpeg_sample_image.to_jpeg(max_size=400)
    with Image.open(io.BytesIO(jpeg_data)) as jpeg_im:
        assert jpeg_im.width == 400
        assert jpeg_im.height == 178

        jpeg_file = tmp_path / "out.jpeg"
        jpeg_file.write_bytes(jpeg_data)

        rgb = decode_jpeg_to_raw(
            jpeg_file, tmp_path, w=jpeg_im.width, h=jpeg_im.height, c=4
        )

    thumb_path = tmp_path / "sample-thumb.jpeg"
    thumb_path.write_bytes(jpeg_data)

    assert np.sum(rgb >= 1.0) / np.size(rgb) * 100 == pytest.approx(47.5, 0.1)


def decode_jpeg_to_raw(jpeg_file, tmp_path, h, w, c):
    "h = height, w = width, c = channels"
    raw_file = tmp_path / "out.raw"

    # Decode a sample image and look at the proportion of pixels > 100%
    # brightness.
    subprocess.check_call(
        [
            "ultrahdr_app",
            "-m",
            ULTRAHDR_APP_MODE_DECODE,
            "-j",
            jpeg_file,
            "-o",
            ULTRAHDR_APP_OUTPUT_TRANSFER_FUNCTION_LINEAR,
            "-O",
            ULTRAHDR_APP_OUTPUT_COLOR_FORMAT_RGBAHALFFLOAT,
            "-f",
            "gainmap",
            "-z",
            raw_file,
        ],
        cwd=tmp_path,
    )

    raw_data = raw_file.read_bytes()
    raw_array = np.frombuffer(raw_data, dtype=np.float16)
    raw_array = rearrange(raw_array, "(w h c) -> w h c", h=h, w=w, c=c)

    alpha = raw_array[:, :, 3]
    assert np.max(alpha) == 1.0
    assert np.min(alpha) == 1.0

    rgb = raw_array[:, :, :3]
    return rgb
