# DDL seul : suppression du champ `devise` d'ArticleBoutique (la devise est
# désormais portée par VarianteArticle). Dans une transaction propre, sans
# écritures (la copie a été validée par 0007).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('boutique', '0007_copier_devise_article_vers_variantes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='articleboutique',
            name='devise',
        ),
    ]
