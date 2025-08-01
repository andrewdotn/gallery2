"""website URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

import polls.urls
import gallery2.urls
from . import views

urlpatterns = [
    # URLs go here
    path("admin/", admin.site.urls),
    path("polls/", include(polls.urls, namespace="polls")),
    path("gallery/", include(gallery2.urls, namespace="gallery2")),
    path("", views.make_redirect_view("gallery/")),
    *(
        [path("__debug__", include("debug_toolbar.urls"))]
        if settings.DEBUG_TOOLBAR
        else []
    ),
    *(
        static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
        if settings.DEBUG
        else []
    ),
]
