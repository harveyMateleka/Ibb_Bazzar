from django import forms

from .models import Domaine, Role, Succursale, User


class UtilisateurForm(forms.ModelForm):
    """Création d'un utilisateur : profil + rôles + affectation + mot de passe."""

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
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'telephone', 'fonction', 'roles',
        ]

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        password2 = cleaned.get('password2')
        if password != password2:
            self.add_error('password2', 'Les deux mots de passe ne correspondent pas.')
        return cleaned
