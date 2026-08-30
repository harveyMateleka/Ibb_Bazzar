# Plan de développement — IBBS BAZAR

Application Django centralisée, multi-succursales, multi-domaines.
Base : module **Approvisionnement** existant (à préserver) + cahier des charges `promt1` (architecture centralisée : utilisateurs, succursales, boutique, immobilisations).

## Progression
- ✅ **Module Utilisateurs & Profil (FBV, dans `core`)** : liste + profil + activer/désactiver (permis `core.activate/deactivate_utilisateur`, auto-désactivation et désactivation d'un superuser bloquées). Profil : identité, compte, rôles/permissions, périmètre (succursales/domaines) et **historique d'audit** affiché. Services d'audit : `user.create/update/role_add/role_remove/activate/deactivate`. `fonction` ajoutée au profil. **37 tests OK.**
- ✅ **Correctif architecture `Prompt2`** : **Approvisionnement = module transversal, PAS un domaine**. Domaines d'activité = BOUTIQUE, RESTAURANT, IMMOBILISATIONS, ADMINISTRATION. L'accès au module se fait par permission ; le périmètre des données = intersection (succursales, domaines) des affectations. `UserSuccursale` porte désormais un `role` (affectation = succursale + domaine + rôle). Stock et mouvements contextualisés `(Article, Succursale, Domaine)`.
- ✅ **Phase 1 — Fondations `core`** : app `core`, `AUTH_USER_MODEL = core.User` (base reconstruite), `Role`, `Succursale`, `Domaine`, `UserSuccursale`, `AuditLog`, permissions granulaires (natives Django + rôles dynamiques), services métier, admin, `init_core`. **13 tests OK.**
- ✅ **Phase 2 — Sécurisation Approvisionnement (Option A, en FBV)** :
  - `succursale` ajoutée sur `Article` (unicité `code`+`succursale`), `MouvementStock`, `BonApprovisionnement`, `BonSortie`, `Inventaire` et journal `Approvisionnement` (traçabilité).
  - Vues FBV sécurisées : `@require_permission(...)` remplace `@login_required` (permissions `approvisionnement.*`).
  - Filtrage centralisé **à deux niveaux** : succursale **et** domaine d'activité (APPROVISIONNEMENT) — un utilisateur affecté à une succursale pour un autre domaine (ex. BOUTIQUE) n'accède pas aux données Approvisionnement (superuser = toutes).
  - **Stock & mouvements sur deux niveaux** : `domaine` ajouté sur `Article` (unicité `code`+`succursale`+`domaine`), `MouvementStock`, bons, inventaire et journal — un mouvement ne touche que le stock (succursale, domaine) de son article.
  - `init_core` : permissions par rôle (Magasinier, Responsable, Direction, Opérateur) + affectation admin.
  - ⚠️ **Décision : FBV conservé, PAS de DRF** — on reste dans l'approche existante (vues fonctions + templates).
  - **27 tests OK** (13 core + 14 approvisionnement).
- ✅ **Phase 3 — Backend Boutique (en FBV)** :
  - App `boutique` : `ArticleBoutique` (OneToOne Article : type/taille/couleur/SKU/prix — pas de stock dupliqué), `Vente`, `VenteLigne`.
  - **Vente** : `VenteService` (créer/ajouter_ligne/valider/annuler, transactions + audit `vente.create/validate/cancel`). Validation atomique → `MouvementStock` SORTIE (stock insuffisant refusé, **seuil non bloquant** pour une vente). Numérotation `VTE-AAAA-NNNN`. Remise/calcul total, paiement (espèces, mobile money…), monnaie.
  - **Remises** contrôlées par permission `boutique.apply_remise` (refusées pour un profil non autorisé).
  - **Règles métier ajoutées** : `prix_limite` sur `ArticleBoutique` (prix plancher — refus côté formulaire ET côté `Vente.valider()` si prix < limite) ; **aucune sortie (vente ou bon de sortie) si `stock <= seuil_minimum`** (blocage dur dans `MouvementStock.valider()`, autorisation propriétaire supprimée).
- ✅ **Règles métier (`prompt_regle_metier`)** :
  - **Succursale + domaine auto-remplis et verrouillés** (readonly) selon l'utilisateur connecté : `User.contexte_actif()` + `appliquer_contexte()` — appliqué à l'entrée, la sortie, l'inventaire et la vente. Contexte verrouillé si affectation principale/unique (non-superuser) ; libre pour superuser. Toute tentative de modification est ignorée (cohérence).
  - **Validation du bon d'approvisionnement** : le **fournisseur** (+ référence/commentaire) et **chaque quantité** restent modifiables (`BonValidationForm` + `LigneValidationFormSet`).
  - **Création du bon avec lignes intégrées** : le formulaire « Nouvel approvisionnement » inclut désormais directement la saisie **articles + quantités** (bon + lignes créés en une seule soumission transactionnelle).
  - **Inventaire avec périmètre au choix** : inventaire à une **date** (jour du comptage), **Complet** (tous les articles du périmètre) ou **Un article** précis ; principale du superuser = BOUTIQUE (contexte par défaut des bons).
  - Permissions `boutique.*` (`view_boutique`, `view_stock`, `create/validate/cancel_vente`, `apply_remise`, `adjust_stock`) ; intégrées aux rôles (Caissier, Responsable, Direction, etc.).
  - Périmètre = succursales affectées au **domaine BOUTIQUE** ; vues filtrées (accès interdit à une autre succursale).
  - Vues FBV : dashboard, articles, ventes (liste/nouvelle/détail/valider/annuler/imprimer). **Templates minimales (le vrai frontend est à faire).**
  - **50 tests OK** au total.
- ✅ **Harmonisation UI (prompt_frontend)** — Boutique et Utilisateurs alignés sur le design system d'Approvisionnement (même `base.html`/`brand.css`) :
  - **Boutique** : dashboard avec cartes stats (articles, stock total, alertes, ventes du jour), « État des stocks », « Dernières ventes » ; sous-nav Tableau de bord / Articles / Ventes / Inventaire / Historique.
  - **Utilisateurs** : dashboard (stats + dernières activités), sous-nav Tableau de bord / Utilisateurs / Rôles / Succursales / Permissions / Audit ; formulaire « Nouvel utilisateur » ; pages Rôles, Succursales, Permissions, Audit.
  - **Immobilisations** : frontend reporté (le backend Phase 4 n'existe pas encore).
- ⬜ **Phase 4 — Immobilisations** (backend puis frontend).

---

## 1. Analyse technique de l'existant

### 1.1 Le cahier des charges (`Classeur1.xlsx` → 6 fonctionnalités APP-01 à APP-06)
| Code | Module | Fonctionnalité | Acteurs |
|---|---|---|---|
| APP-01 | Approvisionnement | Créer article | Administrateur / Responsable |
| APP-02 | Approvisionnement | Entrée stock | Magasinier / Responsable |
| APP-03 | Approvisionnement | Sortie stock | Magasinier / Responsable |
| APP-04 | Approvisionnement | Alerte stock | Responsable |
| APP-05 | Approvisionnement | Historique mouvements | Responsable |
| APP-06 | Approvisionnement | Inventaire | Responsable |

Ces fonctionnalités ont déjà été **importées en base** via la commande
`importer_classeur` (modèles `Module`, `Acteur`, `Fonctionnalite`).

### 1.2 Ce qui est DÉJÀ FAIT et fonctionnel (app `approvisionnement`)
**18 modèles :**
- Référentiel cahier des charges : `Module`, `Acteur`, `Fonctionnalite`
- Paramètres : `Categorie` (+ `nombre_portions`), `Unite`, `Fournisseur`, `Service`
- Stock : `Article` (`code`, `designation`, `categorie`, `unite`, `seuil_minimum`, **`stock`**)
- Mouvements : `MouvementStock` (`ENTREE`/`SORTIE`/`AJUSTEMENT`, `stock_avant/apres`, `valide`,
  `autorisation_depassement`, `nombre_portions`)
- Opérations : `BonApprovisionnement` + `LigneApprovisionnement`,
  `BonSortie` + `LigneSortie`, `Inventaire` + `LigneInventaire`
- Journal : `Approvisionnement` + `ApprovisionnementLigne`, `AlerteStock`

**Logique métier déjà solide (à préserver) :**
- `transaction.atomic()` + `select_for_update()` (verrouillage de l'article à chaque mouvement) — `models.py:179,316,516`
- Contrôles : stock à 0 refusé, quantité > stock refusée, seuil minimum → autorisation du propriétaire
- Numérotation automatique `APP-AAAA-NNNN` / `SOR-AAAA-NNNN` (avec `select_for_update`)
- Génération automatique des alertes de stock après chaque mouvement
- Journal d'historique unique (`Approvisionnement.enregistrer_entree/sortie`)
- Impression de bons (entrée/sortie)

**Frontend existant (ne PAS refaire) :** templates Django complètes (dashboard, entrées, sorties,
inventaires, historique, impression) + admin Django pour les tables de paramètres.

**Points faibles / manques par rapport à `promt1` :**
1. **Aucun `AUTH_USER_MODEL` custom** → l'utilisateur est le `User` Django par défaut,
   sans profil, rôle, succursale. (`settings.py` n'en définit pas.)
2. **`Article.stock` est une quantité GLOBALE unique** → aucune séparation par succursale/domaine.
3. **Aucune permission granulaire** : les vues sont uniquement protégées par `@login_required`.
4. **Aucune notion de succursale / établissement / domaine d'activité.**
5. **Aucune API** (pas de DRF) — le frontend actuel est en templates.
6. **Aucun test** (`tests.py` vide).
7. **Aucun audit centralisé.**
8. Pas de module **Boutique** ni **Immobilisations**.

### 1.3 Modèles existants qui devront être MODIFIÉS
- **`Article`** — ajout du contexte `succursale` (+ éventuellement `domaine`) pour la
  séparation des stocks (voir décision D2).
- **`settings.AUTH_USER_MODEL`** — à définir via un custom `User` (décision D1).

> Les modèles métier d'approvisionnement (`BonApprovisionnement`, `BonSortie`,
> `MouvementStock`, `Inventaire`, etc.) ne doivent PAS être réécrits : on ajoute le
> contexte (succursale/domaine) par rétrocompatibilité.

### 1.4 Nouveaux modèles nécessaires
| App | Modèle | Rôle |
|---|---|---|
| `core` | `User` (custom) | Utilisateur central : identité, téléphone, créé par, date de désactivation |
| `core` | `Role` | Rôles dynamiques (Administrateur, Direction, Responsable, Magasinier, Caissier…) |
| `core` | `Permission` (custom + celles de Django) | Permissions par action (`users.view`, `boutique.sale.create`…) |
| `core` | `Succursale` | Établissement / site |
| `core` | `Domaine` | Domaine d'activité : RESTAURANT, BOUTIQUE, APPROVISIONNEMENT, IMMOBILISATIONS, ADMINISTRATION |
| `core` | `UserSuccursale` (through) | Rattachement utilisateur ↔ succursale ↔ domaine (+ principale) |
| `core` | `AuditLog` | Audit centralisé (qui, quand, quoi, avant/après, IP) |
| `boutique` | `ArticleBoutique` / variantes | Informations habillement (taille, couleur, SKU, prix) liées à `Article` |
| `boutique` | `Vente`, `VenteLigne` | Ventes, remises (contrôlées par permission), paiements |
| `boutique` | `Retour`, `RetourLigne` | Retours / échanges (entrée stock) |
| `immobilisations` | `Immobilisation` | Bien : code, série, valeur, état, statut, emplacement |
| `immobilisations` | `Affectation`, `Deplacement`, `Casse`, `Reparation`, `Declassement` | Cycle de vie historisé |

---

## 2. Décisions critiques à valider AVANT d'écrire du code

### D1 — Custom `AUTH_USER_MODEL` (obligatoire, maintenant ou jamais)
`promt1` impose un utilisateur riche et un `AUTH_USER_MODEL` commun.
**Le moment idéal est MAINTENANT : la base est vide** (aucune donnée de production).
- Créer l'app `core`, un `User(AbstractUser)` étendu (téléphone, `cree_par`, `date_desactivation`, rôle),
  poser `AUTH_USER_MODEL = 'core.User'` dans `settings.py`.
- Reconstruire la base (supprimer `db.sqlite3`, relancer `migrate`) — aucune perte de données réelle.
- ⚠️ Ce changement est **impossible à différer** : le faire plus tard obligerait à des migrations
  douloureuses. À valider avec le client.

### D2 — Séparation du stock par succursale
Deux options compatibles avec `promt1` (§12-13 : « Article + Succursale + Domaine ») :
- **Option A (recommandée, peu invasive)** : ajouter `succursale` (FK) sur `Article`
  et rendre `unique_together(code, succursale)`. Le champ `stock` reste sur `Article`
  mais est désormais **par succursale**. Toute la logique existante (`MouvementStock`,
  alertes, inventaires) fonctionne **sans réécriture**.
- **Option B** : créer `StockArticle` (article + succursale + domaine + quantité + seuil)
  et retirer `Article.stock` → implique de réécrire **toutes** les occurrences de
  `Article.stock` (vues, modèles, templates, admin).

> Recommandation : **Option A** + éventuel champ `domaine`/emplacement en Phase 3.
> L'utilisateur verra une liste « Article » par succursale.

---

## 3. Plan de travail par phases (ordre imposé par `promt1`)

### PHASE 1 — Fondations & app `core` (utilisateurs d'abord) ✅ FAITE
Créer l'app **`core`** (le point de contrôle central).

**Modèles :**
1. `User(AbstractUser)` — `telephone`, `cree_par` (FK self), `date_desactivation`
2. `Role` — `nom`, `code`, `description`, M2M vers permissions
3. `Succursale` — `nom`, `code` unique, `adresse`, `actif`, `description`
4. `Domaine` — `code` (BOUTIQUE, RESTAURANT, APPROVISIONNEMENT, IMMOBILISATIONS, ADMINISTRATION), `libelle`
5. `UserSuccursale` (through `user`, `succursale`, `domaine`, `principale`) + `SuccursalePrincipale` optionnelle
6. `AuditLog` — `utilisateur`, `succursale`, `module`, `action`, `objet_type`, `objet_id`, `avant`, `apres`, `ip`

**Permissions granulares** via le système de permissions Django (codenames) :
`users.view/create/update/activate/deactivate`, `roles.*`, `permissions.view`,
`audit.view`, `boutique.*`, `asset.*`, `approvisionnement.*`.

**Services métier (transactionnels) :**
`UserService`, `RoleService`, `PermissionService`, `SuccursaleService`.

**Système de filtrage centralisé :**
Mixin / décorateur qui calcule automatiquement le périmètre
(utilisateur → succursales autorisées → domaine → QuerySet filtré).
Testé par une batterie de tests.

**Livrables :** `AUTH_USER_MODEL` configuré, base recréée, migrations, admin, tests.

### PHASE 2 — Sécurisation de l'existant (rétrocompatible)
1. Remplacer les simples `@login_required` par un décorateur de permission
   (`require_permission('approvisionnement.view')`) + contrôle de succursale.
2. Ajouter le contexte `succursale`/`domaine` sur `Article` (Décision D2 — Option A)
   avec migration **rétrocompatible** (les articles existants sont rattachés à une succursale par défaut).
3. Vérifier qu'aucune fonctionnalité d'approvisionnement n'est cassée (tests de non-régression).
4. Créer les **API DRF** nécessaires (endpoints exposés, filtrés par périmètre),
   sans toucher aux templates existantes.

**Livrables :** permissions actives sur Approvisionnement, stock séparé par succursale,
API de base, tests.

### PHASE 3 — Module BOUTIQUE
- `ArticleBoutique` / **variantes** (T-shirt / Noir / M…) rattachées à `Article` (SKU, taille, couleur, prix achat/vente).
- **Approvisionnement → Boutique** : réutiliser `BonApprovisionnement` + `MouvementStock ENTREE` (aucune duplication de stock).
- **Vente** : `Vente`, `VenteLigne`, validation atomique → `MouvementStock SORTIE`.
- **Remises** : contrôlées par permission (ex. responsable jusqu'à X %, direction plus) — règles **côté backend**.
- **Retours / échanges** : structures prévues (activables en V2).
- **Inventaire boutique** : réutiliser `Inventaire`/`LigneInventaire` + contexte succursale/domaine.
- API DRF + tests.

**Livrables :** ventes, remises, mouvements boutique, tests.

### PHASE 4 — Module IMMOBILISATIONS
- `Immobilisation` : code, désignation, catégorie, `article_source` éventuel, n° série,
  valeur acquisition, fournisseur, succursale, état (NEUF/BON/A_REPARER/CASSE),
  statut administratif, emplacement, service, utilisateur affecté.
- **Cycle de vie historisé** : `Affectation`, `Deplacement`, `Casse` (déclaration → évaluation → décision),
  `Reparation`, `Declassement` (opération **contrôlée par permission**, jamais de suppression physique).
- API DRF + tests.

**Livrables :** immobilisations + cycle de vie complet, tests.

### PHASE 5 — Audit & vérification globale
- Couvrir toutes les opérations sensibles par `AuditLog` (utilisateurs, boutique, immobilisations, approvisionnement).
- Passer en revue chaque endpoint : authentifié → actif → permission → succursale → périmètre → objet → opération.
- Vérifier l'absence de suppression physique sur les objets métier (PROTECT partout).
- **Recette finale** : scénarios de bout en bout.

**Livrables :** audit complet, matrice de permissions, rapport de recette.

---

## 4. Risques de régression & mesures

| Risque | Impact | Mesure |
|---|---|---|
| Changement `AUTH_USER_MODEL` | Élevé si fait tard | Le faire maintenant (base vide) ; recréer `db.sqlite3` |
| Ajout `succursale` sur `Article` | Moyen (unicité `code`) | Migration rétrocompatible + rattachement par défaut |
| Suppression de `Article.stock` | Élevé | **Non retenu** (Option A conserve le champ) |
| Réécriture de l'existant | Élevé | **Interdite** : on étend, on ne réécrit pas |
| Perte de l'historique | Moyen | `PROTECT`, pas de suppression physique |
| Frontend cassé | Moyen | Aucune modification de template dans cette phase ; API ajoutées, vues conservées |

---

## 5. Contraintes globales (rappel)
- **BACKEND FIRST** : aucune modification du frontend dans cette phase.
- **Préserver `Approvisionnement`** : analyser avant toute modification, migration testée.
- **Un seul système d'utilisateurs / articles / stocks** : pas de doublons.
- **Toutes les opérations :** authentifiées, autorisées, rattachées à une succursale et à un utilisateur, historisées.
- **Tests backend** à chaque phase avant de passer à la suivante.
