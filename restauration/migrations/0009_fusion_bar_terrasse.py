from django.db import migrations, models


def transferer_bar_vers_terrasse(apps, schema_editor):
    for model_name in ('Imprimante', 'Plat', 'LigneCommande'):
        Model = apps.get_model('restauration', model_name)
        Model.objects.filter(service='BAR').update(service='TERRASSE')


class Migration(migrations.Migration):

    dependencies = [
        ('restauration', '0008_rename_article_produit'),
    ]

    operations = [
        migrations.RunPython(transferer_bar_vers_terrasse, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='imprimante',
            name='service',
            field=models.CharField(
                choices=[
                    ('CUISINE', 'Cuisine'),
                    ('BARBECUS', 'Barbecus'),
                    ('TERRASSE', 'Terrasse'),
                ],
                max_length=10,
                verbose_name='service',
            ),
        ),
        migrations.AlterField(
            model_name='imprimante',
            name='nom_systeme',
            field=models.CharField(
                help_text='Nom de l’imprimante telle qu’elle apparaît sur le poste (cuisine, barbecus ou terrasse).',
                max_length=150,
                verbose_name='nom de l’imprimante',
            ),
        ),
        migrations.AlterField(
            model_name='lignecommande',
            name='service',
            field=models.CharField(
                blank=True,
                choices=[
                    ('CUISINE', 'Cuisine'),
                    ('BARBECUS', 'Barbecus'),
                    ('TERRASSE', 'Terrasse'),
                ],
                max_length=10,
                verbose_name='destination',
            ),
        ),
        migrations.AlterField(
            model_name='plat',
            name='service',
            field=models.CharField(
                choices=[
                    ('CUISINE', 'Cuisine'),
                    ('BARBECUS', 'Barbecus'),
                    ('TERRASSE', 'Terrasse'),
                ],
                default='CUISINE',
                help_text='Cuisine, barbecus ou terrasse : détermine où la ligne s’affiche après validation.',
                max_length=10,
                verbose_name='service',
            ),
        ),
        migrations.AlterField(
            model_name='plat',
            name='quantite',
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    'Terrasse : augmentée automatiquement par les sorties magasin (bar inclus). '
                    'Barbecus : alimenté par les sorties de vivres frais. '
                    'Cuisine : saisie des plats préparés sur l’écran Cuisine. '
                    'Diminuée à la commande.'
                ),
                verbose_name='quantité disponible',
            ),
        ),
    ]
