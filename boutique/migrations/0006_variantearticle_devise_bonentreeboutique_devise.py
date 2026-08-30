# Schéma seul : ajout du champ `devise` sur VarianteArticle (la devise vit au
# niveau du produit tarifé) et sur BonEntreeBoutique (l'entrée transporte la
# devise jusqu'à la création de la variante). La copie des données (0007) et la
# suppression de `ArticleBoutique.devise` (0008) sont séparées pour éviter le
# « pending trigger events » de PostgreSQL (écritures et DDL dans des transactions
# distinctes).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('boutique', '0005_bonentreeboutique_commentaire_vente_commentaire_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='variantearticle',
            name='devise',
            field=models.CharField(choices=[('FC', 'Franc congolais (FC)'), ('USD', 'Dollar américain (USD)'), ('EUR', 'Euro (EUR)')], default='FC', max_length=3, verbose_name='devise'),
        ),
        migrations.AddField(
            model_name='bonentreeboutique',
            name='devise',
            field=models.CharField(choices=[('FC', 'Franc congolais (FC)'), ('USD', 'Dollar américain (USD)'), ('EUR', 'Euro (EUR)')], default='FC', max_length=3, verbose_name='devise'),
        ),
    ]
