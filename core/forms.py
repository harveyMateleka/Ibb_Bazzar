from django import forms

from approvisionnement.models import Service

from .models import Domaine, Role, Succursale, User


class UtilisateurForm(forms.ModelForm):
    """Création d'un utilisateur : compte Django + profil + rôles."""

    username = forms.CharField(label='Identifiant', max_length=150)
    first_name = forms.CharField(label='Prénom', max_length=150, required=False)
    last_name = forms.CharField(label='Nom', max_length=150, required=False)
    email = forms.EmailField(label='E-mail', required=False)
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirmation du mot de passe',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    succursale = forms.ModelChoiceField(
        queryset=Succursale.objects.filter(actif=True),
        label='Succursale',
        required=True,
    )
    domaine = forms.ModelChoiceField(
        queryset=Domaine.objects.all(),
        label='Domaine d’activité',
        required=True,
    )
    role_affectation = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        label='Rôle dans ce périmètre',
        required=False,
    )

    class Meta:
        model = User
        fields = ['telephone', 'fonction', 'roles']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        services = [(service.nom, service.nom) for service in Service.objects.order_by('nom')]
        self.fields['fonction'] = forms.ChoiceField(
            label='Fonction / service',
            required=False,
            choices=[('', 'Sélectionnez un service')] + services,
            help_text='Liste issue de la table des services.',
        )
        self.fields['fonction'].widget.attrs.update({'class': 'input'})

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        password2 = cleaned.get('password2')
        if password != password2:
            self.add_error('password2', 'Les deux mots de passe ne correspondent pas.')
        return cleaned
