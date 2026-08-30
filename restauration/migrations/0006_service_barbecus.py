from django.db import migrations, models


def creer_imprimante_barbecus(apps, schema_editor):
    Imprimante = apps.get_model('restauration', 'Imprimante')
    Imprimante.objects.get_or_create(
        nom='Barbecus',
        defaults={'service': 'BARBECUS', 'nom_systeme': 'Barbecus'},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('restauration', '0005_lignecommande_description_plat_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='imprimante',
            name='service',
            field=models.CharField(
                choices=[
                    ('CUISINE', 'Cuisine'),
                    ('BAR', 'Bar'),
                    ('BARBECUS', 'Barbecus'),
                ],
                max_length=10,
                verbose_name='service',
            ),
        ),
        migrations.AlterField(
            model_name='imprimante',
            name='nom_systeme',
            field=models.CharField(
                help_text='Nom de l’imprimante telle qu’elle apparaît sur le poste (cuisine, bar ou barbecus).',
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
                    ('BAR', 'Bar'),
                    ('BARBECUS', 'Barbecus'),
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
                    ('BAR', 'Bar'),
                    ('BARBECUS', 'Barbecus'),
                ],
                default='CUISINE',
                help_text='Cuisine, bar ou barbecus : détermine où la ligne s’affiche après validation.',
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
                    'Bar : augmentée automatiquement par les sorties magasin. '
                    'Barbecus : alimenté par les sorties de vivres frais. '
                    'Cuisine : saisie des plats préparés sur l’écran Cuisine. '
                    'Diminuée à la commande.'
                ),
                verbose_name='quantité disponible',
            ),
        ),
        migrations.RunPython(creer_imprimante_barbecus, migrations.RunPython.noop),
    ]
