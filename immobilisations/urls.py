from django.urls import path

from . import views

app_name = 'immobilisations'

urlpatterns = [
    path('', views.tableau_de_bord, name='dashboard'),
    path('biens/', views.biens, name='biens'),
    path('biens/nouveau/', views.bien_nouveau, name='bien_nouveau'),
    path('biens/<int:pk>/', views.bien_detail, name='bien_detail'),
    path('biens/<int:pk>/affecter/', views.affectation_nouvelle, name='affectation_nouvelle'),
    path('biens/<int:pk>/deplacer/', views.deplacement_nouveau, name='deplacement_nouveau'),
    path('biens/<int:pk>/casse/', views.casse_declarer, name='casse_declarer'),
    path('biens/<int:pk>/casses/<int:casse_pk>/evaluer/', views.casse_evaluer, name='casse_evaluer'),
    path('biens/<int:pk>/reparation/', views.reparation_declarer, name='reparation_declarer'),
    path('biens/<int:pk>/reparations/<int:rep_pk>/terminer/', views.reparation_terminer, name='reparation_terminer'),
    path('biens/<int:pk>/declasser/', views.declassement_demander, name='declassement_demander'),
    path('biens/<int:pk>/declassements/<int:dec_pk>/valider/', views.declassement_valider, name='declassement_valider'),
    path('etats/', views.etats, name='etats'),
    path('affectations/', views.affectations, name='affectations'),
    path('deplacements/', views.deplacements, name='deplacements'),
    path('historique/', views.historique, name='historique'),
]
