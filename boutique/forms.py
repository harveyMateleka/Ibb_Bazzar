from django import forms
from django.forms import inlineformset_factory

from approvisionnement.models import Article
from core.permissions import appliquer_contexte

from .models import ArticleBoutique, Vente, VenteLigne


class VenteForm(forms.ModelForm):
    class Meta:
        model = Vente
        fields = ['succursale', 'domaine', 'type_paiement', 'montant_recu', 'remise']

    def __init__(self, *args, succursales=None, domaines=None, contexte=None, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if succursales is not None:
            self.fields['succursale'].queryset = succursales
        if domaines is not None:
            self.fields['domaine'].queryset = domaines
        appliquer_contexte(self, contexte)
        # Remise : autorisée uniquement avec la permission dédiée.
        if not request_user or not request_user.has_perm('boutique.apply_remise'):
            self.fields['remise'].widget.attrs['readonly'] = True
            self.fields['remise'].help_text = 'Remise réservée aux profils autorisés.'


class VenteLigneForm(forms.ModelForm):
    class Meta:
        model = VenteLigne
        fields = ['article', 'quantite', 'prix_unitaire']
        widgets = {
            'prix_unitaire': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0', 'data-prix-ligne': '1'}
            ),
        }

    def __init__(self, *args, succursale=None, domaine=None, **kwargs):
        super().__init__(*args, **kwargs)
        articles = Article.objects.select_related('infos_boutique', 'unite')
        if succursale is not None:
            articles = articles.filter(succursale_id=succursale)
        if domaine is not None:
            articles = articles.filter(domaine_id=domaine)
        self.fields['article'].queryset = articles
        self.fields['article'].required = False
        self.fields['quantite'].required = False
        self.fields['prix_unitaire'].required = False
        self.fields['article'].widget.attrs['data-article-ligne'] = '1'

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
            infos = ArticleBoutique.objects.filter(article_id=article.pk).first()
            # Prix par défaut : le prix de vente de l'article.
            if prix in (None, ''):
                prix = infos.prix_vente if infos else 0
                cleaned['prix_unitaire'] = prix
            # Règle prix_limite : impossible de vendre sous le prix plancher.
            if infos and infos.prix_limite and prix < infos.prix_limite:
                self.add_error(
                    'prix_unitaire',
                    f'Le prix ({prix}) est inférieur à la limite ({infos.prix_limite}) '
                    f'de {article.code}.',
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


VenteLigneFormSet = inlineformset_factory(
    Vente,
    VenteLigne,
    form=VenteLigneForm,
    formset=BaseVenteLigneFormSet,
    extra=3,
    can_delete=True,
    min_num=0,
)
