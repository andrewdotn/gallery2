from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView

from .models import Gallery


class GalleryListView(ListView):
    model = Gallery
    context_object_name = "galleries"


class GalleryCreateView(CreateView):
    model = Gallery
    fields = ["name"]
    success_url = reverse_lazy("gallery2:gallery_list")
