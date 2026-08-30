# Conversion finale : supprime les anciennes colonnes texte et renomme les
# colonnes FK temporaires vers leur nom définitif. DDL seul, dans une transaction
# propre (les écritures de 0003 ont été validées avant).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0003_service_emplacement_donnees'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='immobilisation',
            name='service',
        ),
        migrations.RemoveField(
            model_name='immobilisation',
            name='emplacement',
        ),
        migrations.RemoveField(
            model_name='affectation',
            name='service',
        ),
        migrations.RemoveField(
            model_name='affectation',
            name='emplacement',
        ),
        migrations.RemoveField(
            model_name='deplacement',
            name='ancien_service',
        ),
        migrations.RemoveField(
            model_name='deplacement',
            name='nouveau_service',
        ),
        migrations.RemoveField(
            model_name='deplacement',
            name='ancien_emplacement',
        ),
        migrations.RemoveField(
            model_name='deplacement',
            name='nouvel_emplacement',
        ),
        migrations.RenameField(
            model_name='immobilisation',
            old_name='service_fk',
            new_name='service',
        ),
        migrations.RenameField(
            model_name='immobilisation',
            old_name='emplacement_fk',
            new_name='emplacement',
        ),
        migrations.RenameField(
            model_name='affectation',
            old_name='service_fk',
            new_name='service',
        ),
        migrations.RenameField(
            model_name='affectation',
            old_name='emplacement_fk',
            new_name='emplacement',
        ),
        migrations.RenameField(
            model_name='deplacement',
            old_name='ancien_service_fk',
            new_name='ancien_service',
        ),
        migrations.RenameField(
            model_name='deplacement',
            old_name='nouveau_service_fk',
            new_name='nouveau_service',
        ),
        migrations.RenameField(
            model_name='deplacement',
            old_name='ancien_emplacement_fk',
            new_name='ancien_emplacement',
        ),
        migrations.RenameField(
            model_name='deplacement',
            old_name='nouvel_emplacement_fk',
            new_name='nouvel_emplacement',
        ),
    ]
