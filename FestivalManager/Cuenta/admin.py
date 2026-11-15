from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("UFEST", {"fields": ("codigo", "rol", "telefono", "verificado")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("UFEST", {"fields": ("codigo", "rol", "telefono", "verificado", "email", "first_name", "last_name")}),)
    list_display = ("codigo", "username", "first_name", "last_name", "rol", "verificado")
    list_filter = ("rol", "verificado")
    search_fields = ("codigo", "username", "first_name", "last_name")
    actions = ["marcar_verificados"]

    @admin.action(description="Marcar como verificados")
    def marcar_verificados(self, request, queryset):
        n = queryset.update(verificado=True)
        self.message_user(request, f"{n} usuario(s) verificados.")