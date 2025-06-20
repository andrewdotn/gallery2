import base64
import io
import logging
import os
import subprocess
import threading
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

from PIL import Image
from exiftool import ExifTool

ULTRAHDR_APP_MODE_ENCODE = "0"
ULTRAHDR_APP_MODE_DECODE = "1"
ULTRAHDR_APP_OUTPUT_TRANSFER_FUNCTION_LINEAR = "0"
ULTRAHDR_APP_OUTPUT_COLOR_FORMAT_RGBAHALFFLOAT = "4"

logger = logging.getLogger(__name__)


class ExifToolWrapper:
    def __init__(self):
        self._exiftool = ExifTool()
        self._running = False
        self.lock = threading.Lock()

    def execute_json(self, *query):
        with self.lock:
            if not self._running:
                self._exiftool.run()
                self._running = True
            try:
                return self._exiftool.execute_json(*query)
            except Exception as e:
                logger.exception(f"Failed on query {query!r}")
                raise


exiftool_json = ExifToolWrapper().execute_json


class HdrSourceImage:
    def __init__(self, image_path):
        self._image_path = os.fspath(image_path)

        self.im = Image.open(self._image_path)
        self.width, self.height = self.im.size
        self.mode = self.im.mode

    def close(self):
        self.im.close()

    def file_is_supported(self):
        if self._supported_heic():
            return True
        if self._supported_jpg():
            return True
        return False

    def _supported_heic(self):
        if self._image_path.lower().endswith(".heic"):
            return self.get_headroom() is not None and self.gain_map() is not None

    def _supported_jpg(self):
        if any(self._image_path.lower().endswith(ext) for ext in (".jpg", ".jpeg")):
            exif = exiftool_json("-b", "-MPImage2", self._image_path)
            return exif[0].get("MPF:MPImage2")

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
        # libraries that could correctly parse apple makernotes. Even osxphotos
        # just uses exiftool. At least this keeps only one copy running in the
        # background for requests for a pipe, rather than forking for every
        # image.
        exif_data = exiftool_json(
            "-MakerNotes:HDRGain",
            "-MakerNotes:HDRHeadroom",
            os.fspath(self._image_path),
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
        max_size=1600,
        gain_map_resolution_divisor=2,
        quality=90,
        gain_map_quality=70,
    ):

        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            base_path = tmpdir / "base.jpg"
            base_im = self.im.copy()
            base_im.thumbnail((max_size, max_size))
            base_im.save(base_path, quality=quality)

            gain_path = tmpdir / "gain.jpg"

            gain_im = None
            try:
                if self._supported_heic():
                    headroom = self.get_headroom()
                    assert headroom is not None
                    gain_im = self.gain_map()
                    assert gain_im is not None

                    config = dedent(
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

                elif gain_map_data := self._supported_jpg():
                    gain_map_data = gain_map_data.removeprefix("base64:")
                    gain_map_data = base64.b64decode(gain_map_data)
                    gain_im = Image.open(io.BytesIO(gain_map_data))
                    config_file = tmpdir / "out-config.cfg"

                    subprocess.check_call(
                        [
                            "ultrahdr_app",
                            "-m",
                            ULTRAHDR_APP_MODE_DECODE,
                            "-j",
                            self._image_path,
                            "-f",
                            config_file,
                            "-z",
                            "/dev/null",
                        ],
                        cwd=tmpdir,
                    )
                    config = config_file.read_text()
                else:
                    raise Exception("unsupported")

                gain_im = gain_im.copy()
                gain_im.thumbnail(
                    (
                        max_size // gain_map_resolution_divisor,
                        max_size // gain_map_resolution_divisor,
                    )
                )
                gain_im.save(gain_path, quality=gain_map_quality)
            finally:
                gain_im.close()

            config_path = tmpdir / "metadata.cfg"
            config_path.write_text(config)

            out_path = tmpdir / "out.jpg"

            subprocess.check_call(
                [
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
                ],
                cwd=tmpdir,
            )
            return out_path.read_bytes()
