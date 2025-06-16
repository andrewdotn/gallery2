import shutil
from pathlib import Path

from PIL import Image
from bs4 import BeautifulSoup
from django.core.management import call_command

from gallery2.models import Gallery, Entry
from hdr.hdr_jpg_thumb_test import SAMPLE_HEIC_PATH

from .tests import blue_jpg_file, blue_png_file, one_frame_mov_file


def test_buildgallery1(db, tmpdir, blue_jpg_file):
    src_dir = tmpdir / "src"
    src_dir.mkdir()
    g = Gallery.objects.create(name="test1", directory=src_dir)

    shutil.copy(blue_jpg_file, src_dir / "e1.jpg")
    e1 = Entry.objects.create(
        gallery=g, order=1.0, basename="e1", filenames=["e1.jpg"], caption="*Item 1*"
    )

    publish_dir = tmpdir / "publish"
    call_command("buildgallery", str(g.id), "--output-dir", str(publish_dir))

    output_html = Path(publish_dir / "index.html").read_text()
    print(output_html)
    soup = BeautifulSoup(output_html, "html.parser")

    assert soup.find("em", text="Item 1")


def test_buildgallery2(db, tmpdir, blue_jpg_file, blue_png_file, one_frame_mov_file):
    src_dir = tmpdir / "src"
    src_dir.mkdir()
    g = Gallery.objects.create(name="test1", directory=src_dir)

    test_file = src_dir / "media" / "public" / "hello.txt"
    test_file.parent.mkdir()
    test_file.write_text("hello\n")

    shutil.copy(blue_jpg_file, src_dir / "e1.jpg")
    e_jpg = Entry.objects.create(
        gallery=g, order=1.0, basename="e1", filenames=["e1.jpg"], caption="*Item 1*"
    )

    shutil.copy(blue_png_file, src_dir / "e2.png")
    e_png = Entry.objects.create(
        gallery=g, order=2.0, basename="e2", filenames=["e2.png"], caption="*Item 1*"
    )

    shutil.copy(SAMPLE_HEIC_PATH, src_dir / "e3.heic")
    e_heic = Entry.objects.create(
        gallery=g, order=3.0, basename="e3", filenames=["e3.heic"], caption="."
    )

    shutil.copy(SAMPLE_HEIC_PATH, src_dir / "e4.heic")
    shutil.copy(one_frame_mov_file, src_dir / "e4.mov")
    e_live_photo = Entry.objects.create(
        gallery=g,
        order=4.0,
        basename="e4",
        filenames=["e4.heic", "e4.mov"],
        caption=".",
    )

    shutil.copy(one_frame_mov_file, src_dir / "e5.mov")
    e_mov_only = Entry.objects.create(
        gallery=g, order=5.0, basename="e5", filenames=["e5.mov"], caption="."
    )

    publish_dir = tmpdir / "publish"
    call_command(
        "buildgallery", str(g.id), "--output-dir", str(publish_dir), "--testing"
    )

    assert Path(publish_dir / "media" / "public" / "hello.txt").read_text() == "hello\n"

    output_html = Path(publish_dir / "index.html").read_text()
    print(output_html)
    soup = BeautifulSoup(output_html, "html.parser")

    e1_div = soup.find("div", {"data-entry-id": e_jpg.id})
    e1_img = e1_div.find("img", {"src": "media/0000.webp"})
    assert e1_img
    assert e1_img["width"] == "800"
    e1_thumb = Image.open(publish_dir / "media" / "0000.webp")
    assert e1_thumb.format == "WEBP"

    e2_div = soup.find("div", {"data-entry-id": e_png.id})
    assert e2_div.find("img", {"src": "media/0001.webp"})
    e2_thumb = Image.open(publish_dir / "media" / "0001.webp")
    assert e2_thumb.format == "WEBP"

    e3_div = soup.find("div", {"data-entry-id": e_heic.id})
    assert e3_div.find("img", {"src": "media/0002.jpg"})
    e3_thumb = Image.open(publish_dir / "media" / "0002.jpg")
    assert e3_thumb.format == "MPO"

    e4_div = soup.find("div", {"data-entry-id": e_live_photo.id})
    e4_img_tag = e4_div.find("img", {"src": "media/0003.jpg"})
    assert e4_img_tag
    e4_thumb = Image.open(publish_dir / "media" / "0003.jpg")
    assert e4_thumb.format == "MPO"
    assert e4_img_tag["data-video-filename"] == "media/0003.mp4"
    assert (publish_dir / "media" / "0003.mp4").exists()

    # I thought about auto-playing videos, but decided to just show thumbnails
    # for them. Click or tap to interact.
    e5_div = soup.find("div", {"data-entry-id": e_mov_only.id})
    assert e5_div
    e5_image = e5_div.find("img", {"src": "media/0004.webp"})
    assert e5_image
    assert e5_image["width"] == "800"
    assert e5_image["data-video-filename"] == "media/0004.mp4"
    assert (publish_dir / "media" / "0004.mp4").exists()
