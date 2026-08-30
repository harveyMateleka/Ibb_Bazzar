from django.db import migrations, models
from django.db.models import F


def restituer_stock_commandes_ouvertes(apps, schema_editor):
    Commande = apps.get_model('restauration', 'Commande')
    Plat = apps.get_model('restauration', 'Plat')
    for commande in Commande.objects.filter(statut='OUVERTE', stock_consomme=False):
        for ligne in commande.lignes.exclude(statut='ANNULEE'):
            if ligne.quantite:
                Plat.objects.filter(pk=ligne.plat_id).update(
                    quantite=F('quantite') + ligne.quantite
                )


class Migration(migrations.Migration):

    dependencies = [
        ('restauration', '0009_fusion_bar_terrasse'),
    ]

    operations = [
        migrations.RunPython(restituer_stock_commandes_ouvertes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='plat',
            name='quantite',
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    'Terrasse : augmentée automatiquement par les sorties magasin (bar inclus). '
                    'Cuisine et barbecus : saisie des plats préparés sur l’écran du poste. '
                    'Diminuée à la validation de la commande.'
                ),
                verbose_name='quantité disponible',
            ),
        ),
    ]
