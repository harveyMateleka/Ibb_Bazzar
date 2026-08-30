from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def rattraper_factures(apps, schema_editor):
    Commande = apps.get_model('restauration', 'Commande')
    Facture = apps.get_model('facturation', 'Facture')
    LigneFacture = apps.get_model('facturation', 'LigneFacture')
    Etablissement = apps.get_model('facturation', 'Etablissement')
    etablissement = Etablissement.objects.filter(pk=1).first()
    if etablissement is None:
        return
    annee = timezone.localdate().year
    prefixe = f'FAC-{annee}-'
    for commande in (
        Commande.objects.filter(statut='PAYEE')
        .select_related('table', 'table__salle')
        .prefetch_related('lignes')
        .order_by('date_cloture', 'pk')
    ):
        if Facture.objects.filter(commande_id=commande.pk).exists():
            continue
        dernier = (
            Facture.objects.filter(numero__startswith=prefixe)
            .order_by('-numero')
            .first()
        )
        sequence = int(dernier.numero.rsplit('-', 1)[-1]) + 1 if dernier else 1
        if commande.emporter:
            emplacement = 'À emporter'
        elif commande.table_id:
            emplacement = f'Table {commande.table.numero}'
        else:
            emplacement = '—'
        facture = Facture.objects.create(
            numero=f'{prefixe}{sequence:04d}',
            commande=commande,
            date_facture=commande.date_cloture or timezone.now(),
            utilisateur_id=commande.utilisateur_id,
            mode_paiement=commande.mode_paiement or 'ESPECES',
            table_liberee=emplacement,
            nom_societe=etablissement.nom_societe,
            sigle=etablissement.sigle,
            contact=etablissement.contact,
            adresse=' '.join((etablissement.adresse or '').split()),
        )
        lignes = []
        for ligne in commande.lignes.exclude(statut='ANNULEE'):
            designation = ligne.designation or 'Plat'
            quantite = ligne.quantite
            prix = ligne.prix_unitaire
            montant = (prix or Decimal('0.00')) * quantite
            lignes.append(
                LigneFacture(
                    facture=facture,
                    designation=designation,
                    quantite=quantite,
                    prix_unitaire=prix,
                    devise=ligne.devise or 'CDF',
                    montant=montant,
                )
            )
        if lignes:
            LigneFacture.objects.bulk_create(lignes)


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0002_etablissement_initial'),
        ('restauration', '0010_stock_a_validation'),
    ]

    operations = [
        migrations.RunPython(rattraper_factures, migrations.RunPython.noop),
    ]
