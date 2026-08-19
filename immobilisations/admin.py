from django.contrib import admin

from .models import (
    Affectation,
    Casse,
    CategorieImmobilisation,
    Declassement,
    Deplacement,
    Immobilisation,
    Reparation,
)


@admin.register(CategorieImmobilisation)
class CategorieImmobilisationAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'actif']
    search_fields = ['nom', 'code']


@admin.register(Immobilisation)
class ImmobilisationAdmin(admin.ModelAdmin):
    list_display = ['code', 'designation', 'categorie', 'succursale', 'etat_physique',
                    'statut_administratif', 'valeur_acquisition', 'emplacement']
    list_filter = ['etat_physique', 'statut_administratif', 'succursale', 'categorie']
    search_fields = ['code', 'designation', 'numero_serie']
    readonly_fields = ['code', 'date_creation', 'date_modification']


@admin.register(Affectation)
class AffectationAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'succursale', 'service', 'emplacement',
                    'date_affectation', 'par', 'actif']
    list_filter = ['succursale', 'actif']
    search_fields = ['immobilisation__code']


@admin.register(Deplacement)
class DeplacementAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'date_deplacement', 'ancienne_succursale',
                    'nouvelle_succursale', 'motif', 'par']
    list_filter = ['nouvelle_succursale']


@admin.register(Reparation)
class ReparationAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'date_reparation', 'motif', 'cout', 'statut', 'par']
    list_filter = ['statut']


@admin.register(Casse)
class CasseAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'date_casse', 'motif', 'decision', 'par']
    list_filter = ['decision']


@admin.register(Declassement)
class DeclassementAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'date_demande', 'motif', 'statut', 'par', 'valide_par']
    list_filter = ['statut']
