from decimal import Decimal

from django import forms
from django.forms import formset_factory, inlineformset_factory

from core.permissions import appliquer_contexte

from .models import (
    ArticleBoutique,
    CategorieBoutique,
    InventaireBoutique,
    LigneInventaireBoutique,
    TypeTissuArticle,
    UniteBoutique,
    VarianteArticle,
    Vente,
    VenteLigne,
)


class ArticleBoutiqueForm(forms.ModelForm):
    """Création de l'article parent (identification seule)."""

    class Meta:
        model = ArticleBoutique
        fields = ['code', 'designation', 'succursale', 'domaine']

    def __init__(self, *args, succursales=None, domaines=None, contexte=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.contexte = contexte
        if succursales is not None:
            self.fields['succursale'].queryset = succursales
        if domaines is not None:
            self.fields['domaine'].queryset = domaines
        appliquer_contexte(self, contexte)

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get('code')
        if not code:
            return cleaned
        # Succursale/domaine du contexte (champs verrouillés = non soumis).
        succursale = cleaned.get('succursale') or (self.contexte or {}).get('succursale')
        domaine = cleaned.get('domaine') or (self.contexte or {}).get('domaine')
        if succursale:
            qs = ArticleBoutique.objects.filter(code=code, succursale=succursale, domaine=domaine)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    'code',
                    f'Le code {code} existe déjà pour un article de cette succursale. '
                    'Choisissez un autre code.',
                )
        return cleaned


class StockEntreeForm(forms.Form):
    """Nouvelle entrée en stock : sélection de l'article parent, création de la
    variante (caractéristiques + prix + seuil) et quantité — le tout soumis d'un bloc."""

    article = forms.ModelChoiceField(
        queryset=ArticleBoutique.objects.none(),
        label='Article parent',
        widget=forms.Select(attrs={'class': 'input'}),
    )
    genre = forms.ChoiceField(label='Genre', required=False,
                              choices=VarianteArticle.Genre.choices,
                              widget=forms.Select(attrs={'class': 'input'}))
    taille = forms.ChoiceField(label='Taille', required=False,
                               choices=VarianteArticle.Taille.choices,
                               widget=forms.Select(attrs={'class': 'input'}))
    couleur = forms.ChoiceField(label='Couleur', required=False,
                                choices=VarianteArticle.Couleur.choices,
                                widget=forms.Select(attrs={'class': 'input'}))
    marque = forms.CharField(label='Marque', required=False, max_length=50,
                             widget=forms.TextInput(attrs={'class': 'input'}))
    modele = forms.CharField(label='Modèle', required=False, max_length=50,
                             widget=forms.TextInput(attrs={'class': 'input'}))
    categorie = forms.ModelChoiceField(
        label='Catégorie', required=False, queryset=None,
        widget=forms.Select(attrs={'class': 'input'}))
    unite = forms.ModelChoiceField(
        label='Unité', required=False, queryset=None,
        widget=forms.Select(attrs={'class': 'input'}))
    type_tissu = forms.ModelChoiceField(
        label='Type de tissu', required=False,
        queryset=TypeTissuArticle.objects.filter(actif=True),
        empty_label='— Aucun —',
        widget=forms.Select(attrs={'class': 'input'}))
    rayon = forms.CharField(label='Rayon', required=False, max_length=50,
                            widget=forms.TextInput(attrs={'class': 'input'}))
    etagere = forms.CharField(label='Étagère', required=False, max_length=50,
                              widget=forms.TextInput(attrs={'class': 'input'}))
    emplacement = forms.CharField(label='Emplacement', required=False, max_length=50,
                                  widget=forms.TextInput(attrs={'class': 'input'}))
    devise = forms.ChoiceField(
        label='Devise', choices=VarianteArticle.Devise.choices,
        initial=VarianteArticle.Devise.FC,
        widget=forms.Select(attrs={'class': 'input'}))
    prix_achat = forms.DecimalField(label='Prix d’achat', required=False, max_digits=12, decimal_places=2)
    prix_unitaire = forms.DecimalField(label='Prix unitaire', required=False, max_digits=12, decimal_places=2)
    prix_minimum = forms.DecimalField(label='Prix minimum', required=False, max_digits=12, decimal_places=2)
    seuil_alerte = forms.IntegerField(label='Seuil d’alerte', required=False, min_value=0)
    quantite = forms.IntegerField(label='Quantité', min_value=1,
                                  widget=forms.NumberInput(attrs={'min': 1}))

    def __init__(self, *args, articles=None, categories=None, unites=None, **kwargs):
        super().__init__(*args, **kwargs)
        if articles is not None:
            self.fields['article'].queryset = articles
        self.fields['categorie'].queryset = categories or CategorieBoutique.objects.filter(actif=True)
        self.fields['unite'].queryset = unites or UniteBoutique.objects.all()

    def clean(self):
        cleaned = super().clean()
        prix = cleaned.get('prix_unitaire')
        mini = cleaned.get('prix_minimum')
        if prix is not None and mini and prix < mini:
            self.add_error('prix_unitaire', f'Le prix de vente ({prix}) est inférieur au prix minimum ({mini}).')
        return cleaned


