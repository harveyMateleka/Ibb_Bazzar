from collections import Counter

from django.db import migrations, models
import django.db.models.deletion


def rattacher_emplacements(apps, schema_editor):
    Service = apps.get_model('immobilisations', 'Service')
    Emplacement = apps.get_model('immobilisations', 'Emplacement')
    Immobilisation = apps.get_model('immobilisations', 'Immobilisation')
    Affectation = apps.get_model('immobilisations', 'Affectation')

    fallback, _ = Service.objects.get_or_create(
        nom='Non classé',
        defaults={
            'description': 'Service provisoire pour les emplacements sans rattachement.',
            'actif': True,
        },
    )
    for emp in Emplacement.objects.all():
        compteur = Counter()
        for sid in Immobilisation.objects.filter(
            emplacement_id=emp.pk,
        ).exclude(service_id=None).values_list('service_id', flat=True):
            compteur[sid] += 2
        for sid in Affectation.objects.filter(
            emplacement_id=emp.pk,
        ).exclude(service_id=None).values_list('service_id', flat=True):
            compteur[sid] += 1
        emp.service_id = compteur.most_common(1)[0][0] if compteur else fallback.pk
        emp.save(update_fields=['service_id'])


def detach_emplacements(apps, schema_editor):
    Emplacement = apps.get_model('immobilisations', 'Emplacement')
    Emplacement.objects.update(service=None)


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0010_immobilisation_quantite_achetee'),
    ]

    operations = [
        migrations.AddField(
            model_name='emplacement',
            name='service',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='emplacements',
                to='immobilisations.service',
                verbose_name='service',
            ),
        ),
        migrations.RunPython(rattacher_emplacements, detach_emplacements),
        migrations.AlterField(
            model_name='emplacement',
            name='service',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='emplacements',
                to='immobilisations.service',
                verbose_name='service',
            ),
        ),
        migrations.AlterField(
            model_name='emplacement',
            name='nom',
            field=models.CharField(max_length=150, verbose_name='nom'),
        ),
        migrations.AlterModelOptions(
            name='emplacement',
            options={
                'ordering': ['service__nom', 'nom'],
                'verbose_name': 'emplacement',
                'verbose_name_plural': 'emplacements',
            },
        ),
        migrations.AddConstraint(
            model_name='emplacement',
            constraint=models.UniqueConstraint(
                fields=('service', 'nom'),
                name='immo_emplacement_unique_par_service',
            ),
        ),
    ]
