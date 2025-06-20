import argparse
import os
import shutil
from argparse import BooleanOptionalAction
from pathlib import Path

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from gallery2.models import Gallery, Entry
from gallery2.thumbnails import ImageThumbnailExtractor, VideoThumbnailExtractor
from gallery2.views import remux_if_necessary


class Command(BaseCommand):
    help = "Build a static gallery for publishing"

    def add_arguments(self, parser):
        parser.add_argument("gallery_id", type=int, help="ID of the gallery to build")
        parser.add_argument(
            "--output-dir",
            type=str,
            default="../publish",
            help="Directory to output the published gallery (default: publish)",
        )
        parser.add_argument(
            "--testing",
            help=argparse.SUPPRESS,
            action=BooleanOptionalAction,
            default=False,
        )

    def handle(self, *args, gallery_id, output_dir, testing, **options):
        gallery = Gallery.objects.get(pk=gallery_id)

        # Create publish directory (wipe if exists)
        publish_path = Path(output_dir)
        if publish_path.exists():
            self.stdout.write(f"Removing existing directory: {publish_path}")
            shutil.rmtree(publish_path)

        media_path = publish_path / "media"
        os.makedirs(media_path, exist_ok=True)

        self.stdout.write(f"Building gallery '{gallery.name}' to {publish_path}")

        entries = (
            Entry.objects.filter(gallery=gallery, hidden=False)
            .exclude(caption="")
            .order_by("order")
        )

        if not entries:
            self.stdout.write(
                self.style.WARNING("No visible entries with captions found")
            )
            return

        self.stdout.write(f"Found {entries.count()} entries to publish")

        # Process each entry
        published_entries = []
        for i, entry in enumerate(entries):
            self.stdout.write(f"Processing entry: {entry.basename}")

            image_file = None
            video_file = None

            for filename in entry.filenames:
                if ImageThumbnailExtractor.can_handle(filename):
                    original_path = Path(gallery.directory) / filename
                    if original_path.exists():
                        image_file = original_path
                        break

            for filename in entry.filenames:
                if VideoThumbnailExtractor.can_handle(filename):
                    original_path = Path(gallery.directory) / filename
                    if original_path.exists():
                        video_file = original_path
                        break

            if not image_file and not video_file:
                self.stdout.write(
                    self.style.WARNING(f"No original files found for entry {entry.id}")
                )
                continue

            # Default to image file if both are available
            primary_file = image_file if image_file else video_file
            file_type = "image" if image_file else "video"

            extension = primary_file.suffix.lower()

            dest_filename = Path(f"{i:04d}{extension}")
            dest_path = media_path / dest_filename

            # For images, use thumbnail instead of original file
            if file_type == "image":
                # Create thumbnail extractor
                thumbnail_extractor = ImageThumbnailExtractor(
                    gallery.id, entry.id, 1600
                )
                thumbnail_path = thumbnail_extractor.get_thumbnail(primary_file)

                dest_filename = dest_filename.with_suffix(thumbnail_path.suffix)
                dest_path = dest_path.with_suffix(thumbnail_path.suffix)

                # Copy the thumbnail instead of the original
                shutil.copy2(thumbnail_path, dest_path)
                self.stdout.write(
                    f"  Copied thumbnail for {primary_file.name} to {dest_path}"
                )
            else:
                # video-only file; generate a thumbnail and treat as image
                assert video_file

                extractor = VideoThumbnailExtractor(
                    gallery_id=gallery.id, entry_id=entry.id, size=1600
                )
                thumbnail_path = extractor.get_thumbnail(video_file)

                dest_filename = dest_filename.with_suffix(thumbnail_path.suffix)
                dest_path = dest_path.with_suffix(thumbnail_path.suffix)
                shutil.copy2(thumbnail_path, dest_path)
                self.stdout.write(
                    f"  Copied thumbnail for video {video_file.name} to {dest_path}"
                )

            video_filename = None
            if video_file:
                video_file = remux_if_necessary(entry, video_file)

                video_extension = video_file.suffix.lower()
                video_dest_filename = f"{i:04d}{video_extension}"
                video_dest_path = media_path / video_dest_filename

                shutil.copy2(video_file, video_dest_path)
                self.stdout.write(f"  Copied {video_file.name} to {video_dest_path}")
                video_filename = video_dest_filename

            # in case width, height filled in during thumbnail generation
            entry.refresh_from_db()
            published_entries.append(
                {
                    "id": entry.id,
                    "filename": dest_filename,
                    "has_image": bool(image_file),
                    "has_video": bool(video_file),
                    "video_filename": video_filename,
                    "caption": entry.caption,
                    "timestamp": entry.timestamp,
                    "width": entry.width,
                    "height": entry.height,
                }
            )

        # Render the template to index.html
        context = {
            "testing": testing,
            "gallery": gallery,
            "entries": published_entries,
        }

        html_content = render_to_string("gallery2/gallery_publish.html", context)

        # Write the HTML to index.html
        with open(publish_path / "index.html", "w") as f:
            f.write(html_content)

        assets_source_path = Path(__file__).parent.parent.parent / "publish_assets"

        public_src = Path(gallery.directory) / "media" / "public"
        public_publish_dir = media_path / "public"
        os.makedirs(public_publish_dir, exist_ok=True)
        for f in (public_src).glob("*"):
            if f.name.startswith("."):
                continue
            shutil.copy2(f, public_publish_dir)
            self.stdout.write(f"  Copied {f.name} to {public_publish_dir}")

        js_dir = publish_path / "js"
        os.makedirs(js_dir, exist_ok=True)
        for js_file in (assets_source_path / "js").glob("*.js"):
            if f.name.startswith("."):
                continue
            shutil.copy2(js_file, js_dir)
            self.stdout.write(f"  Copied {js_file.name} to {js_dir}")

        css_dir = publish_path / "css"
        os.makedirs(css_dir, exist_ok=True)
        for css_file in (assets_source_path / "css").glob("*.css"):
            if f.name.startswith("."):
                continue
            shutil.copy2(css_file, css_dir)
            self.stdout.write(f"  Copied {css_file.name} to {css_dir}")

        self.stdout.write(
            self.style.SUCCESS(f"Gallery published successfully to {publish_path}")
        )
