import os
import shutil
import pathlib
from pathlib import Path

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.conf import settings

from gallery2.models import Gallery, Entry
from gallery2.thumbnails import ImageThumbnailExtractor, VideoThumbnailExtractor


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

    def handle(self, *args, **options):
        gallery_id = options["gallery_id"]
        output_dir = options["output_dir"]

        try:
            gallery = Gallery.objects.get(pk=gallery_id)
        except Gallery.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(f"Gallery with ID {gallery_id} does not exist")
            )
            return

        # Create publish directory (wipe if exists)
        publish_path = Path(output_dir)
        if publish_path.exists():
            self.stdout.write(f"Removing existing directory: {publish_path}")
            shutil.rmtree(publish_path)

        # Create publish directory and media subdirectory
        media_path = publish_path / "media"
        os.makedirs(media_path, exist_ok=True)

        self.stdout.write(f"Building gallery '{gallery.name}' to {publish_path}")

        # Get all non-hidden entries with non-blank captions
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
        for entry in entries:
            self.stdout.write(f"Processing entry: {entry.basename}")

            # Find both image and video files
            image_file = None
            video_file = None

            # Find an image file
            for filename in entry.filenames:
                if ImageThumbnailExtractor.can_handle(filename):
                    original_path = Path(gallery.directory) / filename
                    if original_path.exists():
                        image_file = original_path
                        break

            # Find a video file
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

            # Get file extension for primary file
            extension = primary_file.suffix.lower()

            # Copy primary file to publish/media directory
            dest_filename = Path(f"{entry.id}{extension}")
            dest_path = media_path / dest_filename

            # For images, use thumbnail instead of original file
            if file_type == "image":
                # Create thumbnail extractor
                thumbnail_extractor = ImageThumbnailExtractor(gallery.id, entry.id)

                # Generate thumbnail if it doesn't exist
                if not thumbnail_extractor.thumbnail_exists():
                    thumbnail_path, _, _ = thumbnail_extractor.extract_thumbnail(
                        primary_file
                    )
                else:
                    thumbnail_path = thumbnail_extractor.get_thumbnail_path()

                dest_filename = dest_filename.with_suffix(".jpg")
                dest_path = dest_path.with_suffix(".jpg")

                # Copy the thumbnail instead of the original
                shutil.copy2(thumbnail_path, dest_path)
                self.stdout.write(
                    f"  Copied thumbnail for {primary_file.name} to {dest_path}"
                )
            else:
                # For videos, keep copying the original file
                shutil.copy2(primary_file, dest_path)
                self.stdout.write(f"  Copied {primary_file.name} to {dest_path}")

            # Copy secondary file if it exists
            video_filename = None
            if image_file and video_file:
                video_extension = video_file.suffix.lower()
                video_dest_filename = f"{entry.id}_video{video_extension}"
                video_dest_path = media_path / video_dest_filename

                shutil.copy2(video_file, video_dest_path)
                self.stdout.write(f"  Copied {video_file.name} to {video_dest_path}")
                video_filename = video_dest_filename

            # Add entry to published entries list
            published_entries.append(
                {
                    "id": entry.id,
                    "basename": entry.basename,
                    "caption": entry.caption,
                    "timestamp": entry.timestamp,
                    "width": entry.width,
                    "height": entry.height,
                    "filename": dest_filename,
                    "file_type": file_type,
                    "has_video": bool(video_file),
                    "video_filename": video_filename,
                    "extension": extension,
                }
            )

        # Render the template to index.html
        context = {
            "gallery": gallery,
            "entries": published_entries,
        }

        html_content = render_to_string("gallery2/gallery_publish.html", context)

        # Write the HTML to index.html
        with open(publish_path / "index.html", "w") as f:
            f.write(html_content)

        # Copy assets from publish_assets directory
        assets_source_path = Path(__file__).parent.parent.parent / "publish_assets"

        # Create js directory and copy JS files
        js_dir = publish_path / "js"
        os.makedirs(js_dir, exist_ok=True)
        for js_file in (assets_source_path / "js").glob("*.js"):
            shutil.copy2(js_file, js_dir)
            self.stdout.write(f"  Copied {js_file.name} to {js_dir}")

        # Create css directory and copy CSS files
        css_dir = publish_path / "css"
        os.makedirs(css_dir, exist_ok=True)
        for css_file in (assets_source_path / "css").glob("*.css"):
            shutil.copy2(css_file, css_dir)
            self.stdout.write(f"  Copied {css_file.name} to {css_dir}")

        self.stdout.write(
            self.style.SUCCESS(f"Gallery published successfully to {publish_path}")
        )
