from django.db import migrations


def creer_profils(apps, schema_editor):
    AuthUser = apps.get_model('auth', 'User')
    Profil = apps.get_model('core', 'User')
    for compte in AuthUser.objects.all():
        Profil.objects.get_or_create(compte_id=compte.pk)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_user_fonction'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(creer_profils, noop),
    ]
