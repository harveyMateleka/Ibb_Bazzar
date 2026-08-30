import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('approvisionnement', '0008_rename_article_produit'),
        ('restauration', '0007_service_terrasse'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='compositionplat',
            name='composition_unique_plat_article',
        ),
        migrations.RenameField(
            model_name='compositionplat',
            old_name='article',
            new_name='produit',
        ),
        migrations.AlterField(
            model_name='compositionplat',
            name='produit',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='compositions_plats',
                to='approvisionnement.produit',
                verbose_name='produit',
            ),
        ),
        migrations.AlterField(
            model_name='compositionplat',
            name='quantite',
            field=models.PositiveIntegerField(
                help_text='Quantité de produit consommée pour une portion du plat.',
                verbose_name='quantité',
            ),
        ),
        migrations.AddConstraint(
            model_name='compositionplat',
            constraint=models.UniqueConstraint(
                fields=('plat', 'produit'),
                name='composition_unique_plat_produit',
            ),
        ),
    ]
