from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Permission

from .models import AuditLog, Domaine, Role, Succursale, User, UserSuccursale


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'est_systeme']
    search_fields = ['nom', 'code']
    list_filter = ['est_systeme']
    filter_horizontal = ['permissions']


@admin.register(Succursale)
class SuccursaleAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'actif']
    search_fields = ['nom', 'code']
    list_filter = ['actif']


@admin.register(Domaine)
class DomaineAdmin(admin.ModelAdmin):
    list_display = ['code', 'libelle']
    search_fields = ['code', 'libelle']


@admin.register(UserSuccursale)
class UserSuccursaleAdmin(admin.ModelAdmin):
    list_display = ['utilisateur', 'succursale', 'domaine', 'role', 'principale', 'date_affectation']
    list_filter = ['succursale', 'domaine', 'role', 'principale']
    search_fields = ['utilisateur__username']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['date', 'module', 'action', 'utilisateur', 'succursale', 'objet_type', 'objet_id']
    list_filter = ['module', 'action']
    search_fields = ['utilisateur__username', 'action', 'objet_type']
    readonly_fields = [
        'utilisateur', 'succursale', 'module', 'action', 'objet_type', 'objet_id',
        'ancienne_valeur', 'nouvelle_valeur', 'motif', 'adresse_ip', 'date',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ['username', 'get_full_name', 'email', 'telephone', 'fonction', 'is_active', 'is_staff']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'telephone', 'fonction']
    list_filter = ['is_active', 'is_staff', 'roles', 'succursales']
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Profil', {'fields': ('telephone', 'fonction', 'cree_par', 'date_desactivation')}),
        ('Rôles & succursales', {'fields': ('roles',)}),
    )
    filter_horizontal = DjangoUserAdmin.filter_horizontal + ('roles',)

    def save_model(self, request, obj, form, change):
        if not change and not obj.cree_par_id:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)
        # Traçabilité des créations / modifications effectuées dans l'admin.
        from .services import AuditService

        AuditService.auditer(
            utilisateur=request.user,
            module='CORE',
            action='user.create' if not change else 'user.update',
            objet_type='User',
            objet_id=obj.pk,
            nouvelle_valeur={'username': obj.username},
        )


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['codename', 'name', 'content_type']
    search_fields = ['codename', 'name']
    list_filter = ['content_type__app_label']
