from django.contrib import admin
from django import forms

from restauration.impression import lister_imprimantes_windows

from .models import Etablissement, Facture, LigneFacture


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ['nom_societe', 'sigle', 'contact', 'imprimante_caisse']
    fields = (
        'nom_societe',
        'sigle',
        'logo',
        'contact',
        'email',
        'adresse',
        'imprimante_caisse',
        'message_recu',
    )

    def has_add_permission(self, request):
        return not Etablissement.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name != 'imprimante_caisse' or field is None:
            return field
        noms = lister_imprimantes_windows()
        actuel = ''
        object_id = request.resolver_match.kwargs.get('object_id') if request.resolver_match else None
        if object_id:
            obj = Etablissement.objects.filter(pk=object_id).first()
            actuel = (obj.imprimante_caisse if obj else '') or ''
        if actuel and actuel not in noms:
            noms = [actuel] + noms
        if not noms:
            return field
        return forms.ChoiceField(
            label='Imprimante caisse',
            required=False,
            choices=[('', '—')] + [(nom, nom) for nom in noms],
            help_text='Nom Windows de l’imprimante 80 mm du reçu client.',
            initial=actuel or None,
        )


class LigneFactureInline(admin.TabularInline):
    model = LigneFacture
    extra = 0
    readonly_fields = ['designation', 'quantite', 'prix_unitaire', 'devise', 'montant']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ['numero', 'commande', 'date_facture', 'mode_paiement', 'table_liberee', 'utilisateur']
    list_filter = ['mode_paiement', 'date_facture']
    search_fields = ['numero', 'commande__numero', 'table_liberee']
    date_hierarchy = 'date_facture'
    inlines = [LigneFactureInline]
    readonly_fields = [
        'numero',
        'commande',
        'date_facture',
        'utilisateur',
        'mode_paiement',
        'table_liberee',
        'nom_societe',
        'sigle',
        'contact',
        'adresse',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
