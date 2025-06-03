from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView

from .models import Gallery, Entry


class GalleryListView(ListView):
    model = Gallery
    context_object_name = "galleries"


class GalleryDetailView(DetailView):
    model = Gallery
    context_object_name = "gallery"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entries"] = Entry.objects.filter(gallery=self.object).order_by("order")
        return context


class GalleryCreateView(CreateView):
    model = Gallery
    fields = ["name"]
    success_url = reverse_lazy("gallery2:gallery_list")
