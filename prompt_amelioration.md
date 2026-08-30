PROMPT — Ajustements du montant retenu et de l’interface de traitement
Consigne générale obligatoire

Avant toute modification :

Analyse d’abord le code existant concernant :
le modèle de vente ;
les lignes de vente ;
le traitement/validation des ventes ;
le calcul des montants ;
les totaux dans le détail d’une vente ;
l’affichage des lignes de vente ;
le champ prix proposé ;
le champ prix retenu ;
le ticket/facture.
Identifie précisément où et comment les montants sont actuellement calculés.
Vérifie si une logique existe déjà avant d’en créer une nouvelle.
Ne crée pas de doublon.
Ne reconstruis pas une logique qui fonctionne déjà.
Ne supprime pas une logique métier existante sans nécessité.
Réutilise les fonctions, méthodes, propriétés, modèles et composants existants lorsque cela est pertinent.
Fais les modifications étape par étape, problème par problème.
Après chaque modification, vérifie que les autres règles métier existantes continuent de fonctionner.
ÉTAPE 1 — Utiliser le montant retenu pour TOUS les totaux finaux

Il existe actuellement une incohérence dans le calcul des totaux après le traitement d’une vente.

Situation actuelle

Une ligne de vente possède notamment :

Article / variante
Quantité
Prix unitaire normal
Prix minimum
Prix proposé par l'opérateur/client
Prix retenu par le responsable
Montant proposé
Montant retenu
Statut de la ligne

Lorsqu’une vente est traitée par le responsable, celui-ci peut retenir un prix différent du prix proposé.

Le prix retenu devient alors le prix définitif de cette ligne.

Règle à appliquer

Le système doit distinguer clairement :

Montant proposé :

quantité × prix proposé

Montant retenu :

quantité × prix retenu

Une fois que le responsable a traité la ligne, le montant retenu devient la référence pour le calcul final de la vente.

Modification demandée

Dans le détail d’une vente, lorsque le responsable modifie/traite une ligne :

le prix retenu doit être enregistré ;
le montant retenu doit être recalculé ;
la ligne doit afficher son nouveau montant retenu ;
le total de la vente doit être recalculé à partir des montants retenus, et non plus à partir des montants proposés.
Très important

Il ne doit plus être possible d'avoir une situation incohérente comme :

Article : 30 000 FC
Total : 28 000 FC

si le prix retenu de cet article est bien de 30 000 FC.

Le système doit toujours respecter :

Total vente = somme des montants retenus des lignes

Lorsque plusieurs lignes existent :

Total vente =
    montant retenu ligne 1
  + montant retenu ligne 2
  + montant retenu ligne 3
  + ...
Cas où aucun prix réduit n’est appliqué

Si :

prix retenu = prix normal

alors :

montant retenu = quantité × prix normal
Cas où le responsable accepte un prix inférieur

Si :

prix proposé < prix normal

et que le responsable retient finalement :

prix retenu = prix proposé

alors :

montant retenu = quantité × prix retenu

Le total doit immédiatement prendre ce montant retenu en considération.

À vérifier également

Cette même logique doit être cohérente dans :

le détail de la vente ;
les lignes affichées après traitement ;
les totaux de la vente ;
le ticket/facture final ;
toute autre vue utilisant le montant final de la vente.

Ne modifie pas le montant proposé : il doit rester conservé comme historique de la proposition initiale.

Il faut donc conserver la distinction :

Prix proposé     → proposition initiale
Prix retenu      → prix finalement accepté
Montant proposé  → historique de la proposition
Montant retenu   → montant définitif utilisé pour la vente
ÉTAPE 2 — Agrandir l’input du prix retenu dans le traitement

Dans l’interface de traitement d’une ligne de vente, il existe actuellement un champ permettant au responsable de saisir/modifier le prix retenu, accompagné d’un bouton d’action, par exemple :

[ Prix retenu ] [ Valider ]

Actuellement, l’input du prix retenu est trop petit.

Modification demandée

Le conteneur parent qui contient :

l'input prix retenu ;
le bouton Valider ;

doit être divisé en deux parties égales.

┌───────────────────────────────┐
│ [     Prix retenu     ]       │
│       50 %                    │
│                               │
│              [   Valider   ]  │
│                  50 %         │
└───────────────────────────────┘

Plus précisément, sur une même ligne :

[──────── 50% ────────][──── 50% ────]
      Input                 Bouton
   Prix retenu             Valider

L'input doit donc occuper 50 % de la largeur disponible et le bouton 50 %.

Contraintes
Les deux éléments doivent avoir une largeur visuellement équilibrée.
Ils doivent rester dans le même conteneur.
Le bouton ne doit pas être réduit inutilement.
L'input doit être suffisamment large pour afficher/saisir correctement un montant monétaire.
Conserver le responsive design existant.
Ne pas casser les autres composants de l’interface de traitement.
CONTRAINTE FINALE

Avant de coder, inspecte impérativement l’implémentation actuelle pour déterminer :

où est calculé le montant proposé ;
où est calculé le montant retenu ;
comment le total de la vente est actuellement calculé ;
quelles vues utilisent encore le montant proposé pour calculer le total ;
comment le prix retenu est enregistré lors du traitement ;
comment le ticket récupère le montant final.

Ensuite, applique la correction au niveau approprié de la logique métier, plutôt que de mettre simplement des calculs différents dans chaque template.

Objectif final : une seule source de vérité pour le montant final de la vente : le montant retenu.

Ne touche à aucune autre fonctionnalité qui n’est pas nécessaire à ces deux ajustements.