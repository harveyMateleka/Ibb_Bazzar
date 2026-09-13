from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('utilisateurs/', views.liste, name='utilisateur_liste'),
    path('utilisateurs/nouveau/', views.utilisateur_nouveau, name='utilisateur_nouveau'),
    path('utilisateurs/<int:pk>/', views.detail, name='utilisateur_detail'),
    path('utilisateurs/<int:pk>/activer/', views.activer, name='utilisateur_activer'),
    path('utilisateurs/<int:pk>/desactiver/', views.desactiver, name='utilisateur_desactiver'),
    path('roles/', views.roles, name='roles'),
    path('roles/<int:pk>/permissions/', views.role_permissions, name='role_permissions'),
    path('succursales/', views.succursales, name='succursales'),
    path('permissions/', views.permissions, name='permissions'),
    path('audit/', views.audit, name='audit'),
]
