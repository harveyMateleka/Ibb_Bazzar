from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from restauration.impression import LARGEUR_TICKET, ImpressionError, envoyer_texte_imprimante


def _montant_compact(valeur):
    nombre = Decimal(valeur).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if nombre == nombre.to_integral_value():
        return str(int(nombre))
    return format(nombre, 'f').rstrip('0').rstrip('.')


def _ligne_detail(plat, qte, pu, pt, largeur=LARGEUR_TICKET):
    col_pt, col_pu, col_qte = 7, 7, 3
    col_plat = max(8, largeur - col_pt - col_pu - col_qte - 3)
    nom = (plat or '')[:col_plat].ljust(col_plat)
    return (
        f'{nom} {str(qte).rjust(col_qte)} '
        f'{str(pu).rjust(col_pu)} {str(pt).rjust(col_pt)}'
    )


def texte_recu(facture, etablissement):
    heure = timezone.localtime(facture.date_facture)
    largeur = LARGEUR_TICKET
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
        _ligne_detail('PLAT', 'QTE', 'PU', 'PT', largeur),
    ])
    for ligne in facture.lignes.all():
        lignes.append(_ligne_detail(
            ligne.designation,
            ligne.quantite,
            _montant_compact(ligne.prix_unitaire),
            _montant_compact(ligne.montant),
            largeur,
        ))
    lignes.append('-' * largeur)
    for devise, total in facture.totaux_par_devise.items():
        moitie = largeur // 2
        lignes.append(
            f'TOTAL {devise}'.ljust(moitie)
            + _montant_compact(total).rjust(largeur - moitie)
        )
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
        compact=True,
    )
