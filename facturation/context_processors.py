from django.db.utils import OperationalError, ProgrammingError

from .models import Etablissement


class _EtablissementParDefaut:
    nom_societe = 'IBBS BAZAR'
    sigle = 'IBBS'
    logo = None
    contact = ''
    email = ''
    adresse = ''
    imprimante_caisse = ''
    message_recu = 'Merci de votre visite'

    @property
    def logo_url(self):
        from django.conf import settings

        return f'{settings.MEDIA_URL}logo/logo.jpeg'


def etablissement(request):
    try:
        return {'etablissement': Etablissement.actuel()}
    except (OperationalError, ProgrammingError):
        return {'etablissement': _EtablissementParDefaut()}
