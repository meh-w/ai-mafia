__all__ = ("SignupView",)


import django.contrib.auth
import django.contrib.auth.forms
import django.urls
import django.views.generic


class SignupView(django.views.generic.CreateView):
    form_class = django.contrib.auth.forms.UserCreationForm
    template_name = "users/signup.html"
    success_url = django.urls.reverse_lazy("lobby:lobby_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        django.contrib.auth.login(self.request, self.object)
        return response
