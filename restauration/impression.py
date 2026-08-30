import json
import subprocess
import tempfile
import time
from pathlib import Path

from django.utils import timezone

_CACHE_IMPRIMANTES = (0.0, [])
_CACHE_TTL = 30


class ImpressionError(Exception):
    pass


def lister_imprimantes_windows():
    """Noms des imprimantes installées sur ce poste Windows."""
    global _CACHE_IMPRIMANTES
    maintenant = time.time()
    age, noms = _CACHE_IMPRIMANTES
    if noms and maintenant - age < _CACHE_TTL:
        return list(noms)
    try:
        resultat = subprocess.run(
            [
                'powershell',
                '-NoProfile',
                '-ExecutionPolicy', 'Bypass',
                '-Command',
                'Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name',
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        trouves = [ligne.strip() for ligne in resultat.stdout.splitlines() if ligne.strip()]
    except (OSError, subprocess.TimeoutExpired):
        trouves = []
    _CACHE_IMPRIMANTES = (maintenant, trouves)
    return list(trouves)


def resoudre_imprimante_windows(nom):
    nom = (nom or '').strip()
    if not nom:
        return ''
    installes = lister_imprimantes_windows()
    for installe in installes:
        if installe.casefold() == nom.casefold():
            return installe
    return ''


def texte_ticket(commande, groupe):
    heure = commande.date_validation or commande.date_ouverture or timezone.now()
    heure = timezone.localtime(heure)
    lignes = [
        'IBBS BAZAR',
        str(groupe['libelle']).upper(),
        f"Commande {commande.numero}",
        f"{commande.nom_emplacement}  {commande.nom_serveur}",
        '-' * 32,
    ]
    for ligne in groupe['lignes']:
        lignes.append(f'{ligne.quantite} x {ligne.libelle}')
        if getattr(ligne, 'note', ''):
            lignes.append(f'  ({ligne.note})')
    lignes.extend([
        '-' * 32,
        heure.strftime('%d/%m/%Y %H:%M'),
        '',
    ])
    return '\r\n'.join(lignes)


def envoyer_texte_imprimante(nom_imprimante, texte):
    cible = resoudre_imprimante_windows(nom_imprimante)
    if not cible:
        raise ImpressionError(
            f'Imprimante « {nom_imprimante} » introuvable sur ce poste. '
            'Enregistrez le nom Windows exact dans Paramètres → Imprimantes.'
        )
    with tempfile.NamedTemporaryFile(
        mode='w',
        encoding='utf-8-sig',
        suffix='.txt',
        delete=False,
        newline='\r\n',
    ) as tmp:
        tmp.write(texte)
        chemin = tmp.name
    try:
        commande_ps = (
            f'Get-Content -LiteralPath {json.dumps(chemin)} -Raw -Encoding UTF8 '
            f'| Out-Printer -Name {json.dumps(cible)}'
        )
        resultat = subprocess.run(
            [
                'powershell',
                '-NoProfile',
                '-ExecutionPolicy', 'Bypass',
                '-Command',
                commande_ps,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if resultat.returncode != 0:
            detail = (resultat.stderr or resultat.stdout or '').strip()
            raise ImpressionError(
                f'Échec d’impression sur « {cible} »'
                + (f' : {detail}' if detail else '.')
            )
    finally:
        Path(chemin).unlink(missing_ok=True)
    return cible


def imprimer_commande_aux_postes(commande):
    """Envoie un ticket par service/imprimante. Les plats terrasse n’impriment qu’à la terrasse."""
    resultats = []
    for groupe in commande.groupes_impression():
        imprimante = groupe['imprimante']
        item = {
            'service': groupe['service'],
            'libelle': groupe['libelle'],
            'imprimante': imprimante,
            'nb_lignes': len(groupe['lignes']),
            'ok': False,
            'erreur': '',
        }
        if not groupe['lignes']:
            continue
        if not imprimante:
            item['erreur'] = (
                f'Aucun nom d’imprimante enregistré pour le service {groupe["libelle"]}.'
            )
            resultats.append(item)
            continue
        try:
            item['imprimante'] = envoyer_texte_imprimante(
                imprimante,
                texte_ticket(commande, groupe),
            )
            item['ok'] = True
        except ImpressionError as exc:
            item['erreur'] = str(exc)
        resultats.append(item)
    return resultats
