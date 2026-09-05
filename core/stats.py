from calendar import monthrange
from datetime import timedelta

from django.utils import timezone

_MOIS = (
    '',
    'Janvier',
    'Février',
    'Mars',
    'Avril',
    'Mai',
    'Juin',
    'Juillet',
    'Août',
    'Septembre',
    'Octobre',
    'Novembre',
    'Décembre',
)


def bornes_deux_mois(jour=None):
    jour = jour or timezone.localdate()
    debut_courant = jour.replace(day=1)
    dernier_precedent = debut_courant - timedelta(days=1)
    debut_precedent = dernier_precedent.replace(day=1)
    _, jours_courant = monthrange(debut_courant.year, debut_courant.month)
    fin_courant = debut_courant + timedelta(days=jours_courant)
    return debut_precedent, debut_courant, fin_courant


def libelle_mois(jour):
    return f'{_MOIS[jour.month]} {jour.year}'


def comparaison_mois(series, jour=None):
    """series: liste de {'label', 'precedent', 'courant'}."""
    debut_precedent, debut_courant, _fin = bornes_deux_mois(jour)
    lignes = []
    for item in series:
        precedent = item.get('precedent') or 0
        courant = item.get('courant') or 0
        if isinstance(precedent, float):
            precedent = round(precedent, 2)
            courant = round(courant or 0, 2)
        ecart = (courant or 0) - (precedent or 0)
        lignes.append({
            'label': item['label'],
            'precedent': precedent,
            'courant': courant,
            'ecart': ecart,
        })
    return {
        'labels': [libelle_mois(debut_precedent), libelle_mois(debut_courant)],
        'series': [
            {'label': ligne['label'], 'values': [ligne['precedent'], ligne['courant']]}
            for ligne in lignes
        ],
        'lignes': lignes,
        'mois_precedent': libelle_mois(debut_precedent),
        'mois_courant': libelle_mois(debut_courant),
    }


def filtrer_periode(queryset, champ, debut, fin):
    nom = champ.split('__')[0]
    try:
        champ_modele = queryset.model._meta.get_field(nom)
        est_date = champ_modele.get_internal_type() == 'DateField'
    except Exception:
        est_date = False
    if est_date:
        return queryset.filter(**{f'{champ}__gte': debut, f'{champ}__lt': fin})
    return queryset.filter(**{
        f'{champ}__date__gte': debut,
        f'{champ}__date__lt': fin,
    })


def compter_entre(queryset, champ, debut, fin):
    return filtrer_periode(queryset, champ, debut, fin).count()
