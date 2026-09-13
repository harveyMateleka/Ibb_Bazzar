from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0011_emplacement_appartient_au_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='affectation',
            name='quantite',
            field=models.PositiveIntegerField(default=1, verbose_name='nombre à affecter'),
        ),
        migrations.AddField(
            model_name='affectation',
            name='commentaire',
            field=models.TextField(blank=True, verbose_name='commentaire'),
        ),
    ]
