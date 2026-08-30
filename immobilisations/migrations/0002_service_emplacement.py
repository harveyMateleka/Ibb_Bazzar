# Schéma seul : création des référentiels Service / Emplacement et des colonnes
# FK temporaires. La copie des données (0003) et la conversion des colonnes
# (0004) sont volontairement séparées : PostgreSQL refuse un ALTER TABLE tant que
# des événements de trigger FK sont en attente dans la même transaction que des
# écritures.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=150, unique=True, verbose_name='nom')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('actif', models.BooleanField(default=True, verbose_name='actif')),
            ],
            options={
                'verbose_name': 'service',
                'verbose_name_plural': 'services',
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='Emplacement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=150, unique=True, verbose_name='nom')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('actif', models.BooleanField(default=True, verbose_name='actif')),
            ],
            options={
                'verbose_name': 'emplacement',
                'verbose_name_plural': 'emplacements',
                'ordering': ['nom'],
            },
        ),
        migrations.AddField(
            model_name='immobilisation',
            name='service_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='immobilisations', to='immobilisations.service', verbose_name='service'),
        ),
        migrations.AddField(
            model_name='immobilisation',
            name='emplacement_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='immobilisations', to='immobilisations.emplacement', verbose_name='emplacement'),
        ),
        migrations.AddField(
            model_name='affectation',
            name='service_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='affectations', to='immobilisations.service', verbose_name='service'),
        ),
        migrations.AddField(
            model_name='affectation',
            name='emplacement_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='affectations', to='immobilisations.emplacement', verbose_name='emplacement'),
        ),
        migrations.AddField(
            model_name='deplacement',
            name='ancien_service_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='immobilisations.service', verbose_name='ancien service'),
        ),
        migrations.AddField(
            model_name='deplacement',
            name='nouveau_service_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='immobilisations.service', verbose_name='nouveau service'),
        ),
        migrations.AddField(
            model_name='deplacement',
            name='ancien_emplacement_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='immobilisations.emplacement', verbose_name='ancien emplacement'),
        ),
        migrations.AddField(
            model_name='deplacement',
            name='nouvel_emplacement_fk',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='immobilisations.emplacement', verbose_name='nouvel emplacement'),
        ),
    ]
