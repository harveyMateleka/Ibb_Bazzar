from django import forms

from .impression import lister_imprimantes_windows
from .models import Commande, Imprimante, Plat, Serveur, Table, imprimante_par_defaut


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = f'{css} input'.strip()


class CommandeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Commande
        fields = ['source', 'reference_bon', 'serveur', 'table', 'emporter', 'commentaire']
        widgets = {
            'commentaire': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tables_occupees = Commande.objects.filter(
            statut__in=Commande.STATUTS_ACTIFS,
            table__isnull=False,
        ).values_list('table_id', flat=True)
        self.fields['table'].queryset = Table.objects.select_related('salle').exclude(
            pk__in=tables_occupees
        )
        self.fields['table'].required = False
        self.fields['emporter'].label = 'Commande à emporter'
        self.fields['source'].label = 'Origine de la saisie'
        self.fields['serveur'].queryset = Serveur.objects.filter(actif=True)
        self.fields['serveur'].required = True
        self.fields['serveur'].empty_label = 'Sélectionnez un serveur'
        self.fields['serveur'].label = 'Serveur'
        self.fields['serveur'].help_text = (
            'Liste des serveurs enregistrés dans Paramètres → Serveurs. '
            'Utilisez la recherche de la liste pour trouver un nom.'
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('emporter'):
            cleaned['table'] = None
        elif not cleaned.get('table'):
            self.add_error('table', 'Choisissez une table ou cochez « à emporter ».')
        if cleaned.get('source') == Commande.Source.BON_PAPIER and not (cleaned.get('reference_bon') or '').strip():
            self.add_error(
                'reference_bon',
                'La référence du bon papier doit être conservée.',
            )
        if not cleaned.get('serveur'):
            self.add_error('serveur', 'Choisissez le serveur de cette commande.')
        return cleaned


class EncaissementForm(StyledFormMixin, forms.Form):
    mode_paiement = forms.ChoiceField(
        label='Mode de paiement',
        choices=Commande.ModePaiement.choices,
    )


class AnnulationForm(StyledFormMixin, forms.Form):
    motif = forms.CharField(
        label='Motif d’annulation',
        max_length=250,
        widget=forms.Textarea(attrs={'rows': 3}),
    )


class ImprimanteAdminForm(forms.ModelForm):
    class Meta:
        model = Imprimante
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        noms = lister_imprimantes_windows()
        actuel = ''
        if self.instance.pk:
            actuel = self.instance.nom_systeme or ''
        if actuel and actuel not in noms:
            noms = [actuel] + noms
        if noms:
            self.fields['nom_systeme'] = forms.ChoiceField(
                label='Nom de l’imprimante Windows',
                choices=[(nom, nom) for nom in noms],
                help_text=(
                    'Nom exact tel qu’il apparaît dans Windows (Paramètres → Imprimantes). '
                    'C’est cette imprimante qui recevra automatiquement les tickets du service.'
                ),
            )
            if actuel:
                self.fields['nom_systeme'].initial = actuel
        else:
            self.fields['nom_systeme'].help_text = (
                'Saisissez le nom exact de l’imprimante Windows du poste '
                '(cuisine, barbecus ou terrasse).'
            )


class PlatAdminForm(forms.ModelForm):
    class Meta:
        model = Plat
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['imprimante'].queryset = Imprimante.objects.all()
        self.fields['imprimante'].required = True
        self.fields['imprimante'].help_text = (
            'Imprimante du même service que le plat. Un plat terrasse n’imprime qu’à la terrasse, '
            'un plat cuisine à la cuisine, un plat barbecus au barbecus.'
        )
        service = self.initial.get('service') or getattr(self.instance, 'service', None)
        if self.data.get('service'):
            service = self.data.get('service')
        if service and not (self.instance.imprimante_id if self.instance.pk else None):
            defaut = imprimante_par_defaut(service)
            if defaut:
                self.fields['imprimante'].initial = defaut.pk

    def clean(self):
        cleaned = super().clean()
        service = cleaned.get('service')
        imprimante = cleaned.get('imprimante')
        if service and not imprimante:
            imprimante = imprimante_par_defaut(service)
            cleaned['imprimante'] = imprimante
        if imprimante and service and imprimante.service != service:
            self.add_error(
                'imprimante',
                'Choisissez une imprimante du même service que le plat (cuisine, barbecus ou terrasse).',
            )
        if service and not cleaned.get('imprimante'):
            self.add_error(
                'imprimante',
                'Enregistrez d’abord une imprimante pour ce service dans Paramètres → Imprimantes.',
            )
        return cleaned
