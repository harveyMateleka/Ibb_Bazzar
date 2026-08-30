from django.utils import timezone

from restauration.impression import ImpressionError, envoyer_texte_imprimante


def texte_recu(facture, etablissement):
    heure = timezone.localtime(facture.date_facture)
    largeur = 32
    lignes = [
        (etablissement.nom_societe or facture.nom_societe or 'IBBS BAZAR').center(largeur),
    ]
    if etablissement.sigle or facture.sigle:
        lignes.append((etablissement.sigle or facture.sigle).center(largeur))
    if facture.adresse:
        lignes.append(facture.adresse[:largeur])
    if facture.contact:
        lignes.append(facture.contact[:largeur])
    lignes.extend([
        '-' * largeur,
        f'Reçu {facture.numero}',
        f'Cmd {facture.commande.numero}',
        f'{facture.table_liberee}'[:largeur],
        heure.strftime('%d/%m/%Y %H:%M'),
        '-' * largeur,
    ])
    for ligne in facture.lignes.all():
        lignes.append(f'{ligne.quantite} x {ligne.designation}'[:largeur])
        montant = f'{ligne.montant} {ligne.devise}'
        lignes.append(montant.rjust(largeur))
    lignes.append('-' * largeur)
    for devise, total in facture.totaux_par_devise.items():
        lignes.append(f'TOTAL {devise}'.ljust(16) + f'{total}'.rjust(16))
    lignes.append(f'Paiement : {facture.get_mode_paiement_display()}')
    message = etablissement.message_recu or 'Merci de votre visite'
    lignes.extend(['-' * largeur, message.center(largeur), ''])
    return '\r\n'.join(lignes)


def imprimer_recu(facture, etablissement):
    if not etablissement.imprimante_caisse:
        raise ImpressionError('Aucune imprimante caisse enregistrée.')
    return envoyer_texte_imprimante(
        etablissement.imprimante_caisse,
        texte_recu(facture, etablissement),
    )
