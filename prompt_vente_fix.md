CONTEXTE

Nous devons ajuster le workflow de vente du module « Gestion des Boutiques ».

IMPORTANT :

Le système actuel possède deux interfaces distinctes :

1. Interface de création de la vente / entête.
2. Interface de validation dans laquelle les lignes de vente sont ensuite renseignées.

Nous voulons SUPPRIMER cette séparation fonctionnelle.

La nouvelle logique doit avoir UNE SEULE INTERFACE permettant simultanément :

- de renseigner l'entête de la vente ;
- d'ajouter les lignes de vente ;
- de renseigner les variantes ;
- de renseigner les quantités ;
- de renseigner les prix unitaires ;
- de renseigner les remises ;
- de renseigner les informations de paiement ;
- d'effectuer tous les contrôles métier ;
- puis de créer la vente ET de la soumettre à validation dans la même opération.

IMPORTANT :

Ne pas supprimer les règles métier de contrôle déjà implémentées.

Il s'agit uniquement de modifier le workflow et l'interface pour regrouper les deux étapes.

==================================================
1. NOUVEAU PRINCIPE
==================================================

L'ancien workflow :

CRÉATION DE L'ENTÊTE
        ↓
ENREGISTREMENT
        ↓
OUVERTURE D'UNE DEUXIÈME INTERFACE
        ↓
AJOUT DES LIGNES
        ↓
VALIDATION / SOUMISSION

DOIT DEVENIR :

UNE SEULE INTERFACE
        ↓
ENTÊTE + LIGNES + PAIEMENT + REMISE
        ↓
CONTRÔLES MÉTIER
        ↓
CRÉATION DE LA VENTE
        ↓
DEMANDE DE VALIDATION

La création de la vente et sa demande de validation doivent donc être réalisées dans une seule soumission du formulaire.

==================================================
2. INFORMATIONS DE L'ENTÊTE
==================================================

Dans la même interface, afficher les informations générales nécessaires à la vente.

Par exemple :

- client ;
- informations générales de la vente ;
- paiement ;
- remise ;
- montant reçu ;
- autres informations déjà prévues par le système.

IMPORTANT :

Les informations qui sont déterminées automatiquement par l'utilisateur connecté ne doivent PAS être demandées inutilement dans le formulaire.

==================================================
3. DOMAINE D'ACTIVITÉ ET SUCCURSALE
==================================================

Le domaine d'activité et la succursale ne doivent pas être des champs que l'utilisateur doit sélectionner manuellement à chaque création de vente lorsqu'ils sont déjà déterminés par son contexte utilisateur.

Ces informations doivent être récupérées automatiquement en amont à partir du contexte de l'utilisateur connecté.

Exemple :

Utilisateur connecté :

Succursale = Succursale A
Domaine d'activité = Boutique

Lorsqu'il ouvre « Nouvelle vente » :

Le système connaît déjà :

Succursale = Succursale A
Domaine = Boutique

Ces valeurs doivent donc être préremplies automatiquement ou directement déterminées côté backend.

Ne pas demander à l'utilisateur de les saisir à nouveau.

IMPORTANT :

Le backend doit également déterminer ces informations à partir du contexte utilisateur.

Il ne faut pas faire confiance uniquement aux valeurs envoyées par le frontend.

Cela permet d'éviter qu'un utilisateur puisse créer une vente dans une autre succursale ou un autre domaine d'activité simplement en modifiant une valeur dans la requête.

==================================================
4. AJOUT DES LIGNES DE VENTE
==================================================

Dans la même interface que l'entête, l'utilisateur doit pouvoir ajouter les lignes de la vente.

Chaque ligne doit permettre de renseigner :

- VarianteArticle ;
- quantité ;
- prix unitaire / prix de vente ;
- remise éventuelle ;
- montant de la ligne ;
- autres informations déjà prévues.

La ligne doit être ajoutée dynamiquement.

