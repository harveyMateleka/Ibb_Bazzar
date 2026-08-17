from django.contrib import admin

from .models import ArticleBoutique, Vente, VenteLigne


@admin.register(ArticleBoutique)
class ArticleBoutiqueAdmin(admin.ModelAdmin):
    list_display = ['article', 'type_produit', 'taille', 'couleur', 'prix_achat', 'prix_vente', 'prix_limite', 'en_vente']
    list_filter = ['type_produit', 'taille', 'couleur', 'en_vente']
    search_fields = ['article__code', 'article__designation', 'reference']


@admin.register(VenteLigne)
class VenteLigneAdmin(admin.ModelAdmin):
    list_display = ['vente', 'article', 'quantite', 'prix_unitaire', 'total']


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ['numero', 'date_vente', 'succursale', 'domaine', 'utilisateur', 'statut', 'total']
    list_filter = ['statut', 'type_paiement', 'succursale', 'domaine']
    search_fields = ['numero']
    readonly_fields = ['numero', 'sous_total', 'total', 'date_validation']
