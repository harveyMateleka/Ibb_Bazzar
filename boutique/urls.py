from django.urls import path

from . import views

app_name = 'boutique'

urlpatterns = [
    path('', views.tableau_de_bord, name='dashboard'),
    path('articles/', views.articles, name='articles'),
    path('articles/nouveau/', views.article_nouveau, name='article_nouveau'),
    path('articles/<int:pk>/', views.article_detail, name='article_detail'),
    path('stock/', views.stocks, name='stocks'),
    path('stock/entree/', views.entree, name='entree'),
    path('stock/entrees/', views.entrees_validation, name='entrees_validation'),
    path('stock/entrees/<int:pk>/', views.entree_validation_detail, name='entree_validation_detail'),
    path('stock/entrees/<int:pk>/valider/', views.entree_valider, name='entree_valider'),
    path('stock/entrees/<int:pk>/annuler/', views.entree_annuler, name='entree_annuler'),
    path('mouvements/', views.mouvements, name='mouvements'),
    path('mouvements/rapport/', views.mouvements_report, name='mouvements_report'),
    path('alertes/', views.alertes, name='alertes'),
    path('ventes/', views.ventes, name='ventes'),
    path('ventes/nouvelle/', views.vente_nouvelle, name='vente_nouvelle'),
    path('ventes/rapport/', views.ventes_report, name='ventes_report'),
    path('rapports/', views.rapports, name='rapports'),
    path('rapports/articles/', views.rapport_articles, name='rapport_articles'),
    path('rapports/variantes/', views.rapport_variantes, name='rapport_variantes'),
    path('rapports/variantes/crees/', views.rapport_variantes_crees, name='rapport_variantes_crees'),
    path('rapports/stock/', views.rapport_stock, name='rapport_stock'),
    path('rapports/inventaires/', views.rapport_inventaires, name='rapport_inventaires'),
    path('ventes/validation/', views.ventes_a_valider, name='ventes_a_valider'),
    path('ventes/<int:pk>/', views.vente_detail, name='vente_detail'),
    path('ventes/<int:pk>/lignes/<int:ligne_pk>/decider/', views.vente_decider_ligne, name='vente_decider_ligne'),
    path('ventes/<int:pk>/traiter/', views.vente_traiter, name='vente_traiter'),
    path('ventes/<int:pk>/traiter/modifier/', views.vente_modifier_traitement, name='vente_modifier_traitement'),
    path('ventes/<int:pk>/confirmer/', views.vente_confirmer, name='vente_confirmer'),
    path('ventes/<int:pk>/annuler/', views.vente_annuler, name='vente_annuler'),
    path('ventes/<int:pk>/imprimer/', views.vente_imprimer, name='vente_imprimer'),
    path('inventaires/', views.inventaires, name='inventaires'),
    path('inventaires/nouveau/', views.inventaire_nouveau, name='inventaire_nouveau'),
    path('inventaires/<int:pk>/', views.inventaire_detail, name='inventaire_detail'),
    path('inventaires/<int:pk>/valider/', views.inventaire_valider, name='inventaire_valider'),
]
