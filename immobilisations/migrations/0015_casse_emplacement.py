import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0014_casse_service_quantite_libelles'),
    ]

    operations = [
        migrations.AddField(
            model_name='casse',
            name='emplacement',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='casses',
                to='immobilisations.emplacement',
                verbose_name='emplacement',
            ),
        ),
    ]
