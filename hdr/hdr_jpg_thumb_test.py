import io
import os
import subprocess
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

import numpy as np
import pytest
from PIL import Image
from einops import rearrange
from exiftool import ExifTool

ULTRAHDR_APP_MODE_ENCODE = "0"
ULTRAHDR_APP_MODE_DECODE = "1"
ULTRAHDR_APP_OUTPUT_TRANSFER_FUNCTION_LINEAR = "0"
ULTRAHDR_APP_OUTPUT_COLOR_FORMAT_RGBAHALFFLOAT = "4"

TEST_DATA_DIR = Path(__file__).parent


@cache
def exiftool():
    e = ExifTool()
    e.run()
    return e


class HdrHeicImage:
    def __init__(self, heic_path):
        self._heic_path = heic_path

        self.im = Image.open(self._heic_path)
        self.width, self.height = self.im.size
        self.mode = self.im.mode

    @cache
    def gain_map(self):
        gain_map_index = self.im.info.get("aux", {}).get(
            "urn:com:apple:photo:2020:aux:hdrgainmap"
        )
        if gain_map_index is None:
            return None

        gain_map = self.im._heif_file.get_aux_image(gain_map_index[0])
        gain_map = gain_map.to_pillow()
        assert gain_map.mode == "L"
        return gain_map

    def get_headroom(self):
        # I tried, I really tried, but I could find no maintained python exif
        # libraries that could correctly parse apple makernotes.
        exif_data = exiftool().execute_json(
            "-MakerNotes:HDRGain", "-MakerNotes:HDRHeadroom", os.fspath(self._heic_path)
        )
        gain = exif_data[0].get("MakerNotes:HDRGain")
        headroom = exif_data[0].get("MakerNotes:HDRHeadroom")

        if gain is None or headroom is None:
            return

        headroom = float(headroom)
        gain = float(gain)
        # https://developer.apple.com/documentation/appkit/applying-apple-hdr-effect-to-your-photos
        if headroom < 1.0:
            if gain <= 0.01:
                stops = -20.0 * gain + 1.8
            else:
                stops = -0.101 * gain + 1.601
        else:
            if gain <= 0.01:
                stops = -70.0 * gain + 3.0
            else:
                stops = -0.303 * gain + 2.303
        linear_headroom = pow(2.0, max(stops, 0.0))
        return linear_headroom

    def to_jpeg(
        self,
        max_size=800,
        gain_map_resolution_divisor=2,
        quality=90,
        gain_map_quality=70,
    ):
        with TemporaryDirectory() as tmpdir:
            headroom = self.get_headroom()
            assert headroom is not None
            gain_im = self.gain_map()
            assert gain_im is not None

            tmpdir = Path(tmpdir)

            base_path = tmpdir / "base.jpg"
            base_im = self.im.copy()
            base_im.thumbnail((max_size, max_size))
            base_im.save(base_path, quality=quality)

            gain_path = tmpdir / "gain.jpg"
            gain_im = gain_im.copy()
            gain_im.thumbnail(
                (
                    max_size // gain_map_resolution_divisor,
                    max_size // gain_map_resolution_divisor,
                )
            )
            gain_im.save(gain_path, quality=gain_map_quality)

            config_path = tmpdir / "metadata.cfg"
            config_path.write_text(
                dedent(
                    f"""\
                    --maxContentBoost {headroom} {headroom} {headroom}
                    --minContentBoost 1.0 1.0 1.0
                    --gamma 1.0 1.0 1.0
                    --offsetSdr 0.0 0.0 0.0
                    --offsetHdr 0.0 0.0 0.0
                    --hdrCapacityMin 1.0
                    --hdrCapacityMax {headroom}
                    --useBaseColorSpace 1\
                    """
                )
            )

            out_path = tmpdir / "out.jpg"

            cmd = [
                "ultrahdr_app",
                "-m",
                ULTRAHDR_APP_MODE_ENCODE,
                "-i",
                base_path.relative_to(tmpdir),
                "-g",
                gain_path.relative_to(tmpdir),
                "-f",
                config_path.relative_to(tmpdir),
                "-z",
                out_path.relative_to(tmpdir),
            ]
            subprocess.check_call(
                cmd,
                cwd=tmpdir,
            )
            return out_path.read_bytes()


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
