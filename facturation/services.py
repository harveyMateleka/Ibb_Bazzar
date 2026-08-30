from django.db import transaction

from restauration.models import Commande

from .impression import imprimer_recu
from .models import Etablissement, Facture


@transaction.atomic
def encaisser_et_facturer(commande, utilisateur, mode_paiement):
    """Marque la commande payée, libère la table et émet la facture."""
    commande = Commande.objects.select_for_update().get(pk=commande.pk)
    facture = Facture.objects.filter(commande=commande).first()
    if commande.statut != Commande.Statut.PAYEE:
        commande.encaisser(mode_paiement)
        commande.refresh_from_db()
    if facture is None:
        facture = Facture.creer_depuis_commande(commande, utilisateur)
    return facture


def imprimer_recu_caisse(facture):
    etablissement = Etablissement.actuel()
    if not etablissement.imprimante_caisse:
        return None
    return imprimer_recu(facture, etablissement)
