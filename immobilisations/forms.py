"""Formulaires du module Immobilisations.

Règles :
- succursale / domaine : auto-remplis depuis le périmètre de l'utilisateur
  connecté et verrouillés (readonly) pour les non-superusers.
- `par` (acteur) : TOUJOURS l'utilisateur connecté, auto-rempli et readonly.
"""

from django import forms
from django.utils import timezone

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


class EmplacementSelect(forms.Select):
    """Chaque option porte le service parent pour le filtre JS."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs)
        service_id = getattr(getattr(value, 'instance', None), 'service_id', None)
        if service_id is None and value not in (None, ''):
            pk = getattr(value, 'value', value)
            service_id = (
                Emplacement.objects.filter(pk=pk)
                .values_list('service_id', flat=True)
                .first()
            )
        if service_id:
            option['attrs']['data-service'] = str(service_id)
        return option


def _lier_service_emplacement(form, champ_service, champ_emplacement):
    """Restreint les emplacements au service choisi (POST) et prépare le filtre JS."""
    form.fields[champ_service].queryset = Service.objects.filter(actif=True)
    form.fields[champ_service].widget.attrs.update({
        'class': 'input',
        'data-filtre-emplacements': f'id_{form.add_prefix(champ_emplacement)}',
    })
    emplacements = Emplacement.objects.filter(actif=True).select_related('service')
    if form.is_bound:
        service_id = form.data.get(form.add_prefix(champ_service))
        emplacements = emplacements.filter(service_id=service_id) if service_id else emplacements.none()
    # Le widget doit être posé avant le queryset : sinon Django laisse
    # widget.choices vide et le <select> n'a aucune option.
    form.fields[champ_emplacement].widget = EmplacementSelect(attrs={
        'class': 'input',
        'data-skip-select2': '1',
        'data-filtre-service': f'id_{form.add_prefix(champ_service)}',
    })
    form.fields[champ_emplacement].queryset = emplacements


class ImmobilisationForm(forms.ModelForm):
    class Meta:
        model = Immobilisation
        fields = [
            'designation', 'categorie', 'numero_serie', 'valeur_acquisition',
            'date_acquisition', 'quantite_achetee', 'domaine',
            'periode_entretien', 'duree_vie', 'observation',
        ]
        widgets = {
            'date_acquisition': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'valeur_acquisition': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'quantite_achetee': forms.NumberInput(attrs={'min': 1}),
            'periode_entretien': forms.NumberInput(attrs={'min': 1}),
            'duree_vie': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, succursales=None, domaines=None, contexte=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_acquisition'].input_formats = ['%Y-%m-%d']
        self.fields['quantite_achetee'].initial = 1
        if domaines is not None:
            self.fields['domaine'].queryset = domaines
        appliquer_contexte(self, contexte)

    def clean_quantite_achetee(self):
        quantite = self.cleaned_data.get('quantite_achetee')
        if quantite is None or quantite < 1:
            raise forms.ValidationError('La quantité achetée doit être au moins 1.')
        return quantite


class _ActeurMixin:
    """Rend le champ `par` auto-rempli et readonly (= l'utilisateur connecté)."""

    def _init_acteur(self, request_user):
        if request_user is None:
            return
        self.fields['par'].initial = request_user
        self.fields['par'].disabled = True
        self.fields['par'].help_text = 'Vous — l’utilisateur qui pose l’action.'
        self.fields['par'].widget.attrs['class'] = 'input'


class AffectationForm(forms.ModelForm):
    """Affectation d'un bien : quantité, service, emplacement, date, commentaire."""

    date_affectation = forms.DateField(
        label='Date d’affectation',
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'input'}),
        input_formats=['%Y-%m-%d'],
    )

    class Meta:
        model = Affectation
        fields = ['quantite', 'service', 'emplacement', 'date_affectation', 'commentaire']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1, 'class': 'input'}),
            'commentaire': forms.Textarea(attrs={'rows': 3, 'class': 'input'}),
        }

    def __init__(self, *args, immobilisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.immobilisation = immobilisation
        restante = immobilisation.quantite_restante if immobilisation else 1
        self.fields['quantite'].label = 'Nombre à affecter'
        self.fields['quantite'].initial = restante
        self.fields['quantite'].help_text = f'Reste à affecter : {restante}.'
        self.fields['quantite'].widget.attrs['max'] = restante
        self.fields['date_affectation'].initial = timezone.localdate()
        _lier_service_emplacement(self, 'service', 'emplacement')
        self.fields['service'].required = True
        self.fields['emplacement'].required = True
        self.fields['service'].empty_label = '— Choisir —'
        self.fields['emplacement'].empty_label = '— Choisir —'

    def clean_quantite(self):
        quantite = self.cleaned_data.get('quantite')
        if quantite is None or quantite < 1:
            raise forms.ValidationError('Le nombre à affecter doit être au moins 1.')
        if self.immobilisation is not None and quantite > self.immobilisation.quantite_restante:
            raise forms.ValidationError(
                f'Il ne reste que {self.immobilisation.quantite_restante} unité(s) à affecter.'
            )
        return quantite

    def clean(self):
        cleaned = super().clean()
        service = cleaned.get('service')
        emplacement = cleaned.get('emplacement')
        if service and emplacement and emplacement.service_id != service.pk:
            self.add_error(
                'emplacement',
                'Cet emplacement n’appartient pas au service sélectionné.',
            )
        return cleaned


class DeplacementForm(forms.ModelForm):
    """Déplacement : nouvel emplacement (selon le service) et quantité."""

    class Meta:
        model = Deplacement
        fields = ['quantite', 'nouveau_service', 'nouvel_emplacement']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1, 'class': 'input'}),
        }

    def __init__(self, *args, affectation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.affectation = affectation
        dispo = affectation.quantite if affectation else 1
        self.fields['quantite'].label = 'Quantité à déplacer'
        self.fields['quantite'].initial = dispo
        self.fields['quantite'].help_text = f'Disponible à cet emplacement : {dispo}.'
        self.fields['quantite'].widget.attrs['max'] = dispo
        if affectation and affectation.service_id:
            self.fields['nouveau_service'].initial = affectation.service_id
        _lier_service_emplacement(self, 'nouveau_service', 'nouvel_emplacement')
        self.fields['nouveau_service'].required = True
        self.fields['nouvel_emplacement'].required = True
        self.fields['nouveau_service'].empty_label = '— Choisir —'
        self.fields['nouvel_emplacement'].empty_label = '— Choisir —'

    def clean_quantite(self):
        quantite = self.cleaned_data.get('quantite')
        if quantite is None or quantite < 1:
            raise forms.ValidationError('La quantité à déplacer doit être au moins 1.')
        if self.affectation is not None and quantite > self.affectation.quantite:
            raise forms.ValidationError(
                f'Il n’y a que {self.affectation.quantite} unité(s) à cet emplacement.'
            )
        return quantite

    def clean(self):
        cleaned = super().clean()
        service = cleaned.get('nouveau_service')
        emplacement = cleaned.get('nouvel_emplacement')
        if service and emplacement and emplacement.service_id != service.pk:
            self.add_error(
                'nouvel_emplacement',
                'Cet emplacement n’appartient pas au service sélectionné.',
            )
        if (
            self.affectation is not None
            and emplacement
            and self.affectation.emplacement_id == emplacement.pk
            and self.affectation.service_id == (service.pk if service else None)
        ):
            self.add_error('nouvel_emplacement', 'Choisissez un emplacement différent.')
        return cleaned


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


class _AffectationChoisieMixin:
    """Service et emplacement verrouillés après le bouton Choisir."""

    def _champs_affectation_choisie(self):
        self.fields['affectation_id'] = forms.IntegerField(
            widget=forms.HiddenInput, required=True)
        self.fields['service_affiche'] = forms.CharField(
            label='Service d’affectation', required=False,
            widget=forms.TextInput(attrs={'class': 'input is-locked', 'readonly': True}),
        )
        self.fields['emplacement_affiche'] = forms.CharField(
            label='Emplacement', required=False,
            widget=forms.TextInput(attrs={'class': 'input is-locked', 'readonly': True}),
        )

    def _init_affectation_choisie(self, immobilisation):
        self._champs_affectation_choisie()
        self.immobilisation = immobilisation
        self.affectation_choisie = None
        self.fields['affectation_id'].error_messages['required'] = (
            'Choisissez d’abord une affectation (bouton Choisir).'
        )
        self.fields['service_affiche'].help_text = 'Utilisez Choisir dans le tableau.'
        self.fields['emplacement_affiche'].help_text = 'Utilisez Choisir dans le tableau.'
        if 'quantite' in self.fields:
            self.fields['quantite'].initial = 1
        aff_id = None
        if self.is_bound:
            aff_id = self.data.get(self.add_prefix('affectation_id'))
        if aff_id and immobilisation is not None:
            source = (
                immobilisation.affectations.filter(pk=aff_id, actif=True)
                .select_related('service', 'emplacement')
                .first()
            )
            if source:
                self.fields['service_affiche'].initial = str(source.service)
                self.fields['emplacement_affiche'].initial = str(source.emplacement)
                if 'quantite' in self.fields:
                    self.fields['quantite'].widget.attrs['max'] = source.quantite
                    self.fields['quantite'].help_text = (
                        f'Quantité à cet emplacement : {source.quantite}.'
                    )

    def clean_affectation_id(self):
        aff_id = self.cleaned_data.get('affectation_id')
        if self.immobilisation is None or aff_id is None:
            return aff_id
        source = self.immobilisation.affectations.filter(pk=aff_id, actif=True).first()
        if source is None:
            raise forms.ValidationError('Cette affectation n’est plus disponible.')
        self.affectation_choisie = source
        return aff_id

    def _appliquer_affectation_choisie(self, cleaned):
        source = getattr(self, 'affectation_choisie', None)
        quantite = cleaned.get('quantite')
        if source is None:
            return cleaned
        if quantite is not None and quantite > source.quantite:
            self.add_error(
                'quantite',
                f'Il n’y a que {source.quantite} unité(s) à cet emplacement.',
            )
        cleaned['service'] = source.service
        cleaned['emplacement'] = source.emplacement
        return cleaned


class CasseForm(_AffectationChoisieMixin, _ActeurMixin, forms.ModelForm):
    """Déclaration d'une casse : service et emplacement choisis depuis une affectation."""

    class Meta:
        model = Casse
        fields = [
            'quantite', 'motif', 'date_dommage',
            'description', 'responsable_dommage', 'par',
        ]
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1, 'class': 'input'}),
            'motif': forms.TextInput(attrs={'class': 'input'}),
            'date_dommage': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'input'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'input'}),
            'responsable_dommage': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Nom de la personne ayant causé le dommage',
            }),
        }

    def __init__(self, *args, immobilisation=None, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_affectation_choisie(immobilisation)
        self.fields['quantite'].label = 'Quantité cassée'
        self.order_fields([
            'affectation_id', 'service_affiche', 'emplacement_affiche',
            'quantite', 'motif', 'date_dommage', 'description',
            'responsable_dommage', 'par',
        ])
        self._init_acteur(request_user)

    def clean_quantite(self):
        quantite = self.cleaned_data.get('quantite')
        if quantite is None or quantite < 1:
            raise forms.ValidationError('La quantité cassée doit être au moins 1.')
        return quantite

    def clean(self):
        return self._appliquer_affectation_choisie(super().clean())


class CasseEvaluationForm(forms.ModelForm):
    """Évaluation d'une casse (décision)."""

    class Meta:
        model = Casse
        fields = ['decision', 'observation']
        widgets = {
            'decision': forms.Select(attrs={'class': 'input'}),
        }


class DeclassementForm(_AffectationChoisieMixin, _ActeurMixin, forms.ModelForm):
    """Demande de déclassement : service et emplacement choisis depuis une affectation."""

    class Meta:
        model = Declassement
        fields = ['quantite', 'motif', 'par']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1, 'class': 'input'}),
            'motif': forms.TextInput(attrs={'class': 'input'}),
        }

    def __init__(self, *args, immobilisation=None, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_affectation_choisie(immobilisation)
        self.fields['quantite'].label = 'Quantité à déclasser'
        self.order_fields([
            'affectation_id', 'service_affiche', 'emplacement_affiche',
            'quantite', 'motif', 'par',
        ])
        self._init_acteur(request_user)

    def clean_quantite(self):
        quantite = self.cleaned_data.get('quantite')
        if quantite is None or quantite < 1:
            raise forms.ValidationError('La quantité à déclasser doit être au moins 1.')
        return quantite

    def clean(self):
        return self._appliquer_affectation_choisie(super().clean())
