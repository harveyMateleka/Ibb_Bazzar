from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0012_affectation_quantite_commentaire'),
    ]

    operations = [
        migrations.AddField(
            model_name='deplacement',
            name='quantite',
            field=models.PositiveIntegerField(default=1, verbose_name='quantité à déplacer'),
        ),
    ]
