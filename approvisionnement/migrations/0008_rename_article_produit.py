from django.db import migrations, models
import django.db.models.deletion


def renommer_permissions_et_textes(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    ct = ContentType.objects.filter(
        app_label='approvisionnement', model='produit'
    ).first()
    if ct:
        mapping = {
            'add_article': 'add_produit',
            'change_article': 'change_produit',
            'delete_article': 'delete_produit',
            'view_article': 'view_produit',
        }
        for old, new in mapping.items():
            Permission.objects.filter(content_type=ct, codename=old).update(codename=new)
        for perm in Permission.objects.filter(content_type=ct):
            name = (perm.name or '').replace('article', 'produit').replace('Article', 'Produit')
            if name != perm.name:
                perm.name = name
                perm.save(update_fields=['name'])

    Fonctionnalite = apps.get_model('approvisionnement', 'Fonctionnalite')
    remplacements = (
        ("d'articles", "de produits"),
        ("d’articles", "de produits"),
        ("cet article", "ce produit"),
        ("Cet article", "Ce produit"),
        ("l'article", "le produit"),
        ("l’article", "le produit"),
        ("d'article", "de produit"),
        ("d’article", "de produit"),
        ("un article", "un produit"),
        ("Un article", "Un produit"),
        ("des articles", "des produits"),
        ("Des articles", "Des produits"),
        ("les articles", "les produits"),
        ("Les articles", "Les produits"),
        ('Articles', 'Produits'),
        ('articles', 'produits'),
        ('Article', 'Produit'),
        ('article', 'produit'),
    )
    champs = [
        'libelle',
        'comportement_attendu',
        'donnees_principales',
        'regles_gestion',
    ]
    for obj in Fonctionnalite.objects.all():
        changed = False
        for champ in champs:
            valeur = getattr(obj, champ) or ''
            nouvelle = valeur
            for ancien, nouveau in remplacements:
                nouvelle = nouvelle.replace(ancien, nouveau)
            if nouvelle != valeur:
                setattr(obj, champ, nouvelle)
                changed = True
        if changed:
            obj.save(update_fields=champs)


class Migration(migrations.Migration):

    dependencies = [
        ('approvisionnement', '0007_inventaire_unique_par_jour'),
        ('restauration', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(old_name='Article', new_name='Produit'),
        migrations.AlterModelOptions(
            name='produit',
            options={
                'ordering': ['code'],
                'verbose_name': 'produit',
                'verbose_name_plural': 'produits',
            },
        ),
        migrations.AlterUniqueTogether(
            name='ligneinventaire',
            unique_together=set(),
        ),
        migrations.RenameField(
            model_name='alertestock',
            old_name='article',
            new_name='produit',
        ),
        migrations.RenameField(
            model_name='approvisionnementligne',
            old_name='article',
            new_name='produit',
        ),
        migrations.RenameField(
            model_name='ligneapprovisionnement',
            old_name='article',
            new_name='produit',
        ),
        migrations.RenameField(
            model_name='ligneinventaire',
            old_name='article',
            new_name='produit',
        ),
        migrations.RenameField(
            model_name='lignesortie',
            old_name='article',
            new_name='produit',
        ),
        migrations.RenameField(
            model_name='mouvementstock',
            old_name='article',
            new_name='produit',
        ),
        migrations.AlterUniqueTogether(
            name='ligneinventaire',
            unique_together={('inventaire', 'produit')},
        ),
        migrations.AlterField(
            model_name='produit',
            name='categorie',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='produits',
                to='approvisionnement.categorie',
                verbose_name='catégorie',
            ),
        ),
        migrations.AlterField(
            model_name='produit',
            name='unite',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='produits',
                to='approvisionnement.unite',
                verbose_name='unité',
            ),
        ),
        migrations.AlterField(
            model_name='alertestock',
            name='produit',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='alertes',
                to='approvisionnement.produit',
                verbose_name='produit',
            ),
        ),
        migrations.AlterField(
            model_name='approvisionnementligne',
            name='produit',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='lignes_journal_approvisionnement',
                to='approvisionnement.produit',
                verbose_name='produit',
            ),
        ),
        migrations.AlterField(
            model_name='ligneapprovisionnement',
            name='produit',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='lignes_approvisionnement',
                to='approvisionnement.produit',
                verbose_name='produit',
            ),
        ),
        migrations.AlterField(
            model_name='ligneinventaire',
            name='produit',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='lignes_inventaire',
                to='approvisionnement.produit',
                verbose_name='produit',
            ),
        ),
        migrations.AlterField(
            model_name='lignesortie',
            name='produit',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='lignes_sortie',
                to='approvisionnement.produit',
                verbose_name='produit',
            ),
        ),
        migrations.AlterField(
            model_name='mouvementstock',
            name='produit',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='mouvements',
                to='approvisionnement.produit',
                verbose_name='produit',
            ),
        ),
        migrations.RunPython(renommer_permissions_et_textes, migrations.RunPython.noop),
    ]
