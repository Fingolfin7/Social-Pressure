from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import UserLoginForm, UserProfileForm, UserRegisterForm


def register(request):
    redirect_to = _safe_next(request, request.POST.get("next") or request.GET.get("next") or "")
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Account created.")
            if url_has_allowed_host_and_scheme(
                redirect_to,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(redirect_to)
            return redirect("home")
        messages.error(request, "Please correct the errors below.")
    else:
        form = UserRegisterForm()

    return render(request, "users/register.html", {"form": form, "next": redirect_to})


def _safe_next(request, redirect_to):
    if url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return ""


class CustomLoginView(LoginView):
    authentication_form = UserLoginForm
    template_name = "users/login.html"

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username, email, or password.")
        return super().form_invalid(form)


def logout_view(request):
    auth_logout(request)
    return redirect("login")


@login_required
def profile(request):
    old_avatar_name = request.user.avatar.name
    old_avatar_storage = request.user.avatar.storage if old_avatar_name else None

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            profile_user = form.save(commit=False)
            remove_photo = form.cleaned_data.get("remove_photo")
            if remove_photo:
                profile_user.avatar = ""
            profile_user.save()

            new_avatar_name = profile_user.avatar.name
            should_delete_old = old_avatar_name and (
                remove_photo or (new_avatar_name and old_avatar_name != new_avatar_name)
            )
            if should_delete_old:
                old_avatar_storage.delete(old_avatar_name)

            messages.success(request, "Saved.")
            return redirect("profile")
    else:
        form = UserProfileForm(instance=request.user)

    avatar_name = request.user.first_name or request.user.username
    return render(
        request,
        "users/profile.html",
        {
            "form": form,
            "avatar_initial": avatar_name[:1],
        },
    )
