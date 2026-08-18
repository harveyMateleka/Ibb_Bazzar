from django import forms
from django.forms import inlineformset_factory

from core.permissions import appliquer_contexte

from .models import (
    ArticleBoutique,
    InventaireBoutique,
    LigneInventaireBoutique,
    StockBoutique,
    Vente,
    VenteLigne,
)


class ArticleBoutiqueForm(forms.ModelForm):
    class Meta:
        model = ArticleBoutique
        fields = [
            'code', 'reference', 'designation', 'description', 'type',
            'categorie', 'sous_categorie', 'unite', 'genre',
            'taille', 'couleur', 'marque', 'matiere', 'modele',
            'rayon', 'etagere', 'emplacement',
            'succursale', 'domaine',
            'prix_achat', 'prix_unitaire', 'prix_minimum', 'prix_maximum',
            'statut', 'en_vente',
        ]

    def __init__(self, *args, succursales=None, domaines=None, contexte=None, **kwargs):
        super().__init__(*args, **kwargs)
        if succursales is not None:
            self.fields['succursale'].queryset = succursales
        if domaines is not None:
            self.fields['domaine'].queryset = domaines
        appliquer_contexte(self, contexte)

    def clean(self):
        cleaned = super().clean()
        prix = cleaned.get('prix_unitaire')
        mini = cleaned.get('prix_minimum')
        maxi = cleaned.get('prix_maximum')
        if prix is not None:
            if mini and prix < mini:
                self.add_error(
                    'prix_unitaire',
                    f'Le prix de vente ({prix}) est inférieur au prix minimum ({mini}).',
                )
            if maxi and prix > maxi:
                self.add_error(
                    'prix_unitaire',
                    f'Le prix de vente ({prix}) est supérieur au prix maximum ({maxi}).',
                )
        return cleaned


class StockEntreeForm(forms.Form):
    """Nouvelle entrée en stock boutique (article + quantité + contexte)."""

    article = forms.ModelChoiceField(
        queryset=ArticleBoutique.objects.none(),
        label='Article',
        widget=forms.Select(attrs={'class': 'input'}),
    )
    quantite = forms.IntegerField(
        label='Quantité',
        min_value=1,
        widget=forms.NumberInput(attrs={'min': 1}),
    )
    reference = forms.CharField(
        label='Référence',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'input'}),
    )
    motif = forms.CharField(
        label='Motif',
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'input'}),
    )
    seuil_alerte = forms.IntegerField(
        label='Seuil d’alerte',
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'min': 0}),
        help_text='Laissez vide pour conserver le seuil actuel.',
    )

    def __init__(self, *args, articles=None, **kwargs):
        super().__init__(*args, **kwargs)
        if articles is not None:
            self.fields['article'].queryset = articles


class VenteForm(forms.ModelForm):
    class Meta:
        model = Vente
        fields = ['client', 'succursale', 'domaine', 'type_paiement', 'montant_recu', 'remise']
        widgets = {
            'client': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Nom du client'}),
            'montant_recu': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, succursales=None, domaines=None, contexte=None, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Une vente est rattachée à un client (règle métier).
        self.fields['client'].required = True
        if succursales is not None:
            self.fields['succursale'].queryset = succursales
        if domaines is not None:
            self.fields['domaine'].queryset = domaines
        appliquer_contexte(self, contexte)
        # Remise : autorisée uniquement avec la permission dédiée.
        if not request_user or not request_user.has_perm('boutique.apply_remise'):
            self.fields['remise'].widget.attrs['readonly'] = True
            self.fields['remise'].help_text = 'Remise réservée aux profils autorisés.'


class ArticleBoutiqueSelect(forms.Select):
    """Select d'article : embarque prix normal / min / max sur chaque option.

    Permet au frontend d'afficher le prix normal et le prix minimum de
    l'article sélectionné (et de pré-remplir le prix unitaire)."""

    def __init__(self, attrs=None, prix_par_article=None):
        self.prix_par_article = prix_par_article or {}
        super().__init__(attrs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        # ModelChoiceIteratorValue expose la PK via son attribut .value
        # (int() lève sur cet objet).
        pk = getattr(value, 'value', value)
        try:
            pk = int(pk) if pk else None
        except (TypeError, ValueError):
            pk = None
        if pk and pk in self.prix_par_article:
            normal, mini, maxi = self.prix_par_article[pk]
            option['attrs']['data-prix-normal'] = normal
            option['attrs']['data-prix-min'] = mini
            option['attrs']['data-prix-max'] = maxi
        return option


class VenteLigneForm(forms.ModelForm):
    class Meta:
        model = VenteLigne
        fields = ['article', 'quantite', 'prix_unitaire']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1, 'class': 'input'}),
            'prix_unitaire': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0', 'class': 'input', 'data-prix-ligne': '1'}
            ),
        }

    def __init__(self, *args, succursale=None, domaine=None, **kwargs):
        super().__init__(*args, **kwargs)
        articles = ArticleBoutique.objects.select_related('unite', 'categorie')
        if succursale is not None:
            articles = articles.filter(succursale_id=succursale)
        if domaine is not None:
            articles = articles.filter(domaine_id=domaine)
        self.fields['article'].queryset = articles
        self.fields['article'].required = False
        self.fields['quantite'].required = False
        self.fields['prix_unitaire'].required = False
        # Widget embarquant les prix (normal / min / max) par option.
        prix_par_article = {
            a.pk: (str(a.prix_unitaire), str(a.prix_minimum), str(a.prix_maximum))
            for a in articles
        }
        self.fields['article'].widget = ArticleBoutiqueSelect(
            attrs={'class': 'input', 'data-article-ligne': '1'},
            prix_par_article=prix_par_article,
        )
        # Ré-attacher les choix (le remplacement du widget perd la liaison).
        self.fields['article'].widget.choices = self.fields['article'].choices

    def clean(self):
        cleaned = super().clean()
        article = cleaned.get('article')
        quantite = cleaned.get('quantite')
        prix = cleaned.get('prix_unitaire')
        if article and not quantite:
            self.add_error('quantite', 'La quantité est obligatoire.')
        if quantite and not article:
            self.add_error('article', 'Sélectionnez un article.')
        if article:
            # Prix par défaut : le prix de vente (prix_unitaire) de l'article.
            if prix in (None, ''):
                prix = article.prix_unitaire
                cleaned['prix_unitaire'] = prix
            # Règle des prix : prix_minimum ≤ prix ≤ prix_maximum (plancher/plafond).
            if article.prix_minimum and prix < article.prix_minimum:
                self.add_error(
                    'prix_unitaire',
                    f'Le prix ({prix}) est inférieur au prix minimum '
                    f'({article.prix_minimum}) de {article.code}.',
                )
            if article.prix_maximum and prix > article.prix_maximum:
                self.add_error(
                    'prix_unitaire',
                    f'Le prix ({prix}) est supérieur au prix maximum '
                    f'({article.prix_maximum}) de {article.code}.',
                )
        return cleaned


class BaseVenteLigneFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, succursale=None, domaine=None, **kwargs):
        self.succursale = succursale
        self.domaine = domaine
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['succursale'] = self.succursale
        kwargs['domaine'] = self.domaine
        return super()._construct_form(i, **kwargs)


class EncaissementForm(forms.ModelForm):
    """Montant reçu d'une vente (modifiable sur la page de détail)."""

    class Meta:
        model = Vente
        fields = ['montant_recu']
        widgets = {
            'montant_recu': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'input'}),
        }


VenteLigneFormSet = inlineformset_factory(
    Vente,
    VenteLigne,
    form=VenteLigneForm,
    formset=BaseVenteLigneFormSet,
    extra=3,
    can_delete=True,
    min_num=0,
)


class InventaireForm(forms.ModelForm):
    """Nouvel inventaire : date, périmètre (COMPLET / UN_ARTICLE) + contexte."""

    portee = forms.ChoiceField(
        label='Périmètre',
        choices=InventaireBoutique.Portee.choices,
        initial=InventaireBoutique.Portee.COMPLET,
    )
    article = forms.ModelChoiceField(
        label='Article',
        queryset=ArticleBoutique.objects.none(),
        required=False,
    )

    class Meta:
        model = InventaireBoutique
        fields = ['date_inventaire', 'succursale', 'domaine', 'commentaire']
        widgets = {
            'date_inventaire': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date'},
            ),
        }

    def __init__(self, *args, succursales=None, domaines=None, contexte=None, articles=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_inventaire'].input_formats = ['%Y-%m-%d']
        if succursales is not None:
            self.fields['succursale'].queryset = succursales
        if domaines is not None:
            self.fields['domaine'].queryset = domaines
        if articles is not None:
            self.fields['article'].queryset = articles
        appliquer_contexte(self, contexte)

    def clean(self):
        cleaned = super().clean()
        portee = cleaned.get('portee')
        if portee == 'UN_ARTICLE' and not cleaned.get('article'):
            self.add_error('article', 'Sélectionnez l’article à inventorier.')
        return cleaned


class LigneInventaireBoutiqueForm(forms.ModelForm):
    class Meta:
        model = LigneInventaireBoutique
        fields = ['stock_physique', 'motif']
        widgets = {
            'stock_physique': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['stock_physique'].required = False
        self.fields['motif'].required = False

    def clean(self):
        cleaned = super().clean()
        physique = cleaned.get('stock_physique')
        if physique is None and self.instance.pk:
            physique = self.instance.stock_physique
            cleaned['stock_physique'] = physique
        ecart = (physique or 0) - (self.instance.stock_systeme if self.instance.pk else 0)
        motif = cleaned.get('motif')
        if ecart != 0 and not motif:
            self.add_error(
                'motif',
                f'Un motif est obligatoire pour un écart de {ecart:+d}.',
            )
        return cleaned


class BaseLigneInventaireFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.empty_permitted = False


LigneInventaireFormSet = inlineformset_factory(
    InventaireBoutique,
    LigneInventaireBoutique,
    form=LigneInventaireBoutiqueForm,
    formset=BaseLigneInventaireFormSet,
    extra=0,
    can_delete=False,
    min_num=1,
)
