import unicodedata
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class ServicePoste(models.TextChoices):
    CUISINE = 'CUISINE', 'Cuisine'
    BARBECUS = 'BARBECUS', 'Barbecus'
    TERRASSE = 'TERRASSE', 'Terrasse'


class Salle(models.Model):
    nom = models.CharField('nom', max_length=100, unique=True)
    ordre = models.PositiveIntegerField('ordre', default=0)

    class Meta:
        verbose_name = 'salle'
        verbose_name_plural = 'salles'
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


class Table(models.Model):
    salle = models.ForeignKey(
        Salle,
        on_delete=models.PROTECT,
        related_name='tables',
        verbose_name='salle',
    )
    numero = models.CharField('numéro', max_length=20)
    places = models.PositiveIntegerField('places', default=4)

    class Meta:
        verbose_name = 'table'
        verbose_name_plural = 'tables'
        ordering = ['salle__ordre', 'salle__nom', 'numero']
        constraints = [
            models.UniqueConstraint(fields=['salle', 'numero'], name='table_unique_par_salle'),
        ]

    def __str__(self):
        return f'Table {self.numero} ({self.salle})'

    def commande_ouverte(self):
        cache = getattr(self, '_prefetched_objects_cache', {})
        if 'commandes' in cache:
            for commande in self.commandes.all():
                if commande.statut in Commande.STATUTS_ACTIFS:
                    return commande
            return None
        return self.commandes.filter(statut__in=Commande.STATUTS_ACTIFS).first()

    @property
    def occupee(self):
        return self.commande_ouverte() is not None


class Serveur(models.Model):
    """Serveur / serveuse enregistré(e) dans les tables de paramètre."""

    nom = models.CharField('nom', max_length=100)
    prenom = models.CharField('prénom', max_length=100, blank=True)
    actif = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'serveur'
        verbose_name_plural = 'serveurs'
        ordering = ['nom', 'prenom']
        constraints = [
            models.UniqueConstraint(
                fields=['nom', 'prenom'],
                name='serveur_unique_nom_prenom',
            ),
        ]

    def __str__(self):
        return ' '.join(part for part in (self.prenom, self.nom) if part).strip()


class CategorieMenu(models.Model):
    nom = models.CharField('nom', max_length=100, unique=True)
    ordre = models.PositiveIntegerField('ordre', default=0)

    class Meta:
        verbose_name = 'catégorie de menu'
        verbose_name_plural = 'catégories de menu'
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


class Imprimante(models.Model):
    nom = models.CharField('nom', max_length=100, unique=True)
    service = models.CharField(
        'service',
        max_length=10,
        choices=ServicePoste.choices,
    )
    nom_systeme = models.CharField(
        'nom de l’imprimante',
        max_length=150,
        help_text='Nom de l’imprimante telle qu’elle apparaît sur le poste (cuisine, barbecus ou terrasse).',
    )

    class Meta:
        verbose_name = 'imprimante'
        verbose_name_plural = 'imprimantes'
        ordering = ['service', 'nom']

    def __str__(self):
        return f'{self.nom} ({self.get_service_display()})'


def imprimante_par_defaut(service):
    if not service:
        return None
    qs = Imprimante.objects.filter(service=service)
    libelle = dict(ServicePoste.choices).get(service, '')
    return qs.filter(nom__iexact=libelle).first() or qs.order_by('id').first()


