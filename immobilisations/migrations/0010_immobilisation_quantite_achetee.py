from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0009_remove_immobilisation_fournisseur_casse_date_dommage'),
    ]

    operations = [
        migrations.AddField(
            model_name='immobilisation',
            name='quantite_achetee',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Nombre d’unités acquises.',
                verbose_name='quantité achetée',
            ),
        ),
    ]
