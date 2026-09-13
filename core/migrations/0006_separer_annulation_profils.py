from django.db import migrations

ROLES_SANS_ANNULATION = {
    'OPERATEUR',
    'OPERATEUR_COMMANDE',
    'MAGASINIER',
    'VENDEUR',
    'CAISSIER',
    'SERVEUR',
    'CUISINIER',
    'CHARGE_LOGISTIQUE',
    'COMPTABLE',
    'RESPONSABLE_VENDEUR',
    'RESPONSABLE_LOGISTIQUE',
}

ANNULATIONS_RESPONSABLE = {
    'cancel_commande',
    'cancel_vente',
    'cancel_entree',
    'cancel_approvisionnement',
    'cancel_sortie',
}

ANNULATIONS_DIRECTION = ANNULATIONS_RESPONSABLE | {'cancel_facture'}


def ajuster_annulations(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    Permission = apps.get_model('auth', 'Permission')
    cancels = {
        perm.codename: perm
        for perm in Permission.objects.filter(codename__startswith='cancel_')
    }
    if not cancels:
        return

    for role in Role.objects.filter(code__in=ROLES_SANS_ANNULATION, est_systeme=True):
        role.permissions.remove(*cancels.values())

    for code, wanted in (
        ('RESPONSABLE', ANNULATIONS_RESPONSABLE),
        ('DIRECTION', ANNULATIONS_DIRECTION),
    ):
        role = Role.objects.filter(code=code, est_systeme=True).first()
        if role is None:
            continue
        a_ajouter = [cancels[name] for name in wanted if name in cancels]
        if a_ajouter:
            role.permissions.add(*a_ajouter)


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_profils_comptes_existants'),
        ('restauration', '0011_profils_permissions'),
        ('approvisionnement', '0009_profils_permissions'),
        ('boutique', '0015_profils_permissions'),
        ('facturation', '0004_profils_permissions'),
    ]

    operations = [
        migrations.RunPython(ajuster_annulations, migrations.RunPython.noop),
    ]
