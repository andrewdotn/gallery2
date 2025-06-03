import os
import pathlib
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from gallery2.models import Entry, Gallery


class Command(BaseCommand):
    help = "Import images from a directory into a gallery"

    def add_arguments(self, parser):
        parser.add_argument(
            "directory", type=str, help="Directory containing images to import"
        )
        parser.add_argument(
            "gallery_id", type=int, help="ID of the gallery to import images into"
        )
        parser.add_argument(
            "--order",
            type=float,
            default=0.0,
            help="Starting order value for new entries (default: 0.0)",
        )

    def handle(self, *args, **options):
        directory_path = pathlib.Path(options["directory"])
        gallery_id = options["gallery_id"]
        order_start = options["order"]

        if not directory_path.exists() or not directory_path.is_dir():
            raise CommandError(
                f"Directory '{directory_path}' does not exist or is not a directory"
            )

        try:
            gallery = Gallery.objects.get(pk=gallery_id)
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

        order_value = order_start
        created_count = 0
        skipped_count = 0

        with transaction.atomic():
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

                # Store all filenames in a list
                filenames_list = [file.name for file in files]

                Entry.objects.create(
                    gallery=gallery,
                    basename=basename,
                    filenames=filenames_list,
                    order=order_value,
                    caption="",
                    timestamp=timestamp,
                )

                self.stdout.write(f"Created entry for '{basename}'")
                created_count += 1
                order_value += 1.0

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: {created_count} entries created, {skipped_count} skipped"
            )
        )

    def extract_timestamp(self, file_path):
        """Extract timestamp from image EXIF data if available."""
        try:
            with Image.open(file_path) as img:
                exif_data = img.getexif()
                if exif_data:
                    # EXIF tag 36867 corresponds to DateTimeOriginal
                    date_str = exif_data.get(36867)
                    if date_str:
                        # EXIF date format: 'YYYY:MM:DD HH:MM:SS'
                        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                return None
        except (UnidentifiedImageError, OSError):
            return None
