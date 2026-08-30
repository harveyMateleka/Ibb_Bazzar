Contexte
Tu es développeur front-end. L’interface de recherche et d’affichage des variantes a été partiellement améliorée, mais plusieurs points restent à corriger pour atteindre une version stable et ergonomique.

Objectif général
Finaliser les corrections suivantes, dans l’ordre, en t’appuyant sur le code existant (partie droite comme référence pour les données).

Modifications détaillées

Chargement des prix (normal et minimum) dans la partie gauche

Actuellement, ces deux prix ne s’affichent pas dans les cartes de gauche (seulement des traits).

Action : Inspecter le mécanisme de chargement des données utilisé dans la partie droite (où les prix s’affichent correctement).

Appliquer le même procédé pour alimenter les prix dans les cartes de gauche, en veillant à bien récupérer les champs prix_normal et prix_minimum depuis la même source (table des variantes).

Séparation visuelle des deux panneaux

Ajouter une délimitation claire entre le panneau de recherche/résultats (gauche) et le panneau de détail/ajout (droite).

Solutions possibles (à choisir selon le framework) :

Une grille CSS avec un gap marqué.

flex box css avec un justify content

Effet neumorphisme (box-shadow) sur les deux panneaux

Appliquer une ombre portée douce sur chaque panneau pour un aspect en relief.

Exemple de style :

css
box-shadow: 9px 9px 16px rgba(163,177,198,0.6), -9px -9px 16px rgba(255,255,255,0.8);
Arrondis :

border-radius: 5px à 10px pour les champs de saisie (input).

border-radius: 5px à 10px pour les cartes produits.

Ajustement du carrousel (groupes de 2)

Le carrousel affiche actuellement 4 cartes par vue, ce qui provoque un débordement horizontal.

Modifier pour n’afficher que 2 cartes à la fois (sur desktop), tout en conservant la navigation (flèches ou swipe).

Adapter la largeur des cartes en conséquence (ex. flex: 0 0 50% ou grid-template-columns: repeat(2, 1fr)).

Résultat attendu

Les prix sont cohérents entre les deux panneaux.

Les deux zones sont clairement distinctes.

L’interface bénéficie d’un style neumorphique moderne et cohérent.

Le carrousel présente les produits par groupes de 2, sans débordement, fluide et responsive.