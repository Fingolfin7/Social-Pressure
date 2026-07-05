from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UsernameField


MAX_AVATAR_SIZE = 5 * 1024 * 1024


class UserRegisterForm(UserCreationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"autocomplete": "username"})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )

    class Meta:
        model = get_user_model()
        fields = ["username", "email", "password1", "password2"]


class UserLoginForm(AuthenticationForm):
    username = UsernameField(
        label="Username or email",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Your name",
        help_text="What partners see.",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    avatar = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={"accept": "image/*", "class": "avatar-file-input"}),
    )
    remove_photo = forms.BooleanField(required=False, label="Remove photo")

    class Meta:
        model = get_user_model()
        fields = ["first_name", "avatar"]

    def clean(self):
        cleaned_data = super().clean()
        avatar = self.files.get(self.add_prefix("avatar"))
        if avatar and avatar.size > MAX_AVATAR_SIZE:
            self.add_error("avatar", "That photo's too big — 5 MB max.")
        return cleaned_data