class Plat(models.Model):
    class Devise(models.TextChoices):
        CDF = 'CDF', 'CDF'
        USD = 'USD', 'USD'

    categorie = models.ForeignKey(
        CategorieMenu,
        on_delete=models.PROTECT,
        related_name='plats',
        verbose_name='catégorie',
    )
    nom = models.CharField('nom', max_length=150)
    prix = models.DecimalField('prix', max_digits=10, decimal_places=2)
    devise = models.CharField(
        'devise',
        max_length=3,
        choices=Devise.choices,
        default=Devise.CDF,
    )
    description = models.TextField('description', blank=True)
    service = models.CharField(
        'service',
        max_length=10,
        choices=ServicePoste.choices,
        default=ServicePoste.CUISINE,
        help_text='Cuisine, barbecus ou terrasse : détermine où la ligne s’affiche après validation.',
    )
    imprimante = models.ForeignKey(
        Imprimante,
        on_delete=models.PROTECT,
        related_name='plats',
        verbose_name='imprimante',
        help_text='Imprimante du service qui recevra le ticket de ce plat.',
        null=True,
    )
    quantite = models.PositiveIntegerField(
        'quantité disponible',
        default=0,
        help_text=(
            'Terrasse : augmentée automatiquement par les sorties magasin (bar inclus). '
            'Cuisine et barbecus : saisie des plats préparés sur l’écran du poste. '
            'Diminuée à la validation de la commande.'
        ),
    )
    seuil_alerte = models.PositiveIntegerField(
        'seuil d’alerte',
        default=2,
        help_text='Un signal s’affiche quand il ne reste plus que ce nombre de portions.',
    )
    actif = models.BooleanField('actif', default=True)

    class Meta:
        verbose_name = 'plat'
        verbose_name_plural = 'plats'
        ordering = ['categorie__ordre', 'nom']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.imprimante_id and self.service:
            self.imprimante = imprimante_par_defaut(self.service)
        super().save(*args, **kwargs)

    def clean(self):
        if not self.imprimante_id and self.service:
            self.imprimante = imprimante_par_defaut(self.service)
        if not self.imprimante_id:
            raise ValidationError({'imprimante': 'Indiquez l’imprimante liée à ce plat.'})
        if self.imprimante_id and self.service and self.imprimante.service != self.service:
            raise ValidationError({
                'imprimante': 'Choisissez une imprimante du même service que le plat (cuisine, barbecus ou terrasse).',
            })

    @property
    def prix_affiche(self):
        return f'{self.prix} {self.devise}'

    @property
    def en_rupture(self):
        return self.quantite <= 0

    @property
    def en_alerte(self):
        return 0 < self.quantite <= self.seuil_alerte

    def reserver(self, nombre=1):
        if nombre <= 0:
            return self
        with transaction.atomic():
            plat = Plat.objects.select_for_update().get(pk=self.pk)
            if plat.quantite <= 0:
                raise ValidationError(
                    f'{plat.nom} : quantité à 0, impossible de commander ce plat.'
                )
            if plat.quantite < nombre:
                raise ValidationError(
                    f'{plat.nom} : il ne reste que {plat.quantite} portion(s).'
                )
            plat.quantite -= nombre
            plat.save(update_fields=['quantite'])
            self.quantite = plat.quantite
            return plat

    def verifier_disponible(self, nombre):
        if nombre <= 0:
            raise ValidationError('Indiquez une quantité supérieure à 0.')
        if self.quantite <= 0:
            raise ValidationError(
                f'{self.nom} : quantité à 0, impossible de commander ce plat.'
            )
        if self.quantite < nombre:
            raise ValidationError(
                f'{self.nom} : il ne reste que {self.quantite} portion(s) disponible(s).'
            )
        return self

    def liberer(self, nombre=1):
        if nombre <= 0:
            return
        Plat.objects.filter(pk=self.pk).update(quantite=models.F('quantite') + nombre)
        self.refresh_from_db(fields=['quantite'])

    def ajouter_portions(self, nombre):
        if nombre <= 0:
            raise ValidationError('Indiquez un nombre de plats préparés supérieur à 0.')
        with transaction.atomic():
            plat = Plat.objects.select_for_update().get(pk=self.pk)
            plat.quantite += nombre
            plat.save(update_fields=['quantite'])
            self.quantite = plat.quantite
            return plat

    def ajuster_quantite(self, quantite):
        if quantite < 0:
            raise ValidationError('La quantité ne peut pas être négative.')
        self.quantite = quantite
        self.save(update_fields=['quantite'])
        return self


class CompositionPlat(models.Model):
    plat = models.ForeignKey(
        Plat,
        on_delete=models.CASCADE,
        related_name='compositions',
        verbose_name='plat',
    )
    produit = models.ForeignKey(
        'approvisionnement.Produit',
        on_delete=models.PROTECT,
        related_name='compositions_plats',
        verbose_name='produit',
    )
    quantite = models.PositiveIntegerField(
        'quantité',
        help_text='Quantité de produit consommée pour une portion du plat.',
    )

    class Meta:
        verbose_name = 'composition de plat'
        verbose_name_plural = 'compositions de plat'
        constraints = [
            models.UniqueConstraint(fields=['plat', 'produit'], name='composition_unique_plat_produit'),
        ]

    def __str__(self):
        return f'{self.plat} · {self.produit} × {self.quantite}'


