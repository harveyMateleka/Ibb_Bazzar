from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import Inventaire, LigneInventaire, MouvementStock


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = f'{css} input'.strip()

    def clean_date_mouvement(self):
        value = self.cleaned_data.get('date_mouvement')
        if value and timezone.is_naive(value):
            return timezone.make_aware(value)
        return value


class ConnexionForm(StyledFormMixin, AuthenticationForm):
    pass


class EntreeStockForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MouvementStock
        fields = ['article', 'quantite', 'fournisseur', 'reference', 'date_mouvement']
        widgets = {
            'date_mouvement': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_mouvement'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['quantite'].min_value = 1

    def clean_quantite(self):
        quantite = self.cleaned_data['quantite']
        if quantite <= 0:
            raise forms.ValidationError("La quantité d'une entrée doit être positive.")
        return quantite


class SortieStockForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MouvementStock
        fields = [
            'article',
            'quantite',
            'motif',
            'destination',
            'date_mouvement',
            'autorisation_depassement',
        ]
        widgets = {
            'date_mouvement': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_mouvement'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['motif'].required = True

    def clean_quantite(self):
        quantite = self.cleaned_data['quantite']
        if quantite <= 0:
            raise forms.ValidationError('La quantité d’une sortie doit être positive.')
        return quantite


class InventaireForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Inventaire
        fields = ['date_inventaire', 'commentaire']
        widgets = {
            'date_inventaire': forms.DateInput(attrs={'type': 'date'}),
            'commentaire': forms.Textarea(attrs={'rows': 3}),
        }


class LigneInventaireForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LigneInventaire
        fields = ['stock_physique', 'motif']


LigneInventaireFormSet = inlineformset_factory(
    Inventaire,
    LigneInventaire,
    form=LigneInventaireForm,
    extra=0,
    can_delete=False,
)
