"""
Thumbnail extraction utilities for gallery2 app.

This module provides classes for extracting thumbnails from different types of files.
"""

import os
from pathlib import Path
from typing import List, Optional
import av
from PIL import Image, UnidentifiedImageError
from django.conf import settings
from django.http import Http404

from gallery2.files import IMAGE_EXTENSIONS, MOVIE_EXTENSIONS
from gallery2.models import Entry
from hdr.hdr_jpg_thumb import HdrHeicImage


class ThumbnailExtractor:
    """Base class for thumbnail extractors."""

    def __init__(self, gallery_id: int, entry_id: int, size: int = 500):
        self.gallery_id = gallery_id
        self.entry_id = entry_id
        self.entry = Entry.objects.get(gallery_id=gallery_id, id=entry_id)
        self.size = size
        self.thumbnails_dir = Path(settings.MEDIA_ROOT) / "thumbnails"
        os.makedirs(self.thumbnails_dir, exist_ok=True)

    def _thumbnail_path_name(self, suffix):
        return (
            self.thumbnails_dir
            / f"gallery_{self.gallery_id}_entry_{self.entry_id}_thumb_{self.size}"
        ).with_suffix(suffix)

    def _thumbnail_exists(self, original_path) -> bool:
        if not self.entry.main_thumbnail_path:
            return False
        if not (self.thumbnails_dir / self.entry.main_thumbnail_path).exists():
            return False

        stat = original_path.stat()
        if self.entry.mtimes and stat.st_mtime in self.entry.mtimes:
            return True
        else:
            return False

    def get_thumbnail(self, path):
        if not self._thumbnail_exists(path):
            self._extract_thumbnail(path)
        return self.thumbnails_dir / self.entry.main_thumbnail_path

    def _extract_thumbnail(self, original_path):
        raise NotImplementedError("Subclasses must implement extract_thumbnail")

    def _save_thumb_meta(self, width, height, thumbnail_path):
        print("saved", self.entry.id, "thumbnail", thumbnail_path)
        new_mtimes = []
        for p in self.entry.filenames:
            new_mtimes.append(os.stat(Path(self.entry.gallery.directory) / p).st_mtime)
        self.entry.mtimes = new_mtimes
        self.entry.width = width
        self.entry.height = height
        if thumbnail_path is not None:
            self.entry.main_thumbnail_path = thumbnail_path.relative_to(
                self.thumbnails_dir
            )
        self.entry.save()


class ImageThumbnailExtractor(ThumbnailExtractor):
    """Thumbnail extractor for image files (png, jpeg, heic)."""

    @classmethod
    def can_handle(cls, filename: str) -> bool:
        """Check if this extractor can handle the given filename."""
        ext = Path(filename).suffix.lower()
        return ext in IMAGE_EXTENSIONS

    def _extract_thumbnail(self, original_path: Path) -> tuple:
        saved = False
        if original_path.suffix.lower() == ".heic":
            im = HdrHeicImage(original_path)
            width, height = im.width, im.height

            if im.get_headroom() is not None and im.gain_map():
                thumbnail_path = self._thumbnail_path_name(".jpg")

                jpeg_bytes = im.to_jpeg(max_size=self.size)
                thumbnail_path.write_bytes(jpeg_bytes)
                saved = True

        if not saved:
            with Image.open(original_path) as img:
                thumbnail_path = self._thumbnail_path_name(".webp")

                # Get original dimensions before creating thumbnail
                width, height = img.size
                img.thumbnail((self.size, self.size))
                img.save(thumbnail_path, "WEBP", quality=90)

        self._save_thumb_meta(width=width, height=height, thumbnail_path=thumbnail_path)


class VideoThumbnailExtractor(ThumbnailExtractor):
    """Thumbnail extractor for video files."""

    @classmethod
    def can_handle(cls, filename: str) -> bool:
        """Check if this extractor can handle the given filename."""
        ext = Path(filename).suffix.lower()
        return ext in MOVIE_EXTENSIONS

    def _extract_thumbnail(self, original_path: Path) -> tuple:
        thumbnail_path = self._thumbnail_path_name(".webp")

        container = av.open(str(original_path))
        video_stream = next(s for s in container.streams if s.type == "video")

        width = video_stream.width
        height = video_stream.height

        THUMBNAIL_POSITION = 0.1  # 10% in
        duration = float(container.duration) / av.time_base
        seek_position = int(duration * THUMBNAIL_POSITION)

        container.seek(seek_position, stream=video_stream)

        for frame in container.decode(video_stream):
            img = frame.to_image()
            img.thumbnail((self.size, self.size))
            img.save(thumbnail_path, "WEBP", quality=90)
            break
        container.close()

        self._save_thumb_meta(width=width, height=height, thumbnail_path=thumbnail_path)


def get_thumbnail_extractor(
    filenames: List[str], gallery_id: int, entry_id: int, size: int = 500
) -> Optional[ThumbnailExtractor]:
    """
    Factory function to get the appropriate thumbnail extractor for the given filenames.

    Args:
        filenames: List of filenames to check
        gallery_id: ID of the gallery
        entry_id: ID of the entry
        size: Size of the thumbnail

    Returns:
        An appropriate ThumbnailExtractor instance, or None if no suitable extractor is found
    """
    if not filenames:
        return None

    # Try to find an image file first
    for filename in filenames:
        if ImageThumbnailExtractor.can_handle(filename):
            return ImageThumbnailExtractor(gallery_id, entry_id, size)

    # If no image file is found, try to find a video file
    for filename in filenames:
        if VideoThumbnailExtractor.can_handle(filename):
            return VideoThumbnailExtractor(gallery_id, entry_id, size)

    # If no suitable file is found, return None
    return None
