from django.contrib import admin

from .models import (
    AlerteStockBoutique,
    ArticleBoutique,
    CategorieBoutique,
    FournisseurBoutique,
    InventaireBoutique,
    LigneInventaireBoutique,
    MouvementStockBoutique,
    SousCategorieBoutique,
    StockBoutique,
    UniteBoutique,
    Vente,
    VenteLigne,
)


@admin.register(CategorieBoutique)
class CategorieBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'actif']
    search_fields = ['nom', 'code']


@admin.register(SousCategorieBoutique)
class SousCategorieBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['nom', 'categorie', 'code', 'actif']
    list_filter = ['categorie']
    search_fields = ['nom', 'code']


@admin.register(UniteBoutique)
class UniteBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code']


@admin.register(FournisseurBoutique)
class FournisseurBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['nom', 'contact', 'telephone', 'actif']
    search_fields = ['nom', 'contact']


@admin.register(ArticleBoutique)
class ArticleBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['code', 'designation', 'taille', 'couleur', 'categorie',
                    'prix_unitaire', 'prix_minimum', 'prix_maximum',
                    'succursale', 'en_vente']
    list_filter = ['categorie', 'genre', 'statut', 'en_vente', 'succursale']
    search_fields = ['code', 'reference', 'designation']


@admin.register(StockBoutique)
class StockBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['article', 'succursale', 'domaine', 'quantite', 'seuil_alerte']
    list_filter = ['succursale', 'domaine']
    search_fields = ['article__code', 'article__designation']


@admin.register(MouvementStockBoutique)
class MouvementStockBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['date_mouvement', 'article', 'type', 'quantite',
                    'stock_avant', 'stock_apres', 'utilisateur', 'motif']
    list_filter = ['type', 'succursale', 'domaine']
    search_fields = ['article__code', 'reference', 'motif']


@admin.register(AlerteStockBoutique)
class AlerteStockBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['date_creation', 'article', 'type', 'seuil',
                    'quantite_actuelle', 'statut']
    list_filter = ['type', 'statut']


@admin.register(VenteLigne)
class VenteLigneAdmin(admin.ModelAdmin):
    list_display = ['vente', 'article', 'quantite', 'prix_unitaire', 'total']


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ['numero', 'date_vente', 'succursale', 'domaine', 'utilisateur', 'statut', 'total']
    list_filter = ['statut', 'type_paiement', 'succursale', 'domaine']
    search_fields = ['numero']
    readonly_fields = ['numero', 'sous_total', 'total', 'date_validation']


@admin.register(InventaireBoutique)
class InventaireBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['numero', 'date_inventaire', 'succursale', 'domaine',
                    'responsable', 'portee', 'statut']
    list_filter = ['statut', 'portee', 'succursale', 'domaine']
    search_fields = ['numero']


@admin.register(LigneInventaireBoutique)
class LigneInventaireBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['inventaire', 'article', 'stock_systeme', 'stock_physique', 'ecart']
    list_filter = ['inventaire__statut']
    search_fields = ['article__code']
