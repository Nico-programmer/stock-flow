from django.contrib import admin

# Import the model
from .models import CustomUser

# Register your models here.
admin.site.register(CustomUser)