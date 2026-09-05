from django.urls import path

from . import views

app_name = 'facturation'

urlpatterns = [
    path('', views.journal, name='journal'),
    path('journal/imprimer/', views.journal_imprimer, name='journal_imprimer'),
    path('commandes/<int:pk>/encaisser/', views.encaisser, name='encaisser'),
    path('factures/<int:pk>/recu/', views.recu, name='recu'),
    path('factures/<int:pk>/recu/imprimer/', views.recu_imprimer, name='recu_imprimer'),
]
