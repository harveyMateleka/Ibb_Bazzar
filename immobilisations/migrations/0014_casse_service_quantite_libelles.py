import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0013_deplacement_quantite'),
    ]

    operations = [
        migrations.AddField(
            model_name='casse',
            name='service',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='casses',
                to='immobilisations.service',
                verbose_name='service d’affectation',
            ),
        ),
        migrations.AddField(
            model_name='casse',
            name='quantite',
            field=models.PositiveIntegerField(default=1, verbose_name='quantité cassée'),
        ),
        migrations.AlterField(
            model_name='casse',
            name='motif',
            field=models.CharField(max_length=200, verbose_name='cause'),
        ),
        migrations.AlterField(
            model_name='casse',
            name='description',
            field=models.TextField(blank=True, verbose_name='commentaire'),
        ),
    ]
