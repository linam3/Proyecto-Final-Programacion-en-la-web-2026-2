from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("UFEST", {"fields": ("codigo", "rol")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("UFEST", {"fields": ("codigo", "rol")}),)
    list_display = ("codigo", "username", "first_name", "last_name", "rol")
    list_filter = ("rol",)
    search_fields = ("codigo", "username", "first_name", "last_name")