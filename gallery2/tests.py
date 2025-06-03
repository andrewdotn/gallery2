from django.test import Client
from django.urls import reverse

from gallery2.models import Gallery, Entry


def test_gallery_list_view(db, client):
    g1 = Gallery.objects.create(name="Test Gallery 1")
    g2 = Gallery.objects.create(name="Test Gallery 2")

    response = client.get(reverse("gallery2:gallery_list"))

    assert response.status_code == 200
    assert "gallery2/gallery_list.html" in [t.name for t in response.templates]

    assert "galleries" in response.context

    galleries = response.context["galleries"]
    assert galleries.count() == 2
    assert list(galleries) == [g1, g2]

    assert g1.name in response.text
    assert g2.name in response.text


def test_gallery_create_view_get(db, client):
    response = client.get(reverse("gallery2:gallery_create"))
    assert response.status_code == 200


def test_gallery_create_view_post_valid(db, client):
    response = client.post(
        reverse("gallery2:gallery_create"), data={"name": "New Test Gallery"}
    )

    assert response.status_code == 302
    assert response.url == reverse("gallery2:gallery_list")
    assert Gallery.objects.filter(name="New Test Gallery").exists()


def test_gallery_create_view_post_invalid(db, client):
    response = client.post(reverse("gallery2:gallery_create"), data={"name": ""})

    assert response.status_code == 200
    assert response.context["form"].errors
    assert not Gallery.objects.filter(name="").exists()


def test_gallery_detail_view(db, client):
    gallery = Gallery.objects.create(name="Test Gallery Detail")

    entry1 = Entry.objects.create(
        gallery=gallery,
        filename="image1.jpg",
        order=2.0,
        caption="This is **bold** text",
    )
    entry2 = Entry.objects.create(
        gallery=gallery,
        filename="image2.jpg",
        order=1.0,
        caption="This is *italic* text",
    )
    entry3 = Entry.objects.create(
        gallery=gallery,
        filename="image3.jpg",
        order=3.0,
        caption="This is a [link](http://example.com)",
    )

    response = client.get(reverse("gallery2:gallery_detail", kwargs={"pk": gallery.pk}))

    assert response.status_code == 200
    assert "gallery2/gallery_detail.html" in [t.name for t in response.templates]

    assert "gallery" in response.context
    assert response.context["gallery"] == gallery
    assert gallery.name in response.text

    assert "entries" in response.context
    entries = response.context["entries"]
    assert entries.count() == 3

    assert list(entries) == [entry2, entry1, entry3]

    assert entry1.filename in response.text
    assert entry2.filename in response.text
    assert entry3.filename in response.text

    # Check markdown is interpreted (HTML tags are generated)
    assert "<strong>bold</strong>" in response.text
    assert "<em>italic</em>" in response.text
    assert '<a href="http://example.com">link</a>' in response.text
