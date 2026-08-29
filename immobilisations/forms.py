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
    Emplacement,
    Immobilisation,
    Reparation,
    Service,
)


class ImmobilisationForm(forms.ModelForm):
    class Meta:
        model = Immobilisation
        fields = [
            'designation', 'categorie', 'numero_serie', 'valeur_acquisition',
            'date_acquisition', 'succursale', 'domaine',
            'service', 'emplacement', 'periode_entretien', 'duree_vie', 'observation',
        ]
        widgets = {
            'date_acquisition': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'valeur_acquisition': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'periode_entretien': forms.NumberInput(attrs={'min': 1}),
            'duree_vie': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, succursales=None, domaines=None, contexte=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_acquisition'].input_formats = ['%Y-%m-%d']
        for champ, Entite in (('service', Service), ('emplacement', Emplacement)):
            self.fields[champ].queryset = Entite.objects.filter(actif=True)
            self.fields[champ].empty_label = '— Aucun —'
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

    def __init__(self, *args, succursales=None, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if succursales is not None:
            self.fields['succursale'].queryset = succursales
        for champ, Entite in (('service', Service), ('emplacement', Emplacement)):
            self.fields[champ].queryset = Entite.objects.filter(actif=True)
            self.fields[champ].empty_label = '— Aucun —'
        self._init_acteur(request_user)


class DeplacementForm(_ActeurMixin, forms.ModelForm):
    """Déplacement d'un bien vers une nouvelle situation."""

    class Meta:
        model = Deplacement
        fields = ['nouvelle_succursale', 'nouveau_service', 'nouvel_emplacement', 'motif', 'par']
        widgets = {
            'motif': forms.TextInput(attrs={'class': 'input'}),
        }

    def __init__(self, *args, succursales=None, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if succursales is not None:
            self.fields['nouvelle_succursale'].queryset = succursales
        for champ, Entite in (('nouveau_service', Service), ('nouvel_emplacement', Emplacement)):
            self.fields[champ].queryset = Entite.objects.filter(actif=True)
            self.fields[champ].empty_label = '— Aucun —'
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
        fields = ['motif', 'date_dommage', 'description', 'responsable_dommage', 'par']
        widgets = {
            'motif': forms.TextInput(attrs={'class': 'input'}),
            'date_dommage': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'input'}),
            'responsable_dommage': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Nom de la personne ayant causé le dommage',
            }),
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
