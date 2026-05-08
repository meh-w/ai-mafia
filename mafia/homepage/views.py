__all__ = ("HomeView",)


import django.views
import django.views.generic


class HomeView(django.views.generic.TemplateView):
    template_name = "homepage/main.html"
