from django.db import migrations, models


def marquer_lignes_deja_envoyees(apps, schema_editor):
    LigneCommande = apps.get_model('restauration', 'LigneCommande')
    LigneCommande.objects.filter(
        commande__statut__in=('VALIDEE', 'SERVIE', 'PAYEE'),
    ).update(imprimee=True)


class Migration(migrations.Migration):

    dependencies = [
        ('restauration', '0011_profils_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='lignecommande',
            name='imprimee',
            field=models.BooleanField(
                default=False,
                help_text='True après un envoi réussi en cuisine, barbecus ou terrasse.',
                verbose_name='envoyée à l’imprimante',
            ),
        ),
        migrations.RunPython(marquer_lignes_deja_envoyees, migrations.RunPython.noop),
    ]
