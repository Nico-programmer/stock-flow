from django import forms

# Imports models and functions
from django.contrib.auth import get_user_model
from apps.companies.models import Company

# Login form
class LoginForm(forms.Form):
    username = forms.CharField(max_length=25, widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True, 'placeholder': 'Ingresa tu nombre de usuario.'}), label="Nombre de usuario")
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ingresa tu contraseña.'}), label="Contraseña")

# ----------------------------------------------------------------------------------------------------------------------------------------------------