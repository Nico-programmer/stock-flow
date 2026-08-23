from django import forms

# Imports models and functions
from django.contrib.auth import get_user_model
from apps.companies.models import Company

# Login form
class LoginForm(forms.Form):
    username = forms.CharField(max_length=25, widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}), label="Nombre de usuario")
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="Contraseña")

# ----------------------------------------------------------------------------------------------------------------------------------------------------

CustomUser = get_user_model()

class CreateUserForm(forms.ModelForm):
    """
    Form to create a new CustomUser (admin/manager creating employees, etc.).
    Built as a ModelForm so uniqueness on username/email is validated
    automatically using the model's `unique=True` constraints.
    """

    # Password is not a model field on CustomUser (it's hashed via set_password),
    # so we declare it manually with two inputs to confirm the value.
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = CustomUser
        # Only expose fields relevant to a "create user" form.
        # is_active, is_staff, date_joined, etc. are left to model defaults.
        fields = ['first_name', 'last_name', 'username', 'email', 'company', 'role']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-select'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'first_name': "Nombres",
            'last_name': "Apellidos",
            'username': "Nombre de usuario",
            'email': "Correo electrónico",
            'company': "Compañía",
            'role': "Rol de usuario",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict the company dropdown to real Company records.
        self.fields['company'].queryset = Company.objects.all()
        # Company is optional at the model level, keep it that way here too.
        self.fields['company'].required = False

    def clean_password2(self):
        """Ensure both password fields match before saving."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password2

    def save(self, commit=True):
        """
        Override save() so the password gets hashed via set_password()
        instead of being stored as plain text by the default ModelForm save.
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user