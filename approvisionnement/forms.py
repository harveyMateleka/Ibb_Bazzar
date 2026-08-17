from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import (
    Article,
    BonApprovisionnement,
    BonSortie,
    Inventaire,
    LigneApprovisionnement,
    LigneInventaire,
    LigneSortie,
    MouvementStock,
    Service,
)


class ArticlePortionsSelect(forms.Select):
    def __init__(self, *args, portions_map=None, **kwargs):
        self.portions_map = portions_map or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        raw = value.value if hasattr(value, 'value') else value
        pk = str(raw) if raw not in (None, '') else ''
        option['attrs']['data-nombre-portions'] = str(self.portions_map.get(pk, 0))
        return option


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


class BonApprovisionnementForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BonApprovisionnement
        fields = ['date_approvisionnement', 'fournisseur', 'reference', 'commentaire']
        widgets = {
            'date_approvisionnement': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'commentaire': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_approvisionnement'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean_date_approvisionnement(self):
        value = self.cleaned_data.get('date_approvisionnement')
        if value and timezone.is_naive(value):
            return timezone.make_aware(value)
        return value


class LigneApprovisionnementForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LigneApprovisionnement
        fields = ['article', 'quantite']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, articles_exclus=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['article'].required = False
        self.fields['quantite'].required = False
        self.fields['article'].widget.attrs['data-article-ligne'] = '1'
        articles = Article.objects.all()
        if articles_exclus:
            articles = articles.exclude(pk__in=articles_exclus)
        self.fields['article'].queryset = articles

    def clean(self):
        cleaned = super().clean()
        article = cleaned.get('article')
        quantite = cleaned.get('quantite')
        if article and not quantite:
            self.add_error('quantite', 'La quantité est obligatoire.')
        if quantite and not article:
            self.add_error('article', 'Sélectionnez un article.')
        return cleaned

    def clean_quantite(self):
        quantite = self.cleaned_data.get('quantite')
        if self.cleaned_data.get('article') and (quantite is None or quantite <= 0):
            raise forms.ValidationError('La quantité doit être positive.')
        return quantite


class BaseLigneApprovisionnementFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, articles_exclus=None, **kwargs):
        self.articles_exclus = set(articles_exclus or [])
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['articles_exclus'] = self.articles_exclus
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        deja_choisis = set(self.articles_exclus)
        for form in self.forms:
            if not getattr(form, 'cleaned_data', None):
                continue
            article = form.cleaned_data.get('article')
            if not article:
                continue
            if article.pk in deja_choisis:
                form.add_error(
                    'article',
                    'Ce produit est déjà présent sur une autre ligne.',
                )
            else:
                deja_choisis.add(article.pk)


LigneApprovisionnementFormSet = inlineformset_factory(
    BonApprovisionnement,
    LigneApprovisionnement,
    form=LigneApprovisionnementForm,
    formset=BaseLigneApprovisionnementFormSet,
    extra=4,
    can_delete=False,
    min_num=0,
)


class LigneValidationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LigneApprovisionnement
        fields = ['quantite']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1}),
        }

    def clean_quantite(self):
        quantite = self.cleaned_data.get('quantite')
        if quantite is None or quantite <= 0:
            raise forms.ValidationError('La quantité doit être positive.')
        return quantite


LigneValidationFormSet = inlineformset_factory(
    BonApprovisionnement,
    LigneApprovisionnement,
    form=LigneValidationForm,
    extra=0,
    can_delete=True,
    min_num=0,
)


class BonSortieForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BonSortie
        fields = [
            'date_sortie',
            'motif',
            'destination',
            'commentaire',
        ]
        widgets = {
            'date_sortie': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'commentaire': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_sortie'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['motif'].required = True
        self.fields['destination'].required = True
        self.fields['destination'].queryset = Service.objects.all()
        self.fields['destination'].empty_label = 'Sélectionnez un service'
        self.fields['destination'].label = 'Service'

    def clean_date_sortie(self):
        value = self.cleaned_data.get('date_sortie')
        if value and timezone.is_naive(value):
            return timezone.make_aware(value)
        return value


class AutorisationDepassementForm(StyledFormMixin, forms.Form):
    username = forms.CharField(
        label='Nom d’utilisateur',
        max_length=150,
        widget=forms.TextInput(attrs={'autocomplete': 'username'}),
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get('username')
        password = cleaned.get('password')
        if not username or not password:
            return cleaned
        utilisateur = authenticate(
            self.request,
            username=username,
            password=password,
        )
        if utilisateur is None or not utilisateur.is_active:
            raise forms.ValidationError(
                'Identifiant ou mot de passe incorrect. '
                'L’autorisation du propriétaire n’a pas été accordée.'
            )
        cleaned['user'] = utilisateur
        return cleaned


class LigneSortieForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LigneSortie
        fields = ['article', 'quantite', 'nombre_portions']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1}),
            'nombre_portions': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, portions_map=None, articles_exclus=None, **kwargs):
        super().__init__(*args, **kwargs)
        articles = Article.objects.select_related('categorie', 'unite')
        portions_map = portions_map or {
            str(article.pk): article.categorie.nombre_portions
            for article in articles
        }
        exclus = set(articles_exclus or [])
        if self.instance.pk and self.instance.article_id:
            exclus.discard(self.instance.article_id)
        if exclus:
            articles = articles.exclude(pk__in=exclus)
        self.fields['article'].required = False
        self.fields['quantite'].required = False
        self.fields['nombre_portions'].required = False
        self.fields['article'].empty_label = 'Sélectionnez un article'
        self.fields['article'].widget = ArticlePortionsSelect(
            portions_map=portions_map,
            attrs={'class': 'input', 'data-article-ligne': '1'},
        )
        self.fields['article'].queryset = articles
        self.fields['nombre_portions'].widget.attrs.update(
            {
                'min': '0',
                'placeholder': 'Nb portions',
            }
        )

    def _ligne_incomplete(self):
        article = None
        quantite = None
        if self.is_bound:
            article = self.data.get(self.add_prefix('article'))
            quantite = self.data.get(self.add_prefix('quantite'))
        elif hasattr(self, 'cleaned_data'):
            article = self.cleaned_data.get('article')
            quantite = self.cleaned_data.get('quantite')
        return not article and not quantite

    def has_changed(self):
        if not self.instance.pk and self._ligne_incomplete():
            return False
        return super().has_changed()

    def clean(self):
        cleaned = super().clean()
        article = cleaned.get('article')
        quantite = cleaned.get('quantite')
        portions = cleaned.get('nombre_portions') or 0
        if not article and not quantite:
            cleaned['nombre_portions'] = 0
            return cleaned
        if article and not quantite:
            self.add_error('quantite', 'La quantité est obligatoire.')
        if quantite and not article:
            self.add_error('article', 'Sélectionnez un article.')
        if article and article.exige_portions and portions <= 0:
            self.add_error(
                'nombre_portions',
                'Indiquez le nombre de portions pour cette catégorie de vivres frais.',
            )
        if article and not article.exige_portions:
            cleaned['nombre_portions'] = 0
        return cleaned


class BaseLigneSortieFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, articles_exclus=None, **kwargs):
        self.articles_exclus = set(articles_exclus or [])
        self.portions_map = {
            str(article.pk): article.categorie.nombre_portions
            for article in Article.objects.select_related('categorie')
        }
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['portions_map'] = self.portions_map
        kwargs['articles_exclus'] = self.articles_exclus
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        deja_choisis = set()
        for form in self.forms:
            if not getattr(form, 'cleaned_data', None):
                continue
            if form.cleaned_data.get('DELETE'):
                continue
            article = form.cleaned_data.get('article')
            if not article:
                continue
            if article.pk in deja_choisis:
                form.add_error(
                    'article',
                    'Ce produit est déjà présent sur une autre ligne.',
                )
            else:
                deja_choisis.add(article.pk)

    def save(self, commit=True):
        instances = super().save(commit=False)
        saved = []
        for obj in instances:
            if obj is None or not obj.article_id or not obj.quantite:
                continue
            if commit:
                obj.save()
            saved.append(obj)
        if commit:
            for obj in self.deleted_objects:
                obj.delete()
            self.save_m2m()
        return saved


LigneSortieFormSet = inlineformset_factory(
    BonSortie,
    LigneSortie,
    form=LigneSortieForm,
    formset=BaseLigneSortieFormSet,
    extra=4,
    can_delete=False,
    min_num=0,
)


class LigneSortieValidationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LigneSortie
        fields = ['quantite', 'nombre_portions']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 1}),
            'nombre_portions': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        article = getattr(self.instance, 'article', None)
        if not article or not article.exige_portions:
            self.fields['nombre_portions'].widget = forms.HiddenInput()
            self.fields['nombre_portions'].required = False

    def clean_quantite(self):
        quantite = self.cleaned_data.get('quantite')
        if quantite is None or quantite <= 0:
            raise forms.ValidationError('La quantité doit être positive.')
        return quantite

    def clean(self):
        cleaned = super().clean()
        article = getattr(self.instance, 'article', None)
        portions = cleaned.get('nombre_portions') or 0
        if article and article.exige_portions and portions <= 0:
            self.add_error(
                'nombre_portions',
                'Indiquez le nombre de portions pour cette catégorie de vivres frais.',
            )
        if article and not article.exige_portions:
            cleaned['nombre_portions'] = 0
        return cleaned


LigneSortieValidationFormSet = inlineformset_factory(
    BonSortie,
    LigneSortie,
    form=LigneSortieValidationForm,
    extra=0,
    can_delete=True,
    min_num=0,
)


class InventaireForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Inventaire
        fields = ['date_inventaire', 'commentaire']
        widgets = {
            'date_inventaire': forms.DateInput(
                attrs={'type': 'date'},
                format='%Y-%m-%d',
            ),
            'commentaire': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_inventaire'].input_formats = ['%Y-%m-%d']


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


class RapportPeriodeForm(StyledFormMixin, forms.Form):
    TYPE_ENTREE = 'ENTREE'
    TYPE_SORTIE = 'SORTIE'
    TYPE_INVENTAIRE = 'INVENTAIRE'
    TYPE_CHOICES = [
        ('', 'Sélectionnez'),
        (TYPE_ENTREE, 'Entrée'),
        (TYPE_SORTIE, 'Sortie'),
        (TYPE_INVENTAIRE, 'Inventaire'),
    ]

    date_debut = forms.DateField(
        label='Du',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    date_fin = forms.DateField(
        label='Au',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    type_rapport = forms.ChoiceField(
        label='Type',
        choices=TYPE_CHOICES,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_debut'].input_formats = ['%Y-%m-%d']
        self.fields['date_fin'].input_formats = ['%Y-%m-%d']

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('date_debut')
        fin = cleaned.get('date_fin')
        if debut and fin and debut > fin:
            raise forms.ValidationError(
                'La date de début doit précéder ou être égale à la date de fin.'
            )
        return cleaned
