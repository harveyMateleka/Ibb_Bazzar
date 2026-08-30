from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from restauration.models import Commande, LigneCommande, Plat


class Etablissement(models.Model):
    nom_societe = models.CharField('nom de la société', max_length=150)
    sigle = models.CharField('sigle', max_length=40, blank=True)
    logo = models.ImageField('logo', upload_to='etablissement/', blank=True)
    contact = models.CharField('contact', max_length=80, blank=True)
    email = models.EmailField('e-mail', blank=True)
    adresse = models.TextField('adresse', blank=True)
    imprimante_caisse = models.CharField(
        'imprimante caisse',
        max_length=150,
        blank=True,
        help_text='Nom Windows de l’imprimante 80 mm qui imprime le reçu client.',
    )
    message_recu = models.CharField(
        'message du reçu',
        max_length=200,
        blank=True,
        default='Merci de votre visite',
    )

    class Meta:
        verbose_name = 'établissement'
        verbose_name_plural = 'établissement'

    def __str__(self):
        return self.nom_societe or self.sigle or 'Établissement'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return

    @classmethod
    def actuel(cls):
        objet, _cree = cls.objects.get_or_create(
            pk=1,
            defaults={
                'nom_societe': 'IBBS BAZAR',
                'sigle': 'IBBS',
                'message_recu': 'Merci de votre visite',
            },
        )
        return objet

    @property
    def logo_url(self):
        if self.logo:
            return self.logo.url
        return f'{settings.MEDIA_URL}logo/logo.jpeg'


class Facture(models.Model):
    numero = models.CharField('numéro', max_length=20, unique=True, editable=False)
    commande = models.OneToOneField(
        Commande,
        on_delete=models.PROTECT,
        related_name='facture',
        verbose_name='commande',
    )
    date_facture = models.DateTimeField('date', default=timezone.now)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='factures',
        verbose_name='caissier',
    )
    mode_paiement = models.CharField(
        'mode de paiement',
        max_length=12,
        choices=Commande.ModePaiement.choices,
    )
    table_liberee = models.CharField('table libérée', max_length=150, blank=True)
    nom_societe = models.CharField('société', max_length=150)
    sigle = models.CharField('sigle', max_length=40, blank=True)
    contact = models.CharField('contact', max_length=80, blank=True)
    adresse = models.CharField('adresse', max_length=250, blank=True)

    class Meta:
        verbose_name = 'facture'
        verbose_name_plural = 'factures'
        ordering = ['-date_facture']

    def __str__(self):
        return self.numero

    @classmethod
    def prochain_numero(cls):
        annee = timezone.localdate().year
        prefixe = f'FAC-{annee}-'
        dernier = (
            cls.objects.select_for_update()
            .filter(numero__startswith=prefixe)
            .order_by('-numero')
            .first()
        )
        sequence = int(dernier.numero.rsplit('-', 1)[-1]) + 1 if dernier else 1
        return f'{prefixe}{sequence:04d}'

    @property
    def totaux_par_devise(self):
        totaux = {}
        for ligne in self.lignes.all():
            devise = ligne.devise or Plat.Devise.CDF
            totaux[devise] = totaux.get(devise, Decimal('0.00')) + ligne.montant
        return totaux

    @property
    def total(self):
        return sum((ligne.montant for ligne in self.lignes.all()), Decimal('0.00'))

    @classmethod
    def creer_depuis_commande(cls, commande, utilisateur):
        etablissement = Etablissement.actuel()
        with transaction.atomic():
            facture = cls.objects.create(
                numero=cls.prochain_numero(),
                commande=commande,
                date_facture=commande.date_cloture or timezone.now(),
                utilisateur=utilisateur,
                mode_paiement=commande.mode_paiement,
                table_liberee=commande.nom_emplacement,
                nom_societe=etablissement.nom_societe,
                sigle=etablissement.sigle,
                contact=etablissement.contact,
                adresse=' '.join((etablissement.adresse or '').split()),
            )
            lignes = [
                LigneFacture(
                    facture=facture,
                    designation=ligne.libelle,
                    quantite=ligne.quantite,
                    prix_unitaire=ligne.prix_unitaire,
                    devise=ligne.devise or Plat.Devise.CDF,
                    montant=ligne.montant,
                )
                for ligne in commande.lignes.exclude(statut=LigneCommande.Statut.ANNULEE)
            ]
            if lignes:
                LigneFacture.objects.bulk_create(lignes)
        return facture


class LigneFacture(models.Model):
    facture = models.ForeignKey(
        Facture,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='facture',
    )
    designation = models.CharField('désignation', max_length=150)
    quantite = models.PositiveIntegerField('quantité')
    prix_unitaire = models.DecimalField('prix unitaire', max_digits=10, decimal_places=2)
    devise = models.CharField(
        'devise',
        max_length=3,
        choices=Plat.Devise.choices,
        default=Plat.Devise.CDF,
    )
    montant = models.DecimalField('montant', max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'ligne de facture'
        verbose_name_plural = 'lignes de facture'
        ordering = ['id']

    def __str__(self):
        return f'{self.designation} × {self.quantite}'
