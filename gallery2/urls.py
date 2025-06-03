from django.urls import path
from . import views

app_name = "gallery2"

urlpatterns = [
    path("", views.GalleryListView.as_view(), name="gallery_list"),
    path("<int:pk>/", views.GalleryDetailView.as_view(), name="gallery_detail"),
    path("create/", views.GalleryCreateView.as_view(), name="gallery_create"),
]
