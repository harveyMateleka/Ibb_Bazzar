from django.db import migrations, models


def creer_terrasse(apps, schema_editor):
    Imprimante = apps.get_model('restauration', 'Imprimante')
    Imprimante.objects.get_or_create(
        nom='Terrasse',
        defaults={'service': 'TERRASSE', 'nom_systeme': 'Terrasse'},
    )
    Service = apps.get_model('approvisionnement', 'Service')
    Service.objects.get_or_create(nom='Terrasse')


class Migration(migrations.Migration):

    dependencies = [
        ('approvisionnement', '0007_inventaire_unique_par_jour'),
        ('restauration', '0006_service_barbecus'),
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
                help_text='Nom de l’imprimante telle qu’elle apparaît sur le poste (cuisine, bar, barbecus ou terrasse).',
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
                    ('BAR', 'Bar'),
                    ('BARBECUS', 'Barbecus'),
                    ('TERRASSE', 'Terrasse'),
                ],
                default='CUISINE',
                help_text='Cuisine, bar, barbecus ou terrasse : détermine où la ligne s’affiche après validation.',
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
                    'Bar et terrasse : augmentée automatiquement par les sorties magasin. '
                    'Barbecus : alimenté par les sorties de vivres frais. '
                    'Cuisine : saisie des plats préparés sur l’écran Cuisine. '
                    'Diminuée à la commande.'
                ),
                verbose_name='quantité disponible',
            ),
        ),
        migrations.RunPython(creer_terrasse, migrations.RunPython.noop),
    ]
