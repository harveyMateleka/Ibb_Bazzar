from django.urls import path

from . import views

app_name = 'boutique'

urlpatterns = [
    path('', views.tableau_de_bord, name='dashboard'),
    path('articles/', views.articles, name='articles'),
    path('articles/nouveau/', views.article_nouveau, name='article_nouveau'),
    path('articles/<int:pk>/', views.article_detail, name='article_detail'),
    path('variantes/nouvelle/', views.variante_nouvelle, name='variante_nouvelle'),
    path('stock/', views.stocks, name='stocks'),
    path('stock/entree/', views.entree, name='entree'),
    path('mouvements/', views.mouvements, name='mouvements'),
    path('mouvements/rapport/', views.mouvements_report, name='mouvements_report'),
    path('alertes/', views.alertes, name='alertes'),
    path('ventes/', views.ventes, name='ventes'),
    path('ventes/nouvelle/', views.vente_nouvelle, name='vente_nouvelle'),
    path('ventes/<int:pk>/', views.vente_detail, name='vente_detail'),
    path('ventes/<int:pk>/valider/', views.vente_valider, name='vente_valider'),
    path('ventes/<int:pk>/annuler/', views.vente_annuler, name='vente_annuler'),
    path('ventes/<int:pk>/imprimer/', views.vente_imprimer, name='vente_imprimer'),
    path('inventaires/', views.inventaires, name='inventaires'),
    path('inventaires/nouveau/', views.inventaire_nouveau, name='inventaire_nouveau'),
    path('inventaires/<int:pk>/', views.inventaire_detail, name='inventaire_detail'),
    path('inventaires/<int:pk>/valider/', views.inventaire_valider, name='inventaire_valider'),
]
