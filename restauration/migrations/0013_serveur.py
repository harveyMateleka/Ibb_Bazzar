from django.db import migrations, models
import django.db.models.deletion


def lier_serveurs_existants(apps, schema_editor):
    Commande = apps.get_model('restauration', 'Commande')
    Serveur = apps.get_model('restauration', 'Serveur')
    cache = {}
    for commande in Commande.objects.exclude(serveur='').exclude(serveur__isnull=True):
        nom = (commande.serveur or '').strip()
        if not nom:
            continue
        if nom not in cache:
            cache[nom] = Serveur.objects.create(nom=nom[:100], prenom='')
        commande.serveur_fiche = cache[nom]
        commande.save(update_fields=['serveur_fiche'])


class Migration(migrations.Migration):
    dependencies = [
        ('restauration', '0012_lignecommande_imprimee'),
    ]

    operations = [
        migrations.CreateModel(
            name='Serveur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, verbose_name='nom')),
                ('prenom', models.CharField(blank=True, max_length=100, verbose_name='prénom')),
                ('actif', models.BooleanField(default=True, verbose_name='actif')),
            ],
            options={
                'verbose_name': 'serveur',
                'verbose_name_plural': 'serveurs',
                'ordering': ['nom', 'prenom'],
            },
        ),
        migrations.AddConstraint(
            model_name='serveur',
            constraint=models.UniqueConstraint(fields=('nom', 'prenom'), name='serveur_unique_nom_prenom'),
        ),
        migrations.AddField(
            model_name='commande',
            name='serveur_fiche',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='commandes',
                to='restauration.serveur',
                verbose_name='serveur',
            ),
        ),
        migrations.RunPython(lier_serveurs_existants, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='commande',
            name='serveur',
        ),
        migrations.RenameField(
            model_name='commande',
            old_name='serveur_fiche',
            new_name='serveur',
        ),
    ]
