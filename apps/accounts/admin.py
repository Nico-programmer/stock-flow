from django.contrib import admin

# Import the model
from .models import CustomUser, EmployeePermission

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(EmployeePermission)