from django.test import Client
from django.urls import reverse

from gallery2.models import Gallery


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

    response = client.get(reverse("gallery2:gallery_detail", kwargs={"pk": gallery.pk}))

    assert response.status_code == 200
    assert "gallery2/gallery_detail.html" in [t.name for t in response.templates]

    assert "gallery" in response.context
    assert response.context["gallery"] == gallery

    assert gallery.name in response.text
