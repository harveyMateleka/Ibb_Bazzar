from django.conf import settings
from django.db import migrations


def creer_etablissement(apps, schema_editor):
    Etablissement = apps.get_model('facturation', 'Etablissement')
    objet, _cree = Etablissement.objects.get_or_create(
        pk=1,
        defaults={
            'nom_societe': 'IBBS BAZAR',
            'sigle': 'IBBS',
            'message_recu': 'Merci de votre visite',
        },
    )
    logo = settings.BASE_DIR / 'media' / 'logo' / 'logo.jpeg'
    if logo.exists() and not objet.logo:
        objet.logo = 'logo/logo.jpeg'
        objet.save(update_fields=['logo'])


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(creer_etablissement, migrations.RunPython.noop),
    ]
