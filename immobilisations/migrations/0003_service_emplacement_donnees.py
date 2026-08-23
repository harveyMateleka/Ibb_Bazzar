# Copie des données : crée une ligne Service / Emplacement par valeur distincte
# des anciens champs texte et affecte les colonnes FK temporaires. Migration à
# part (pas de DDL ici) pour ne pas laisser d'événements de trigger FK en attente.

from django.db import migrations


def _entite_ou_create(Entite, nom):
    return Entite.objects.get_or_create(nom=nom)[0]


def _copier(queryset, champ_texte, champ_fk, Entite):
    for obj in queryset.all():
        valeur = getattr(obj, champ_texte)
        if valeur:
            setattr(obj, champ_fk, _entite_ou_create(Entite, valeur))
            obj.save(update_fields=[champ_fk])


def forward(apps, schema_editor):
    Service = apps.get_model('immobilisations', 'Service')
    Emplacement = apps.get_model('immobilisations', 'Emplacement')
    Immobilisation = apps.get_model('immobilisations', 'Immobilisation')
    Affectation = apps.get_model('immobilisations', 'Affectation')
    Deplacement = apps.get_model('immobilisations', 'Deplacement')

    _copier(Immobilisation.objects, 'service', 'service_fk', Service)
    _copier(Immobilisation.objects, 'emplacement', 'emplacement_fk', Emplacement)
    _copier(Affectation.objects, 'service', 'service_fk', Service)
    _copier(Affectation.objects, 'emplacement', 'emplacement_fk', Emplacement)
    _copier(Deplacement.objects, 'ancien_service', 'ancien_service_fk', Service)
    _copier(Deplacement.objects, 'nouveau_service', 'nouveau_service_fk', Service)
    _copier(Deplacement.objects, 'ancien_emplacement', 'ancien_emplacement_fk', Emplacement)
    _copier(Deplacement.objects, 'nouvel_emplacement', 'nouvel_emplacement_fk', Emplacement)


def backward(apps, schema_editor):
    """Restaure les anciens champs texte depuis les noms des référentiels."""
    Immobilisation = apps.get_model('immobilisations', 'Immobilisation')
    Affectation = apps.get_model('immobilisations', 'Affectation')
    Deplacement = apps.get_model('immobilisations', 'Deplacement')

    def _recopier(queryset, champ_fk, champ_texte):
        for obj in queryset.all():
            entite = getattr(obj, champ_fk)
            if entite is not None:
                setattr(obj, champ_texte, entite.nom)
                obj.save(update_fields=[champ_texte])

    _recopier(Immobilisation.objects, 'service_fk', 'service')
    _recopier(Immobilisation.objects, 'emplacement_fk', 'emplacement')
    _recopier(Affectation.objects, 'service_fk', 'service')
    _recopier(Affectation.objects, 'emplacement_fk', 'emplacement')
    _recopier(Deplacement.objects, 'ancien_service_fk', 'ancien_service')
    _recopier(Deplacement.objects, 'nouveau_service_fk', 'nouveau_service')
    _recopier(Deplacement.objects, 'ancien_emplacement_fk', 'ancien_emplacement')
    _recopier(Deplacement.objects, 'nouvel_emplacement_fk', 'nouvel_emplacement')


class Migration(migrations.Migration):

    dependencies = [
        ('immobilisations', '0002_service_emplacement'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