class Commande(models.Model):
    class Statut(models.TextChoices):
        OUVERTE = 'OUVERTE', 'Saisie'
        VALIDEE = 'VALIDEE', 'Validée'
        SERVIE = 'SERVIE', 'Servie'
        PAYEE = 'PAYEE', 'Payée'
        ANNULEE = 'ANNULEE', 'Annulée'

    class Source(models.TextChoices):
        TABLETTE = 'TABLETTE', 'Tablette'
        BON_PAPIER = 'BON_PAPIER', 'Bon papier'

    class ModePaiement(models.TextChoices):
        ESPECES = 'ESPECES', 'Espèces'
        MOBILE = 'MOBILE', 'Mobile money'
        CARTE = 'CARTE', 'Carte'

    STATUTS_ACTIFS = (Statut.OUVERTE, Statut.VALIDEE, Statut.SERVIE)

    numero = models.CharField('numéro', max_length=20, unique=True, editable=False)
    table = models.ForeignKey(
        Table,
        on_delete=models.PROTECT,
        related_name='commandes',
        verbose_name='table',
        null=True,
        blank=True,
    )
    emporter = models.BooleanField('à emporter', default=False)
    source = models.CharField(
        'saisie',
        max_length=12,
        choices=Source.choices,
        default=Source.TABLETTE,
    )
    reference_bon = models.CharField(
        'référence du bon papier',
        max_length=50,
        blank=True,
        help_text='Obligatoire si la commande est saisie à partir d’un bon papier.',
    )
    serveur = models.ForeignKey(
        Serveur,
        on_delete=models.PROTECT,
        related_name='commandes',
        verbose_name='serveur',
        null=True,
        blank=True,
    )
    date_ouverture = models.DateTimeField('ouverture', default=timezone.now)
    date_cloture = models.DateTimeField('clôture', null=True, blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='commandes_restauration',
        verbose_name='opérateur',
    )
    statut = models.CharField(
        'statut',
        max_length=16,
        choices=Statut.choices,
        default=Statut.OUVERTE,
    )
    commentaire = models.TextField('commentaire', blank=True)
    date_validation = models.DateTimeField('date de validation', null=True, blank=True)
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='commandes_validees',
        verbose_name='validée par',
        null=True,
        blank=True,
    )
    motif_annulation = models.CharField('motif d’annulation', max_length=250, blank=True)
    date_annulation = models.DateTimeField('date d’annulation', null=True, blank=True)
    annulee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='commandes_annulees',
        verbose_name='annulée par',
        null=True,
        blank=True,
    )
    mode_paiement = models.CharField(
        'mode de paiement',
        max_length=12,
        choices=ModePaiement.choices,
        blank=True,
    )
    stock_consomme = models.BooleanField('stock consommé', default=False)

    class Meta:
        verbose_name = 'commande'
        verbose_name_plural = 'commandes'
        ordering = ['-date_ouverture']
        permissions = [
            ('view_restauration', 'Peut consulter la restauration'),
            ('create_commande', 'Peut enregistrer une commande'),
            ('modify_commande', 'Peut modifier une commande avant validation'),
            ('validate_commande', 'Peut valider et imprimer une commande'),
            ('cancel_commande', 'Peut annuler une commande non validée'),
            ('encaisser_commande', 'Peut enregistrer le paiement d’une commande'),
            ('servir_ligne', 'Peut marquer une ligne comme servie'),
            ('adjust_plat_portions', 'Peut ajouter des plats préparés (cuisine / barbecus)'),
        ]

    def __str__(self):
        return self.numero

    @classmethod
    def prochain_numero(cls):
        annee = timezone.localdate().year
        prefixe = f'RST-{annee}-'
        dernier = (
            cls.objects.select_for_update()
            .filter(numero__startswith=prefixe)
            .order_by('-numero')
            .first()
        )
        sequence = int(dernier.numero.rsplit('-', 1)[-1]) + 1 if dernier else 1
        return f'{prefixe}{sequence:04d}'

    @property
    def nom_emplacement(self):
        if self.emporter:
            return 'À emporter'
        if self.table_id:
            return str(self.table)
        return '—'

    @property
    def nom_serveur(self):
        if self.serveur_id:
            return str(self.serveur)
        return str(self.utilisateur)

    @property
    def modifiable(self):
        return self.statut in self.STATUTS_ACTIFS

    @property
    def stock_deja_reserve(self):
        return self.stock_consomme or self.statut in (
            self.Statut.VALIDEE,
            self.Statut.SERVIE,
            self.Statut.PAYEE,
        )

    @property
    def peut_encaisser(self):
        if self.statut not in (self.Statut.VALIDEE, self.Statut.SERVIE):
            return False
        return any(
            ligne.statut != LigneCommande.Statut.ANNULEE
            for ligne in self.lignes.all()
        )

    @property
    def est_mixte(self):
        services = {ligne.service for ligne in self.lignes.all() if ligne.service}
        return len(services) > 1

    def groupes_impression(self, seulement_non_imprimees=True):
        """Un ticket par service et imprimante : cuisine, barbecus et terrasse séparément."""
        groupes = {}
        ordre = []
        toutes = [
            ligne for ligne in self.lignes.all()
            if ligne.statut != LigneCommande.Statut.ANNULEE
        ]
        est_ajout = any(ligne.imprimee for ligne in toutes)
        lignes = [
            ligne for ligne in toutes
            if ligne.service and (not seulement_non_imprimees or not ligne.imprimee)
        ]
        for ligne in lignes:
            imprimante = (ligne.imprimante_nom or '').strip()
            if not imprimante:
                defaut = imprimante_par_defaut(ligne.service)
                imprimante = ((defaut.nom_systeme or defaut.nom) if defaut else '')
            cle = (ligne.service, imprimante)
            if cle not in groupes:
                groupes[cle] = {
                    'service': ligne.service,
                    'libelle': ligne.get_service_display(),
                    'imprimante': imprimante,
                    'ajout': est_ajout,
                    'lignes': [],
                }
                ordre.append(cle)
            groupes[cle]['lignes'].append(ligne)
        return [groupes[cle] for cle in ordre]

    @property
    def a_des_lignes_imprimees(self):
        return any(
            ligne.imprimee and ligne.statut != LigneCommande.Statut.ANNULEE
            for ligne in self.lignes.all()
        )

    @property
    def a_des_ajouts_a_imprimer(self):
        return any(
            (not ligne.imprimee)
            and ligne.statut != LigneCommande.Statut.ANNULEE
            and ligne.service
            for ligne in self.lignes.all()
        )

    def marquer_lignes_imprimees(self, lignes):
        ids = [ligne.pk for ligne in lignes if ligne.pk]
        if not ids:
            return
        self.lignes.filter(pk__in=ids).update(imprimee=True)
        for ligne in lignes:
            ligne.imprimee = True

    @property
    def est_payee(self):
        return self.statut == self.Statut.PAYEE

    @property
    def facture_emise(self):
        from django.core.exceptions import ObjectDoesNotExist
        try:
            return self.facture
        except ObjectDoesNotExist:
            return None

    @property
    def est_impayee(self):
        return self.statut in self.STATUTS_ACTIFS

    @property
    def resume_lignes(self):
        return ', '.join(
            f'{ligne.quantite} × {ligne.libelle}'
            for ligne in self.lignes.all()
        ) or '—'

    @property
    def totaux_par_devise(self):
        totaux = {}
        for ligne in self.lignes.all():
            if ligne.statut == LigneCommande.Statut.ANNULEE:
                continue
            devise = ligne.devise or Plat.Devise.CDF
            totaux[devise] = totaux.get(devise, Decimal('0.00')) + ligne.montant
        return totaux

    @property
    def total(self):
        return sum(
            (
                ligne.montant
                for ligne in self.lignes.all()
                if ligne.statut != LigneCommande.Statut.ANNULEE
            ),
            Decimal('0.00'),
        )

    def valider(self, utilisateur):
        if self.statut != self.Statut.OUVERTE:
            raise ValidationError('Seule une commande en saisie peut être validée.')
        lignes = list(self.lignes.select_related('plat', 'plat__imprimante'))
        if not lignes:
            raise ValidationError('Ajoutez au moins un plat ou une boisson avant de valider.')
        totaux = {}
        for ligne in lignes:
            totaux[ligne.plat_id] = totaux.get(ligne.plat_id, 0) + ligne.quantite
        with transaction.atomic():
            for plat_id, nombre in totaux.items():
                plat = Plat.objects.select_for_update().get(pk=plat_id)
                plat.reserver(nombre)
            for ligne in lignes:
                if not ligne.plat.imprimante_id:
                    defaut = imprimante_par_defaut(ligne.plat.service)
                    if defaut:
                        ligne.plat.imprimante = defaut
                        ligne.plat.save(update_fields=['imprimante'])
                ligne.figer_destination()
                ligne.stock_consomme = True
                ligne.save(update_fields=[
                    'service',
                    'imprimante_nom',
                    'devise',
                    'designation',
                    'description_plat',
                    'stock_consomme',
                ])
            self.statut = self.Statut.VALIDEE
            self.date_validation = timezone.now()
            self.validee_par = utilisateur
            self.stock_consomme = True
            self.save(update_fields=[
                'statut',
                'date_validation',
                'validee_par',
                'stock_consomme',
            ])

    def servir(self, utilisateur):
        raise ValidationError('Le service se fait ligne par ligne depuis l’écran cuisine, barbecus ou terrasse.')

    def encaisser(self, mode_paiement):
        if self.statut not in (self.Statut.VALIDEE, self.Statut.SERVIE):
            raise ValidationError('Validez la commande avant l’encaissement.')
        if not self.lignes.exclude(statut=LigneCommande.Statut.ANNULEE).exists():
            raise ValidationError('Impossible d’encaisser une commande vide.')
        self.statut = self.Statut.PAYEE
        self.mode_paiement = mode_paiement
        self.date_cloture = timezone.now()
        self.save(update_fields=['statut', 'mode_paiement', 'date_cloture'])
        # PAYEE n’est plus un statut actif : la table redevient libre.

    def annuler(self, utilisateur, motif):
        if self.statut == self.Statut.PAYEE:
            raise ValidationError('Une facture déjà payée ne peut pas être annulée.')
        if self.statut == self.Statut.ANNULEE:
            raise ValidationError('Cette commande ne peut plus être annulée.')
        if self.statut == self.Statut.VALIDEE and not getattr(utilisateur, 'is_superuser', False):
            raise ValidationError(
                'Une commande déjà validée ne peut pas être annulée. '
                'Seul un superuser peut le faire.'
            )
        if self.lignes.filter(statut=LigneCommande.Statut.SERVIE).exists():
            raise ValidationError('Impossible d’annuler : des lignes sont déjà servies.')
        motif = (motif or '').strip()
        if not motif:
            raise ValidationError('Le motif d’annulation est obligatoire.')
        with transaction.atomic():
            deja_deduit = self.statut == self.Statut.VALIDEE or self.stock_consomme
            for ligne in self.lignes.exclude(statut=LigneCommande.Statut.ANNULEE).select_related('plat'):
                if deja_deduit:
                    ligne.plat.liberer(ligne.quantite)
                ligne.statut = LigneCommande.Statut.ANNULEE
                ligne.save(update_fields=['statut'])
            self.statut = self.Statut.ANNULEE
            self.motif_annulation = motif
            self.date_annulation = timezone.now()
            self.annulee_par = utilisateur
            self.date_cloture = self.date_annulation
            self.save(update_fields=[
                'statut',
                'motif_annulation',
                'date_annulation',
                'annulee_par',
                'date_cloture',
            ])

    def actualiser_apres_service(self):
        lignes = list(self.lignes.all())
        if not lignes:
            return
        if any(ligne.statut == LigneCommande.Statut.EN_ATTENTE for ligne in lignes):
            return
        if all(ligne.statut == LigneCommande.Statut.ANNULEE for ligne in lignes):
            return
        if self.statut == self.Statut.VALIDEE:
            self.statut = self.Statut.SERVIE
            self.stock_consomme = all(ligne.stock_consomme or ligne.statut == LigneCommande.Statut.ANNULEE for ligne in lignes)
            self.save(update_fields=['statut', 'stock_consomme'])


