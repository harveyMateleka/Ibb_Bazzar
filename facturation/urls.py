from django.urls import path

from . import views

app_name = 'facturation'

urlpatterns = [
    path('', views.journal, name='journal'),
    path('journal/imprimer/', views.journal_imprimer, name='journal_imprimer'),
    path('factures/<int:pk>/recu/', views.recu, name='recu'),
]