Il ne faut PAS afficher plusieurs groupes de champs identiques inutilement.

Le principe doit être :

Variante | Quantité | Prix unitaire | Remise | Montant | Action

Puis :

+ Ajouter une ligne

Chaque nouvelle ligne est ajoutée dynamiquement à la vente.

==================================================
5. SÉLECTION DE LA VARIANTE
==================================================

Lorsque l'utilisateur sélectionne une VarianteArticle :

Le système doit récupérer automatiquement les informations disponibles pour cette variante.

Notamment :

- stock disponible ;
- prix unitaire / prix de référence ;
- prix minimum ;
- autres informations nécessaires.

Exemple :

Variante sélectionnée :

Chemise Noir / M / Homme

Le formulaire récupère automatiquement :

Stock disponible : 40
Prix de référence : 400
Prix minimum : 300

Le prix unitaire doit être automatiquement renseigné avec :

400

L'utilisateur peut ensuite modifier ce prix si les règles métier l'autorisent.

==================================================
6. PRIX UNITAIRE
==================================================

Conserver intégralement la logique métier existante concernant les prix.

Le prix unitaire saisi dans la ligne représente le prix réellement appliqué à la vente.

Le système doit comparer :

Prix de vente saisi
VS
Prix de référence de la variante
VS
Prix minimum de la variante.

==================================================
7. RÈGLE DU PRIX MINIMUM
==================================================

Cette règle reste INCHANGÉE.

Si :

Prix de vente < Prix minimum

→ REFUSER la soumission.

Exemple :

Prix de référence = 400
Prix minimum = 300
Prix saisi = 250

Résultat :

REFUS.

Afficher un message clair :

« Cette variante ne peut pas être vendue en dessous de son prix minimum autorisé. »

La vente ne doit pas être créée comme vente valide.

==================================================
8. PRIX INFÉRIEUR AU PRIX DE RÉFÉRENCE
==================================================

Cette règle reste également INCHANGÉE.

Si :

Prix minimum <= Prix de vente < Prix de référence

alors :

→ la vente est acceptable au niveau du prix minimum ;
→ mais elle nécessite une validation du responsable.

Exemple :

Prix de référence = 400
Prix minimum = 300
Prix saisi = 350

Résultat :

→ la vente est créée ;
→ statut = PENDING_VALIDATION ;
→ demande de validation envoyée au responsable.

==================================================
9. PRIX NORMAL
==================================================

Si :

Prix de vente >= Prix de référence

si le prix de vent est egal au prix de reference pas devalidation requise

Exemple :

Prix référence = 400
Prix saisi = 400

ou :
si le prix de vente est supperieur au prix de reference/unitaire cela doit envoyer un message claire à l'utilisateur () et bloquer la soumission de ce dernier

Prix saisi = 450


→ vente normale selon les règles existantes.

==================================================
10. PLUSIEURS LIGNES
==================================================

Les contrôles doivent être réalisés sur CHAQUE ligne.

Exemple :

Ligne 1 :

Variante A
Prix référence = 400
Prix minimum = 300
Prix saisi = 400

→ OK

Ligne 2 :

Variante B
Prix référence = 800
Prix minimum = 600
Prix saisi = 700

→ Validation responsable nécessaire.

Ligne 3 :

Variante C
Prix référence = 1000
Prix minimum = 700
Prix saisi = 500

→ Erreur bloquante.

Dans ce cas, la soumission doit être refusée tant qu'une ligne contient une erreur bloquante.

==================================================
11. CALCULS AUTOMATIQUES
==================================================

Dans la même interface, calculer automatiquement :

- montant de chaque ligne ;
- sous-total ;
- remise totale ;
- montant total ;
- montant reçu ;
- monnaie.

Exemple :

Quantité = 2
Prix unitaire = 400

Montant ligne :

2 × 400 = 800

Puis calculer le total de la vente selon les règles de remise existantes.

==================================================
12. MONTANT REÇU ET MONNAIE
==================================================

