from django.contrib import admin

from .models import (
    AlerteStockBoutique,
    ArticleBoutique,
    BonEntreeBoutique,
    CategorieBoutique,
    FournisseurBoutique,
    InventaireBoutique,
    LigneInventaireBoutique,
    MouvementStockBoutique,
    SousCategorieBoutique,
    StockBoutique,
    UniteBoutique,
    VarianteArticle,
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
    list_display = ['code', 'designation', 'succursale', 'domaine']
    list_filter = ['succursale', 'domaine']
    search_fields = ['code', 'designation']


@admin.register(BonEntreeBoutique)
class BonEntreeBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['numero', 'article', 'couleur', 'taille', 'genre',
                    'quantite', 'prix_unitaire', 'statut', 'cree_par', 'date_creation']
    list_filter = ['statut', 'succursale']
    search_fields = ['numero', 'article__code']
    readonly_fields = ['numero', 'date_creation', 'date_validation']


@admin.register(VarianteArticle)
class VarianteArticleAdmin(admin.ModelAdmin):
    list_display = ['code_variante', 'article', 'couleur', 'taille', 'genre',
                    'prix_unitaire', 'prix_minimum', 'prix_maximum', 'seuil_alerte', 'statut']
    list_filter = ['genre', 'statut', 'categorie', 'en_vente']
    search_fields = ['code_variante', 'article__code', 'article__designation']
    readonly_fields = ['code_variante']


@admin.register(StockBoutique)
class StockBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['variante', 'succursale', 'domaine', 'quantite']
    list_filter = ['succursale', 'domaine']
    search_fields = ['variante__article__code', 'variante__article__designation']


@admin.register(MouvementStockBoutique)
class MouvementStockBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['date_mouvement', 'variante', 'type', 'quantite',
                    'stock_avant', 'stock_apres', 'utilisateur', 'motif']
    list_filter = ['type', 'succursale', 'domaine']
    search_fields = ['variante__article__code', 'reference', 'motif']


@admin.register(AlerteStockBoutique)
class AlerteStockBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['date_creation', 'variante', 'type', 'seuil',
                    'quantite_actuelle', 'statut']
    list_filter = ['type', 'statut']


@admin.register(VenteLigne)
class VenteLigneAdmin(admin.ModelAdmin):
    list_display = ['vente', 'variante', 'quantite', 'prix_unitaire', 'total']


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
    list_display = ['inventaire', 'variante', 'stock_systeme', 'stock_physique', 'ecart']
    list_filter = ['inventaire__statut']
    search_fields = ['variante__article__code']
