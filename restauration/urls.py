from django.urls import path

from . import views

app_name = 'restauration'

urlpatterns = [
    path('', views.tableau_de_bord, name='dashboard'),
    path('cuisine/', views.ecran_cuisine, name='cuisine'),
    path('cuisine/plats/<int:pk>/portions/', views.plat_ajouter_portions, name='plat_ajouter_portions'),
    path('cuisine/plats/<int:pk>/ajuster/', views.plat_ajuster_quantite, name='plat_ajuster_quantite'),
    path('bar/', views.ecran_bar, name='bar'),
    path('barbecus/', views.ecran_barbecus, name='barbecus'),
    path('terrasse/', views.ecran_terrasse, name='terrasse'),
    path('commandes/', views.commande_liste, name='commandes'),
    path('commandes/nouvelle/', views.commande_nouveau, name='commande_nouveau'),
    path('commandes/<int:pk>/', views.commande_detail, name='commande_detail'),
    path('commandes/<int:pk>/ajouter/', views.commande_ajouter_plat, name='commande_ajouter'),
    path('commandes/<int:pk>/lignes/<int:ligne_pk>/plus/', views.commande_ligne_plus, name='commande_ligne_plus'),
    path('commandes/<int:pk>/lignes/<int:ligne_pk>/moins/', views.commande_ligne_moins, name='commande_ligne_moins'),
    path('commandes/<int:pk>/lignes/<int:ligne_pk>/supprimer/', views.commande_ligne_supprimer, name='commande_ligne_supprimer'),
    path('commandes/<int:pk>/lignes/<int:ligne_pk>/servir/', views.commande_ligne_servir, name='commande_ligne_servir'),
    path('commandes/<int:pk>/valider/', views.commande_valider, name='commande_valider'),
    path('commandes/<int:pk>/encaisser/', views.commande_encaisser, name='commande_encaisser'),
    path('commandes/<int:pk>/annuler/', views.commande_annuler, name='commande_annuler'),
    path('commandes/<int:pk>/imprimer/', views.commande_imprimer, name='commande_imprimer'),
    path('commandes/<int:pk>/tickets/', views.commande_tickets, name='commande_tickets'),
    path('commandes/<int:pk>/tickets/envoyer/', views.commande_imprimer_postes, name='commande_imprimer_postes'),
    path('commandes/<int:pk>/ticket/<str:service>/', views.commande_ticket_service, name='commande_ticket_service'),
    path('tables/<int:pk>/ouvrir/', views.table_ouvrir, name='table_ouvrir'),
]