Les champs :

- montant reçu ;
- monnaie

doivent être disponibles directement dans cette même interface.

Ils ne doivent plus être reportés à une deuxième étape.

La monnaie doit être calculée automatiquement.

Exemple :

Total = 800
Montant reçu = 1 000

Monnaie :

1 000 - 800 = 200

==================================================
13. SOUMISSION UNIQUE
==================================================

Le bouton final de l'interface doit réaliser une seule opération logique :

« Créer et soumettre »

ou un libellé équivalent cohérent avec le design existant.

Lorsqu'il est déclenché :

1. valider les données de l'entête ;
2. valider les lignes ;
3. vérifier les variantes ;
4. vérifier les quantités ;
5. vérifier les stocks disponibles ;
6. récupérer/contrôler les prix de référence ;
7. vérifier les prix minimums ;
8. déterminer si une validation responsable est nécessaire ;
9. valider les informations de paiement ;
10. créer la vente ;
11. créer les lignes de vente ;
12. déterminer le statut final approprié ;
13. soumettre la vente au workflow de validation.

Toutes ces opérations doivent être cohérentes et transactionnelles.

==================================================
14. TRANSACTION BACKEND
==================================================

La création de l'entête et des lignes doit être effectuée dans une transaction.

Si une validation échoue :

→ ne pas créer une vente partiellement.

Exemple :

L'entête est valide
Ligne 1 est valide
Ligne 2 est valide
Ligne 3 contient un prix inférieur au prix minimum

Résultat :

→ la transaction doit être annulée ;
→ aucune vente partiellement enregistrée ne doit rester en base.

==================================================
15. STATUT APRÈS SOUMISSION
==================================================

Après la soumission :

CAS 1 :

Aucune validation spéciale n'est nécessaire.

→ utiliser le workflow prévu par le système.

CAS 2 :

Une ou plusieurs lignes sont vendues sous leur prix de référence mais au-dessus ou au niveau du prix minimum.

→ vente :

PENDING_VALIDATION

→ responsable habilité doit pouvoir la voir.

IMPORTANT :

Ne pas créer plusieurs systèmes de validation.

Réutiliser le système de validation déjà mis en place.

==================================================
16. STOCK
==================================================

La création et la soumission de la vente ne doivent PAS provoquer automatiquement une double sortie de stock.

Le mouvement définitif de sortie doit être déclenché selon le workflow de validation existant.

Si la vente est :

PENDING_VALIDATION

→ ne pas décrémenter définitivement le stock.

Lorsque la vente est APPROVED :

→ vérifier une dernière fois la disponibilité du stock ;
→ créer les mouvements SORTIE ;
→ décrémenter les stocks des VarianteArticle concernées ;
→ recalculer les alertes.

==================================================
17. DOUBLE VALIDATION / DOUBLE SOUMISSION
==================================================

Le backend doit empêcher :

- double soumission ;
- double validation ;
- double mouvement de sortie ;
- double décrémentation du stock.

Une vente déjà approuvée ne doit pas pouvoir être approuvée une deuxième fois.

==================================================
18. UTILISATEUR, SUCCURSALE ET DOMAINE
==================================================

La vente doit automatiquement être associée au contexte de l'utilisateur connecté :

- utilisateur créateur ;
- succursale ;
- domaine d'activité.

Ces informations doivent être déterminées côté backend.

Exemple :

Utilisateur X

Succursale :
Succursale A

Domaine :
Boutique

Nouvelle vente :

created_by = X
succursale = A
domaine_activite = Boutique

L'utilisateur ne doit pas pouvoir changer ces informations manuellement si elles sont définies par son contexte.

==================================================
19. EXPÉRIENCE UTILISATEUR
==================================================

L'utilisateur doit avoir une expérience simple :

Il ouvre :

« Nouvelle vente »

Puis une seule interface contient :

---------------------------------------------
INFORMATIONS DE LA VENTE
---------------------------------------------

