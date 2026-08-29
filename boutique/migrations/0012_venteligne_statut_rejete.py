# Données : le statut de ligne « annulée » devient « rejetée » (compréhension
# du traitement par le responsable). Migration de données isolée de tout DDL
# (pattern du projet) : les lignes existantes `ANNULEE` sont converties en
# `REJETEE`, le changement de choix étant géré par une migration séparée.
from django.db import migrations


def convertir_statut_ligne_annulee_en_rejetee(apps, schema_editor):
    VenteLigne = apps.get_model('boutique', 'VenteLigne')
    VenteLigne.objects.filter(statut_ligne='ANNULEE').update(statut_ligne='REJETEE')


def annuler_conversion(apps, schema_editor):
    VenteLigne = apps.get_model('boutique', 'VenteLigne')
    VenteLigne.objects.filter(statut_ligne='REJETEE').update(statut_ligne='ANNULEE')


class Migration(migrations.Migration):

    dependencies = [
        ('boutique', '0011_venteligne_date_decision_venteligne_decide_par_and_more'),
    ]

    operations = [
        migrations.RunPython(convertir_statut_ligne_annulee_en_rejetee, annuler_conversion),
    ]
