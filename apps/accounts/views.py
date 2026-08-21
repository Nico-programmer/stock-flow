from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect


# Import forms
from .forms import *

""" Login View """
def login_view(request):
    # If you are already authenticated, there is no point in seeing the login again.
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                if not user.is_active:
                    messages.error(request, "Tu cuenta está inactiva. Contacta al administrador.")
                    return render(request, 'login.html', {'form': form})

                login(request, user)

                # Redirection according to role
                if user.role == 'admin':
                    return redirect('dashboard')
                else:
                    return redirect('dashboard')
            else:
                messages.error(request, "Usuario o contraseña incorrectos.")
        # If the form is invalid, it lands here and is re-rendered with errors.
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})