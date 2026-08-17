from django.urls import path

from . import views

app_name = 'approvisionnement'

urlpatterns = [
    path('', views.tableau_de_bord, name='dashboard'),
    path('entrees/', views.entree_liste, name='entree'),
    path('entrees/nouvelle/', views.entree_nouveau, name='entree_nouveau'),
    path('entrees/validation/', views.entree_validation_liste, name='entree_validation'),
    path('entrees/validation/<int:pk>/', views.entree_validation_detail, name='entree_validation_detail'),
    path('entrees/<int:pk>/', views.entree_detail, name='entree_detail'),
    path('entrees/<int:pk>/valider/', views.entree_valider, name='entree_valider'),
    path('entrees/<int:pk>/imprimer/', views.entree_imprimer, name='entree_imprimer'),
    path('sorties/', views.sortie_liste, name='sortie'),
    path('sorties/nouvelle/', views.sortie_nouveau, name='sortie_nouveau'),
    path('sorties/validation/', views.sortie_validation_liste, name='sortie_validation'),
    path('sorties/validation/<int:pk>/', views.sortie_validation_detail, name='sortie_validation_detail'),
    path('sorties/<int:pk>/', views.sortie_detail, name='sortie_detail'),
    path('sorties/<int:pk>/valider/', views.sortie_valider, name='sortie_valider'),
    path('sorties/<int:pk>/imprimer/', views.sortie_imprimer, name='sortie_imprimer'),
    path('mouvements/', views.historique, name='historique'),
    path('mouvements/<int:pk>/', views.historique_detail, name='historique_detail'),
    path('inventaires/', views.inventaire_liste, name='inventaires'),
    path('inventaires/nouveau/', views.inventaire_nouveau, name='inventaire_nouveau'),
    path('inventaires/<int:pk>/', views.inventaire_detail, name='inventaire_detail'),
    path('inventaires/<int:pk>/valider/', views.inventaire_valider, name='inventaire_valider'),
    path('rapports/', views.rapport, name='rapport'),
    path('rapports/imprimer/', views.rapport_imprimer, name='rapport_imprimer'),
]