Client
Date
Paiement
Remise
Montant reçu
Monnaie

---------------------------------------------
ARTICLES
---------------------------------------------

Variante | Quantité | Prix | Remise | Montant

[ Ajouter une ligne ]

---------------------------------------------
TOTAUX
---------------------------------------------

Sous-total
Remise totale
Total
Montant reçu
Monnaie

---------------------------------------------

[ CRÉER ET SOUMETTRE ]

Il ne doit plus être nécessaire :

Créer la vente
→ quitter l'écran
→ ouvrir Validation
→ ajouter les articles
→ compléter le paiement
→ soumettre.

Tout doit être réalisé dans une seule interface.

==================================================
20. MESSAGES DE CONFIRMATION ET D'ERREUR
==================================================

Après chaque soumission, afficher un retour utilisateur clair.

En cas de succès :

« Vente créée et soumise à validation. »

ou, si aucune validation n'est nécessaire :

« Vente créée avec succès. »

En cas d'erreur :

Afficher précisément l'erreur concernée.

Exemples :

« Le prix de vente de la variante Chemise Noir/M est inférieur au prix minimum autorisé. »

« Stock insuffisant pour la variante Chemise Noir/M. Stock disponible : 4. »

Ne pas afficher uniquement une erreur technique générique lorsque l'erreur métier peut être expliquée clairement.

==================================================
21. IMPRESSION
==================================================

Conserver la logique prévue précédemment :

Après validation effective de la vente, l'utilisateur doit pouvoir retrouver la vente dans la liste.

Actions :

- Voir les détails ;
- Imprimer.

L'impression doit utiliser les données de la vente validée.

==================================================
22. ANALYSE OBLIGATOIRE AVANT MODIFICATION
==================================================

Avant toute modification du code :

Analyser l'implémentation actuelle afin d'identifier :

- interface actuelle de création de vente ;
- interface actuelle de validation ;
- modèle Vente ;
- modèle LigneVente ;
- modèle VarianteArticle ;
- modèle Stock ;
- modèle MouvementStock ;
- logique de prix ;
- logique de prix minimum ;
- logique de remise ;
- logique de paiement ;
- logique de validation ;
- logique de stock ;
- logique d'impression.

Identifier exactement quelles parties doivent être fusionnées.

NE PAS supprimer brutalement la deuxième interface avant d'avoir transféré toutes les fonctionnalités nécessaires dans la nouvelle interface.

==================================================
RÉSULTAT FINAL
==================================================

L'ancienne architecture :

ÉCRAN 1
Création de vente
    ↓
ÉCRAN 2
Validation / ajout des lignes

DOIT DEVENIR :

ÉCRAN UNIQUE
Création + lignes + paiement + contrôles + soumission

Avec le workflow :

Utilisateur
    ↓
Nouvelle vente
    ↓
Entête
+
Lignes
+
Variantes
+
Quantités
+
Prix
+
Remises
+
Paiement
    ↓
Contrôles métier
    ↓
Création de la vente
    ↓
Soumission à validation si nécessaire
    ↓
Responsable
    ↓
APPROVED
    ↓
Mouvement SORTIE
    ↓
Décrémentation du Stock de chaque VarianteArticle
    ↓
Alerte éventuelle
    ↓
Historique
    ↓
Impression

RÈGLES EXISTANTES À CONSERVER ABSOLUMENT :

- prix de vente < prix minimum → refus ;
- prix minimum <= prix de vente < prix de référence → validation responsable ;
- prix de vente >= prix de référence → workflow normal ;
- contrôle du stock disponible ;
- mouvement de stock après validation ;
- traçabilité ;
- séparation créateur / validateur ;
- prévention des doubles mouvements.

La modification demandée porte principalement sur la SUPPRESSION DE LA DOUBLE INTERFACE et la FUSION DE LA CRÉATION ET DE LA SOUMISSION EN UNE SEULE INTERFACE.