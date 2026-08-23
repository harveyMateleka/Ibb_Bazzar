# Copie des données : chaque variante (et bon d'entrée) hérite de la devise de
# son article, avant la suppression du champ sur ArticleBoutique (0008).

from django.db import migrations


def forward(apps, schema_editor):
    ArticleBoutique = apps.get_model('boutique', 'ArticleBoutique')
    VarianteArticle = apps.get_model('boutique', 'VarianteArticle')
    BonEntreeBoutique = apps.get_model('boutique', 'BonEntreeBoutique')

    for article in ArticleBoutique.objects.all():
        VarianteArticle.objects.filter(article_id=article.pk).update(devise=article.devise)
        BonEntreeBoutique.objects.filter(article_id=article.pk).update(devise=article.devise)


def backward(apps, schema_editor):
    # Le champ article.devise est recréé par la migration précédente (reverse) ;
    # on restaure la devise des articles depuis leurs variantes (best-effort).
    ArticleBoutique = apps.get_model('boutique', 'ArticleBoutique')
    VarianteArticle = apps.get_model('boutique', 'VarianteArticle')

    for article in ArticleBoutique.objects.all():
        devise = (
            VarianteArticle.objects.filter(article_id=article.pk)
            .exclude(devise='')
            .values_list('devise', flat=True)
            .first()
        )
        if devise:
            article.devise = devise
            article.save(update_fields=['devise'])


class Migration(migrations.Migration):

    dependencies = [
        ('boutique', '0006_variantearticle_devise_bonentreeboutique_devise'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
