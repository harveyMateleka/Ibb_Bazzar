from django import template

from approvisionnement.models import BonApprovisionnement, LigneApprovisionnement

register = template.Library()


@register.inclusion_tag('approvisionnement/_entree_onglets.html', takes_context=True)
def entree_onglets(context):
    request = context.get('request')
    url_name = ''
    if request is not None and getattr(request, 'resolver_match', None):
        url_name = request.resolver_match.url_name or ''
    nb_en_attente = LigneApprovisionnement.objects.filter(
        bon__statut=BonApprovisionnement.Statut.BROUILLON
    ).count()
    return {
        'nb_en_attente': nb_en_attente,
        'onglet_validation': 'validation' in url_name,
    }
