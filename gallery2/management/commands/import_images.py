import os
import pathlib
import re
from collections import defaultdict
from datetime import datetime, timezone

from PIL import Image, ExifTags
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Min

from gallery2.models import Entry, Gallery
from gallery2.utils import timestamp_to_order


class Command(BaseCommand):
    help = "Import images from a directory into a gallery"

    def add_arguments(self, parser):
        parser.add_argument(
            "directory", type=str, help="Directory containing images to import"
        )
        parser.add_argument(
            "gallery_id", type=int, help="ID of the gallery to import images into"
        )

    def handle(self, *args, **options):
        directory_path = pathlib.Path(options["directory"])
        gallery_id = options["gallery_id"]

        if not directory_path.exists() or not directory_path.is_dir():
            raise CommandError(
                f"Directory '{directory_path}' does not exist or is not a directory"
            )

        try:
            gallery = Gallery.objects.get(pk=gallery_id)
            if gallery.directory is None or gallery.directory == ".":
                gallery.directory = os.fspath(directory_path)
                gallery.save()
        except Gallery.DoesNotExist:
            raise CommandError(f"Gallery with ID {gallery_id} does not exist")

        self.stdout.write(
            f"Importing images from '{directory_path}' into gallery '{gallery.name}'"
        )

        image_extensions = (".jpg", ".jpeg", ".png", ".heic", ".mov")
        image_files = [
            f
            for f in directory_path.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ]

        basename_groups = {}
        for image_file in image_files:
            basename = image_file.stem
            if basename not in basename_groups:
                basename_groups[basename] = []
            basename_groups[basename].append(image_file)

        self.stdout.write(f"Found {len(basename_groups)} unique images")

        created_count = 0
        skipped_count = 0
        entries_to_create = []

        # First pass: collect all entries to create with their timestamps
        for basename, files in basename_groups.items():
            if Entry.objects.filter(gallery=gallery, basename=basename).exists():
                self.stdout.write(f"Skipping '{basename}' - already exists")
                skipped_count += 1
                continue

            timestamp = None
            for file_path in files:
                if file_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic"):
                    try:
                        timestamp = self.extract_timestamp(file_path)
                        if timestamp:
                            break
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Could not extract timestamp from '{file_path.name}': {e}"
                            )
                        )
            filenames_list = [file.name for file in files]

            entries_to_create.append(
                {
                    "basename": basename,
                    "filenames": filenames_list,
                    "timestamp": timestamp,
                    "files": files,
                }
            )

        entries_to_create.sort(
            key=lambda x: x["timestamp"] if x["timestamp"] else str(datetime.max)
        )

        # Group entries by order value to handle duplicates
        order_groups = defaultdict(list)
        for entry_data in entries_to_create:
            order_value = timestamp_to_order(entry_data["timestamp"])
            order_groups[order_value].append(entry_data)

        with transaction.atomic():
            for order_value, entries in order_groups.items():
                if order_value is None:
                    min_order = min(
                        Entry.objects.filter(gallery=gallery).aggregate(Min("order"))[
                            "order__min"
                        ],
                        0,
                    )
                    min_order -= len(entries)

                # If multiple entries have the same order value (including those
                # without timestamp), add a small increment to make them unique
                for i, entry_data in enumerate(entries):
                    if order_value is None:
                        order_value = min_order + i

                    unique_order = order_value + (1e-6 * i) if i > 0 else order_value

                    Entry.objects.create(
                        gallery=gallery,
                        basename=entry_data["basename"],
                        filenames=entry_data["filenames"],
                        order=unique_order,
                        caption="",
                        timestamp=entry_data["timestamp"],
                    )

                    self.stdout.write(f"Created entry for '{entry_data['basename']}'")
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: {created_count} entries created, {skipped_count} skipped"
            )
        )

    def extract_timestamp(self, file_path):
        """
        Extract timestamp from image EXIF data if available.

        Returns:
            A datetime object in UTC timezone, or None if no timestamp could be extracted.
        """
        with Image.open(file_path) as img:
            exif_data = img.getexif()
            if exif_data:
                data = {ExifTags.TAGS[k]: v for k, v in exif_data.items()}
                data |= {
                    ExifTags.TAGS[k]: v
                    for k, v in exif_data.get_ifd(ExifTags.IFD.Exif).items()
                }
                data |= {
                    ExifTags.GPSTAGS[k]: v
                    for k, v in exif_data.get_ifd(ExifTags.IFD.GPSInfo).items()
                }

                if "DateTimeOriginal" not in data or "OffsetTimeOriginal" not in data:
                    return None

                # Format the date from "YYYY:MM:DD HH:MM:SS" to "YYYY-MM-DD HH:MM:SS"
                date_time_str = re.sub(
                    r"""
                    (\d{4})
                    :
                    (\d{2})
                    :
                    (\d{2})
                    """,
                    r"\1-\2-\3",
                    data["DateTimeOriginal"],
                    flags=re.VERBOSE,
                )

                # Parse the datetime with timezone offset
                dt_str = date_time_str + " " + data["OffsetTimeOriginal"]
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S %z")

                # Convert to UTC
                return dt.astimezone(timezone.utc)
