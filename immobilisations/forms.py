"""Formulaires du module Immobilisations.

Règles :
- succursale / domaine : auto-remplis depuis le périmètre de l'utilisateur
  connecté et verrouillés (readonly) pour les non-superusers.
- `par` (acteur) : TOUJOURS l'utilisateur connecté, auto-rempli et readonly.
"""

from django import forms

from core.permissions import appliquer_contexte

from .models import (
    Affectation,
    Casse,
    Declassement,
    Deplacement,
    Immobilisation,
    Reparation,
)


class ImmobilisationForm(forms.ModelForm):
    class Meta:
        model = Immobilisation
        fields = [
            'designation', 'categorie', 'numero_serie', 'valeur_acquisition',
            'date_acquisition', 'fournisseur', 'succursale', 'domaine',
            'service', 'emplacement', 'observation',
        ]
        widgets = {
            'date_acquisition': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'valeur_acquisition': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, succursales=None, domaines=None, contexte=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_acquisition'].input_formats = ['%Y-%m-%d']
        if succursales is not None:
            self.fields['succursale'].queryset = succursales
        if domaines is not None:
            self.fields['domaine'].queryset = domaines
        appliquer_contexte(self, contexte)


class _ActeurMixin:
    """Rend le champ `par` auto-rempli et readonly (= l'utilisateur connecté)."""

    def _init_acteur(self, request_user):
        if request_user is None:
            return
        self.fields['par'].initial = request_user
        self.fields['par'].disabled = True
        self.fields['par'].help_text = 'Vous — l’utilisateur qui pose l’action.'
        self.fields['par'].widget.attrs['class'] = 'input'


class AffectationForm(_ActeurMixin, forms.ModelForm):
    """Affectation d'un bien à un service / succursale / emplacement."""

    class Meta:
        model = Affectation
        fields = ['succursale', 'service', 'emplacement', 'par']
        widgets = {
            'service': forms.TextInput(attrs={'class': 'input'}),
            'emplacement': forms.TextInput(attrs={'class': 'input'}),
        }

    def __init__(self, *args, succursales=None, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if succursales is not None:
            self.fields['succursale'].queryset = succursales
        self._init_acteur(request_user)


class DeplacementForm(_ActeurMixin, forms.ModelForm):
    """Déplacement d'un bien vers une nouvelle situation."""

    class Meta:
        model = Deplacement
        fields = ['nouvelle_succursale', 'nouveau_service', 'nouvel_emplacement', 'motif', 'par']
        widgets = {
            'nouveau_service': forms.TextInput(attrs={'class': 'input'}),
            'nouvel_emplacement': forms.TextInput(attrs={'class': 'input'}),
            'motif': forms.TextInput(attrs={'class': 'input'}),
        }

    def __init__(self, *args, succursales=None, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if succursales is not None:
            self.fields['nouvelle_succursale'].queryset = succursales
        self._init_acteur(request_user)


class ReparationForm(_ActeurMixin, forms.ModelForm):
    """Déclaration d'une réparation."""

    class Meta:
        model = Reparation
        fields = ['motif', 'description', 'cout', 'par']
        widgets = {
            'motif': forms.TextInput(attrs={'class': 'input'}),
            'cout': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_acteur(request_user)


class CasseForm(_ActeurMixin, forms.ModelForm):
    """Déclaration d'une casse."""

    class Meta:
        model = Casse
        fields = ['motif', 'description', 'par']
        widgets = {
            'motif': forms.TextInput(attrs={'class': 'input'}),
        }

    def __init__(self, *args, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_acteur(request_user)


class CasseEvaluationForm(forms.ModelForm):
    """Évaluation d'une casse (décision)."""

    class Meta:
        model = Casse
        fields = ['decision', 'observation']
        widgets = {
            'decision': forms.Select(attrs={'class': 'input'}),
        }


class DeclassementForm(_ActeurMixin, forms.ModelForm):
    """Demande de déclassement d'un bien."""

    class Meta:
        model = Declassement
        fields = ['motif', 'par']
        widgets = {
            'motif': forms.TextInput(attrs={'class': 'input'}),
        }

    def __init__(self, *args, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_acteur(request_user)