class LigneCommande(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente'
        SERVIE = 'SERVIE', 'Servie'
        ANNULEE = 'ANNULEE', 'Annulée'

    commande = models.ForeignKey(
        Commande,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='commande',
    )
    plat = models.ForeignKey(
        Plat,
        on_delete=models.PROTECT,
        related_name='lignes_commandes',
        verbose_name='plat',
    )
    quantite = models.PositiveIntegerField('quantité', default=1)
    prix_unitaire = models.DecimalField('prix unitaire', max_digits=10, decimal_places=2)
    devise = models.CharField(
        'devise',
        max_length=3,
        choices=Plat.Devise.choices,
        default=Plat.Devise.CDF,
    )
    note = models.CharField('note', max_length=200, blank=True)
    designation = models.CharField(
        'plat commandé',
        max_length=150,
        blank=True,
        help_text='Libellé du plat au moment de la commande.',
    )
    description_plat = models.TextField(
        'description du plat',
        blank=True,
        help_text='Description enregistrée au moment de la commande.',
    )
    service = models.CharField(
        'destination',
        max_length=10,
        choices=ServicePoste.choices,
        blank=True,
    )
    imprimante_nom = models.CharField('imprimante', max_length=150, blank=True)
    statut = models.CharField(
        'statut',
        max_length=12,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
    )
    date_service = models.DateTimeField('date de service', null=True, blank=True)
    servi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='lignes_servies',
        verbose_name='servi par',
        null=True,
        blank=True,
    )
    stock_consomme = models.BooleanField('stock consommé', default=False)
    imprimee = models.BooleanField(
        'envoyée à l’imprimante',
        default=False,
        help_text='True après un envoi réussi en cuisine, barbecus ou terrasse.',
    )

    class Meta:
        verbose_name = 'ligne de commande'
        verbose_name_plural = 'lignes de commande'
        ordering = ['id']

    def __str__(self):
        return f'{self.libelle} × {self.quantite}'

    @property
    def libelle(self):
        return self.designation or (self.plat.nom if self.plat_id else 'Plat')

    @property
    def montant(self):
        return self.prix_unitaire * self.quantite

    def figer_destination(self):
        plat = self.plat
        self.service = plat.service
        self.devise = plat.devise
        self.designation = plat.nom
        self.description_plat = plat.description
        imprimante = plat.imprimante
        if not imprimante and plat.service:
            imprimante = imprimante_par_defaut(plat.service)
        if imprimante:
            self.imprimante_nom = imprimante.nom_systeme or imprimante.nom
        elif not self.imprimante_nom:
            self.imprimante_nom = ''

    def marquer_servie(self, utilisateur):
        if self.commande.statut not in (
            Commande.Statut.VALIDEE,
            Commande.Statut.SERVIE,
            Commande.Statut.PAYEE,
        ):
            raise ValidationError('La commande doit être validée avant le service.')
        if self.statut != self.Statut.EN_ATTENTE:
            raise ValidationError('Cette ligne ne peut plus être marquée comme servie.')
        with transaction.atomic():
            self.statut = self.Statut.SERVIE
            self.date_service = timezone.now()
            self.servi_par = utilisateur
            self.stock_consomme = True
            self.save(update_fields=['statut', 'date_service', 'servi_par', 'stock_consomme'])
            self.commande.actualiser_apres_service()


