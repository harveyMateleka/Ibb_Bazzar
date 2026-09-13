import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0015_casse_emplacement'),
    ]

    operations = [
        migrations.AddField(
            model_name='declassement',
            name='service',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='declassements',
                to='immobilisations.service',
                verbose_name='service d’affectation',
            ),
        ),
        migrations.AddField(
            model_name='declassement',
            name='emplacement',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='declassements',
                to='immobilisations.emplacement',
                verbose_name='emplacement',
            ),
        ),
        migrations.AddField(
            model_name='declassement',
            name='quantite',
            field=models.PositiveIntegerField(
                default=1,
                verbose_name='quantité à déclasser',
            ),
        ),
    ]
