import io
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from einops import rearrange

from .hdr_jpg_thumb import (
    ULTRAHDR_APP_MODE_DECODE,
    ULTRAHDR_APP_OUTPUT_TRANSFER_FUNCTION_LINEAR,
    ULTRAHDR_APP_OUTPUT_COLOR_FORMAT_RGBAHALFFLOAT,
    HdrHeicImage,
)

TEST_DATA_DIR = Path(__file__).parent


@pytest.fixture
def sample_image():
    return HdrHeicImage(TEST_DATA_DIR / "sample-apple-image.heic")


def test_image_size(sample_image):
    assert sample_image.width == 640
    assert sample_image.height == 480
    assert sample_image.mode == "RGB"


def test_load_aux_image(sample_image):
    # This looks like a bug in Photos.app, that the exported smaller-size image
    # has the original gain map, 1/2 the horizontal resolution of the original
    # image
    assert sample_image.gain_map().width == 2016
    assert sample_image.gain_map().mode == "L"  # grayscale


def test_load_hdr_gain_info(sample_image):
    # The number comes from the inspector in Preview.app
    assert sample_image.get_headroom() == pytest.approx(3.445, 0.001)


def test_hdr_decode_fraction(sample_image, tmp_path):
    jpeg_data = sample_image.to_jpeg(max_size=400)
    jpeg_im = Image.open(io.BytesIO(jpeg_data))
    assert jpeg_im.width == 400
    assert jpeg_im.height == 300

    jpeg_file = tmp_path / "out.jpeg"
    jpeg_file.write_bytes(jpeg_data)

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
    raw_array = rearrange(raw_array, "(w h c) -> w h c", h=400, w=300, c=4)

    alpha = raw_array[:, :, 3]
    assert np.max(alpha) == 1.0
    assert np.min(alpha) == 1.0

    rgb = raw_array[:, :, :3]

    # I guess about 0.19% of RGB values are > 1.0?
    assert np.sum(rgb >= 1.0) / np.size(rgb) * 100 == pytest.approx(0.19, 0.01)
