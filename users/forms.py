from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UsernameField


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
