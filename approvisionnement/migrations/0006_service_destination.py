import django.db.models.deletion
from django.db import migrations, models


def lier_services(apps, schema_editor):
    BonSortie = apps.get_model('approvisionnement', 'BonSortie')
    Service = apps.get_model('approvisionnement', 'Service')
    for bon in BonSortie.objects.exclude(destination_ancienne='').exclude(
        destination_ancienne__isnull=True
    ):
        nom = (bon.destination_ancienne or '').strip()
        if not nom:
            continue
        service, _ = Service.objects.get_or_create(nom=nom)
        bon.destination = service
        bon.save(update_fields=['destination'])


class Migration(migrations.Migration):

    dependencies = [
        ('approvisionnement', '0005_journal_approvisionnement'),
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('nom', models.CharField(max_length=150, unique=True, verbose_name='nom')),
            ],
            options={
                'verbose_name': 'service',
                'verbose_name_plural': 'services',
                'ordering': ['nom'],
            },
        ),
        migrations.RenameField(
            model_name='bonsortie',
            old_name='destination',
            new_name='destination_ancienne',
        ),
        migrations.AddField(
            model_name='bonsortie',
            name='destination',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bons_sortie',
                to='approvisionnement.service',
                verbose_name='service',
            ),
        ),
        migrations.RunPython(lier_services, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='bonsortie',
            name='destination_ancienne',
        ),
    ]