def _normaliser_destination(nom):
    texte = unicodedata.normalize('NFD', nom or '')
    texte = ''.join(car for car in texte if unicodedata.category(car) != 'Mn')
    return texte.casefold()


def service_poste_depuis_destination(nom):
    texte = _normaliser_destination(nom)
    if 'cuisine' in texte:
        return ServicePoste.CUISINE
    if 'barbecus' in texte or 'barbecue' in texte:
        return ServicePoste.BARBECUS
    if (
        'terras' in texte
        or 'teras' in texte
        or 'terrace' in texte
        or 'bar' in texte
    ):
        return ServicePoste.TERRASSE
    return ''


def ids_produits_rattaches_au_poste(service):
    return set(
        CompositionPlat.objects.filter(
            plat__service=service,
            plat__actif=True,
        ).values_list('produit_id', flat=True)
    )


def _plats_alimentes_par_produit(produit, service):
    plats = list(
        Plat.objects.filter(
            compositions__produit=produit,
            service=service,
            actif=True,
        ).distinct()
    )
    if plats:
        return plats
    return list(
        Plat.objects.filter(
            service=service,
            actif=True,
        ).filter(
            models.Q(nom__iexact=produit.designation) | models.Q(nom__iexact=produit.code)
        )
    )


def alimenter_plats_depuis_sortie(bon):
    """Augmente les plats terrasse vendables à partir des produits sortis."""
    service = service_poste_depuis_destination(getattr(bon, 'nom_destination', ''))
    if service != ServicePoste.TERRASSE:
        return []
    ajouts = []
    lignes = bon.lignes.filter(quantite__gt=0).select_related('produit', 'produit__categorie')
    for ligne in lignes:
        produit = ligne.produit
        qte = ligne.nombre_portions if produit.exige_portions and ligne.nombre_portions else ligne.quantite
        if qte <= 0:
            continue
        for plat_lie in _plats_alimentes_par_produit(produit, service):
            plat = Plat.objects.select_for_update().get(pk=plat_lie.pk)
            plat.quantite += qte
            plat.save(update_fields=['quantite'])
            ajouts.append((plat.nom, qte, plat.quantite, service))
    return ajouts
