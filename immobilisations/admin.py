from django.contrib import admin

from .models import (
    Affectation,
    Casse,
    CategorieImmobilisation,
    Declassement,
    Deplacement,
    Emplacement,
    Immobilisation,
    Reparation,
    Service,
)


@admin.register(CategorieImmobilisation)
class CategorieImmobilisationAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'actif']
    search_fields = ['nom', 'code']


class EmplacementInline(admin.TabularInline):
    model = Emplacement
    extra = 1


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['nom', 'actif']
    search_fields = ['nom']
    inlines = [EmplacementInline]


@admin.register(Emplacement)
class EmplacementAdmin(admin.ModelAdmin):
    list_display = ['nom', 'service', 'actif']
    list_filter = ['service', 'actif']
    search_fields = ['nom', 'service__nom']


@admin.register(Immobilisation)
class ImmobilisationAdmin(admin.ModelAdmin):
    list_display = ['code', 'designation', 'categorie', 'succursale', 'etat_physique',
                    'statut_administratif', 'valeur_acquisition', 'emplacement']
    list_filter = ['etat_physique', 'statut_administratif', 'succursale', 'categorie', 'service']
    search_fields = ['code', 'designation', 'numero_serie', 'service__nom', 'emplacement__nom']
    readonly_fields = ['code', 'date_creation', 'date_modification']


@admin.register(Affectation)
class AffectationAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'quantite', 'succursale', 'service', 'emplacement',
                    'date_affectation', 'par', 'actif']
    list_filter = ['succursale', 'actif']
    search_fields = ['immobilisation__code']


@admin.register(Deplacement)
class DeplacementAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'quantite', 'date_deplacement',
                    'ancien_emplacement', 'nouvel_emplacement', 'par']
    list_filter = ['nouvelle_succursale']


@admin.register(Reparation)
class ReparationAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'date_reparation', 'motif', 'cout', 'statut', 'par']
    list_filter = ['statut']


@admin.register(Casse)
class CasseAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'service', 'emplacement', 'quantite', 'date_casse', 'motif',
                    'responsable_dommage', 'decision', 'par']
    list_filter = ['decision']


@admin.register(Declassement)
class DeclassementAdmin(admin.ModelAdmin):
    list_display = ['immobilisation', 'service', 'emplacement', 'quantite',
                    'date_demande', 'motif', 'statut', 'par', 'valide_par']
    list_filter = ['statut']
