from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import UserLoginForm, UserRegisterForm


def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Account created.")
            return redirect("home")
        messages.error(request, "Please correct the errors below.")
    else:
        form = UserRegisterForm()

    return render(request, "users/register.html", {"form": form})


class CustomLoginView(LoginView):
    authentication_form = UserLoginForm
    template_name = "users/login.html"

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username, email, or password.")
        return super().form_invalid(form)


def logout_view(request):
    auth_logout(request)
    return redirect("login")
