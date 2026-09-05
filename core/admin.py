from django import forms
from django.contrib import admin
from django.contrib.auth.models import Permission

from approvisionnement.models import Service

from .models import AuditLog, Domaine, Role, Succursale, User, UserSuccursale


class UserAdminForm(forms.ModelForm):
    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        services = [(service.nom, service.nom) for service in Service.objects.order_by('nom')]
        self.fields['fonction'] = forms.ChoiceField(
            label='Fonction / service',
            required=False,
            choices=[('', 'Sélectionnez un service')] + services,
        )


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
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm
    list_display = ['compte', 'telephone', 'fonction', 'date_desactivation']
    search_fields = ['compte__username', 'compte__first_name', 'compte__last_name', 'telephone', 'fonction']
    list_filter = ['roles']
    raw_id_fields = ['compte', 'cree_par']
    filter_horizontal = ['roles']


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['codename', 'name', 'content_type']
    search_fields = ['codename', 'name']
    list_filter = ['content_type__app_label']
