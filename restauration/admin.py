from django.contrib import admin

from .forms import ImprimanteAdminForm, PlatAdminForm
from .impression import lister_imprimantes_windows, resoudre_imprimante_windows
from .models import CategorieMenu, CompositionPlat, Imprimante, Plat, Salle, ServicePoste, Serveur, Table


class CompositionPlatInline(admin.TabularInline):
    model = CompositionPlat
    extra = 1
    autocomplete_fields = ['produit']


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = ['nom', 'ordre']
    search_fields = ['nom']


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ['numero', 'salle', 'places']
    list_filter = ['salle']
    search_fields = ['numero']
    autocomplete_fields = ['salle']


@admin.register(Serveur)
class ServeurAdmin(admin.ModelAdmin):
    list_display = ['nom', 'prenom', 'actif']
    list_filter = ['actif']
    search_fields = ['nom', 'prenom']


@admin.register(CategorieMenu)
class CategorieMenuAdmin(admin.ModelAdmin):
    list_display = ['nom', 'ordre']
    search_fields = ['nom']


@admin.register(Imprimante)
class ImprimanteAdmin(admin.ModelAdmin):
    form = ImprimanteAdminForm
    list_display = ['nom', 'service', 'nom_systeme', 'installee']
    list_filter = ['service']
    search_fields = ['nom', 'nom_systeme']

    @admin.display(boolean=True, description='Installée sur ce PC')
    def installee(self, obj):
        return bool(resoudre_imprimante_windows(obj.nom_systeme))

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['imprimantes_windows'] = lister_imprimantes_windows()
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Plat)
class PlatAdmin(admin.ModelAdmin):
    form = PlatAdminForm
    list_display = ['nom', 'categorie', 'prix', 'devise', 'quantite', 'service', 'imprimante', 'actif']
    list_filter = ['categorie', 'devise', 'service', 'imprimante', 'actif']
    search_fields = ['nom']
    autocomplete_fields = ['categorie']
    inlines = [CompositionPlatInline]
    change_form_template = 'admin/restauration/plat/change_form.html'
    fieldsets = (
        (None, {
            'fields': ('categorie', 'nom', 'prix', 'devise', 'description', 'actif'),
        }),
        ('Disponibilité', {
            'fields': ('quantite', 'seuil_alerte'),
            'description': (
                'Terrasse : la quantité augmente à la sortie magasin (y compris une sortie bar). '
                'Cuisine et barbecus : saisissez les plats préparés sur l’écran du poste. '
                'La quantité n’est diminuée qu’à la validation de la commande (alerte à 2, blocage à 0).'
            ),
        }),
        ('Service et impression', {
            'fields': ('service', 'imprimante'),
            'description': (
                'Le service détermine l’écran et l’imprimante. Un plat terrasse n’est envoyé '
                'qu’à l’imprimante terrasse, un plat cuisine à la cuisine, un plat barbecus au barbecus. '
                'Une commande mixte imprime un ticket distinct par service.'
            ),
        }),
    )

    class Media:
        js = ['js/plat_admin.js']

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        mapping = {service: [] for service, _libelle in ServicePoste.choices}
        for imprimante in Imprimante.objects.all():
            mapping.setdefault(imprimante.service, []).append(imprimante.pk)
        context['imprimantes_par_service'] = mapping
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj,
        )