class VenteForm(forms.ModelForm):
    """Interface unique de vente : entête (client, paiement, remise, montant reçu).

    Succursale et domaine sont déterminés côté backend (contexte utilisateur),
    jamais demandés ni acceptés depuis l'input."""

    class Meta:
        model = Vente
        fields = ['client', 'type_paiement', 'remise', 'montant_recu']
        widgets = {
            'client': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Nom du client'}),
            'type_paiement': forms.Select(attrs={'class': 'input'}),
            'montant_recu': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'input'}),
        }

    def __init__(self, *args, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].required = True
        self.fields['remise'].required = False
        self.fields['montant_recu'].required = False
        if not request_user or not request_user.has_perm('boutique.apply_remise'):
            self.fields['remise'].widget.attrs['readonly'] = True
            self.fields['remise'].help_text = 'Remise réservée aux profils autorisés.'


class VarianteArticleSelect(forms.Select):
    """Select de variante : embarque prix normal / min / max sur chaque option."""

    def __init__(self, attrs=None, prix_par_variante=None):
        self.prix_par_variante = prix_par_variante or {}
        super().__init__(attrs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        pk = getattr(value, 'value', value)
        try:
            pk = int(pk) if pk else None
        except (TypeError, ValueError):
            pk = None
        if pk and pk in self.prix_par_variante:
            normal, mini, maxi = self.prix_par_variante[pk]
            option['attrs']['data-prix-normal'] = normal
            option['attrs']['data-prix-min'] = mini
            option['attrs']['data-prix-max'] = maxi
        return option


class VenteLigneForm(forms.ModelForm):
    class Meta:
        model = VenteLigne
        fields = ['variante', 'quantite', 'prix_unitaire']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1, 'class': 'input'}),
            'prix_unitaire': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0', 'class': 'input', 'data-prix-ligne': '1'}),
        }

    def __init__(self, *args, succursale=None, domaine=None, **kwargs):
        super().__init__(*args, **kwargs)
        variantes = VarianteArticle.objects.select_related('article', 'unite', 'categorie', 'type_tissu')
        if succursale is not None:
            variantes = variantes.filter(article__succursale_id=succursale)
        if domaine is not None:
            variantes = variantes.filter(article__domaine_id=domaine)
        self.fields['variante'].queryset = variantes
        self.fields['variante'].required = False
        self.fields['quantite'].required = False
        self.fields['prix_unitaire'].required = False
        prix_par_variante = {
            v.pk: (str(v.prix_unitaire), str(v.prix_minimum), str(v.prix_maximum))
            for v in variantes
        }
        self.fields['variante'].widget = VarianteArticleSelect(
            attrs={'class': 'input', 'data-article-ligne': '1'},
            prix_par_variante=prix_par_variante,
        )
        self.fields['variante'].widget.choices = self.fields['variante'].choices

    def clean(self):
        cleaned = super().clean()
        variante = cleaned.get('variante')
        quantite = cleaned.get('quantite')
        prix = cleaned.get('prix_unitaire')
        if variante and not quantite:
            self.add_error('quantite', 'La quantité est obligatoire.')
        if quantite and not variante:
            self.add_error('variante', 'Sélectionnez une variante.')
        if variante:
            if prix in (None, ''):
                prix = variante.prix_unitaire
                cleaned['prix_unitaire'] = prix
            if variante.prix_minimum and prix < variante.prix_minimum:
                self.add_error(
                    'prix_unitaire',
                    f'Cette variante ne peut pas être vendue en dessous de son prix '
                    f'minimum autorisé ({variante.prix_minimum}).')
            if prix > variante.prix_unitaire:
                self.add_error(
                    'prix_unitaire',
                    f'Le prix de vente de {variante.article.code} ({variante.label}) '
                    f'est supérieur au prix de référence autorisé ({variante.prix_unitaire}).')
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


VenteLigneFormSet = inlineformset_factory(
    Vente,
    VenteLigne,
    form=VenteLigneForm,
    formset=BaseVenteLigneFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
)


class BaseLigneVenteSaisieFormSet(forms.BaseFormSet):
    """Formset autonome des lignes de vente (saisie dans l'interface unique)."""

    def __init__(self, *args, succursale=None, domaine=None, **kwargs):
        self.succursale = succursale
        self.domaine = domaine
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['succursale'] = self.succursale
        kwargs['domaine'] = self.domaine
        return super()._construct_form(i, **kwargs)

    def lignes_cleaned(self):
        """Lignes (variante, quantite, prix_unitaire) à soumettre."""
        lignes = []
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            variante = form.cleaned_data.get('variante')
            quantite = form.cleaned_data.get('quantite')
            if variante and quantite:
                lignes.append((
                    variante,
                    quantite,
                    form.cleaned_data.get('prix_unitaire') or variante.prix_unitaire,
                ))
        return lignes


LigneVenteSaisieFormSet = formset_factory(
    VenteLigneForm,
    formset=BaseLigneVenteSaisieFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
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
            'date_inventaire': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
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
            self.add_error('motif', f'Un motif est obligatoire pour un écart de {ecart:+d}.')
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
