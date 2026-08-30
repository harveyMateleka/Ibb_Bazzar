"""Tags de template réutilisables pour le module Boutique."""

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """Reconstruit la query string en remplaçant/ajoutant des paramètres,
    en conservant les filtres déjà actifs."""
    request = context.get('request')
    qs = request.GET.copy() if request else {}
    for cle, valeur in kwargs.items():
        if valeur is None:
            qs.pop(cle, None)
        else:
            qs[cle] = str(valeur)
    return qs.urlencode()


@register.filter
def page_window(page_obj, radius=2):
    """Numéros de page autour de la page courante (fenêtre pour la pagination)."""
    paginator = page_obj.paginator
    debut = max(1, page_obj.number - radius)
    fin = min(paginator.num_pages, page_obj.number + radius)
    return range(debut, fin + 1)
