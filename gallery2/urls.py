from django.urls import path
from . import views

app_name = "gallery2"

urlpatterns = [
    path("", views.GalleryListView.as_view(), name="gallery_list"),
    path("<int:pk>/", views.GalleryDetailView.as_view(), name="gallery_detail"),
    path("create/", views.GalleryCreateView.as_view(), name="gallery_create"),
    path(
        "entry/<int:entry_id>/thumbnail/", views.entry_thumbnail, name="entry_thumbnail"
    ),
    path(
        "entry/<int:entry_id>/thumbnail/<int:size>/",
        views.entry_thumbnail,
        name="entry_thumbnail_with_size",
    ),
    path(
        "entry/<int:entry_id>/edit-caption",
        views.edit_caption,
        name="entry_edit_caption",
    ),
    path(
        "entry/<int:entry_id>/set_hidden",
        views.set_entry_hidden,
        name="set_entry_hidden",
    ),
]
