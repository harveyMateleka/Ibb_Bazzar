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
    path('ventes/validation/', views.ventes_a_valider, name='ventes_a_valider'),
    path('ventes/<int:pk>/', views.vente_detail, name='vente_detail'),
    path('ventes/<int:pk>/approuver/', views.vente_approuver, name='vente_approuver'),
    path('ventes/<int:pk>/annuler/', views.vente_annuler, name='vente_annuler'),
    path('ventes/<int:pk>/imprimer/', views.vente_imprimer, name='vente_imprimer'),
    path('inventaires/', views.inventaires, name='inventaires'),
    path('inventaires/nouveau/', views.inventaire_nouveau, name='inventaire_nouveau'),
    path('inventaires/<int:pk>/', views.inventaire_detail, name='inventaire_detail'),
    path('inventaires/<int:pk>/valider/', views.inventaire_valider, name='inventaire_valider'),
]
