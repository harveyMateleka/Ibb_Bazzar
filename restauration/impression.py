import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from django.utils import timezone

_CACHE_IMPRIMANTES = (0.0, [])
_CACHE_TTL = 30

# Police A ESC/POS sur rouleau 80 mm : 42 colonnes. 32 colonnes laissait
# une bande vide ; Out-Printer ajoutait encore les marges d’un document A4.
LARGEUR_TICKET = 42

ESC = b'\x1b'
GS = b'\x1d'

_REMPLACEMENTS_TICKET = str.maketrans({
    '×': 'x',
    '–': '-',
    '—': '-',
    '’': "'",
    '‘': "'",
    '«': '"',
    '»': '"',
    '\u00a0': ' ',
})

_PS_RAW = r'''
param(
  [Parameter(Mandatory=$true)][string]$Printer,
  [Parameter(Mandatory=$true)][string]$File
)
$source = @"
using System;
using System.Runtime.InteropServices;

public class IbbsRawPrinter {
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Ansi)]
  public class DOCINFOA {
    [MarshalAs(UnmanagedType.LPStr)] public string pDocName;
    [MarshalAs(UnmanagedType.LPStr)] public string pOutputFile;
    [MarshalAs(UnmanagedType.LPStr)] public string pDataType;
  }
  [DllImport("winspool.drv", EntryPoint="OpenPrinterA", SetLastError=true, CharSet=CharSet.Ansi, ExactSpelling=true)]
  public static extern bool OpenPrinter(string szPrinter, out IntPtr hPrinter, IntPtr pd);
  [DllImport("winspool.drv", EntryPoint="ClosePrinter", SetLastError=true)]
  public static extern bool ClosePrinter(IntPtr hPrinter);
  [DllImport("winspool.drv", EntryPoint="StartDocPrinterA", SetLastError=true, CharSet=CharSet.Ansi, ExactSpelling=true)]
  public static extern int StartDocPrinter(IntPtr hPrinter, int level, [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOA di);
  [DllImport("winspool.drv", EntryPoint="EndDocPrinter", SetLastError=true)]
  public static extern bool EndDocPrinter(IntPtr hPrinter);
  [DllImport("winspool.drv", EntryPoint="StartPagePrinter", SetLastError=true)]
  public static extern bool StartPagePrinter(IntPtr hPrinter);
  [DllImport("winspool.drv", EntryPoint="EndPagePrinter", SetLastError=true)]
  public static extern bool EndPagePrinter(IntPtr hPrinter);
  [DllImport("winspool.drv", EntryPoint="WritePrinter", SetLastError=true)]
  public static extern bool WritePrinter(IntPtr hPrinter, IntPtr pBytes, int dwCount, out int dwWritten);

  public static bool SendFileToPrinter(string printerName, string filePath) {
    byte[] bytes = System.IO.File.ReadAllBytes(filePath);
    IntPtr hPrinter = IntPtr.Zero;
    if (!OpenPrinter(printerName, out hPrinter, IntPtr.Zero)) return false;
    DOCINFOA di = new DOCINFOA();
    di.pDocName = "Ticket IBBS";
    di.pDataType = "RAW";
    try {
      if (StartDocPrinter(hPrinter, 1, di) <= 0) return false;
      if (!StartPagePrinter(hPrinter)) { EndDocPrinter(hPrinter); return false; }
      IntPtr unmanaged = Marshal.AllocCoTaskMem(bytes.Length);
      Marshal.Copy(bytes, 0, unmanaged, bytes.Length);
      int written = 0;
      bool ok = WritePrinter(hPrinter, unmanaged, bytes.Length, out written);
      Marshal.FreeCoTaskMem(unmanaged);
      EndPagePrinter(hPrinter);
      EndDocPrinter(hPrinter);
      return ok && written == bytes.Length;
    } finally {
      ClosePrinter(hPrinter);
    }
  }
}
"@
Add-Type -TypeDefinition $source -Language CSharp
if (-not [IbbsRawPrinter]::SendFileToPrinter($Printer, $File)) {
  throw "Envoi RAW refuse par l'imprimante"
}
'''

_PS_GDI = r'''
param(
  [Parameter(Mandatory=$true)][string]$Printer,
  [Parameter(Mandatory=$true)][string]$File
)
Add-Type -AssemblyName System.Drawing
$lines = [System.IO.File]::ReadAllLines($File, [System.Text.Encoding]::UTF8)
$doc = New-Object System.Drawing.Printing.PrintDocument
$doc.PrinterSettings.PrinterName = $Printer
if (-not $doc.PrinterSettings.IsValid) { throw "Imprimante invalide" }
$doc.DocumentName = "Ticket IBBS"
$doc.PrintController = New-Object System.Drawing.Printing.StandardPrintController
$doc.DefaultPageSettings.Landscape = $false
$doc.DefaultPageSettings.Margins = New-Object System.Drawing.Printing.Margins(8, 8, 10, 10)
$roll = $doc.PrinterSettings.PaperSizes | Where-Object { $_.PaperName -match '80' } | Select-Object -First 1
if ($roll) {
  $doc.DefaultPageSettings.PaperSize = $roll
} else {
  $doc.DefaultPageSettings.PaperSize = New-Object System.Drawing.Printing.PaperSize("Ticket80", 315, 4000)
}
$doc.add_PrintPage({
  param($sender, $e)
  $e.Graphics.Clear([System.Drawing.Color]::White)
  $e.Graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::SingleBitPerPixelGridFit
  $left = $e.MarginBounds.Left
  $width = [Math]::Max(40, $e.MarginBounds.Width)
  $y = $e.MarginBounds.Top
  $probe = New-Object System.Drawing.Font("Consolas", 20, [System.Drawing.FontStyle]::Bold)
  $probeW = $e.Graphics.MeasureString(("M" * 42), $probe).Width
  $size = 12
  if ($probeW -gt 0) { $size = [Math]::Max(9, [Math]::Min(16, 20 * $width / $probeW)) }
  $probe.Dispose()
  $font = New-Object System.Drawing.Font("Consolas", $size, [System.Drawing.FontStyle]::Bold)
  $brush = [System.Drawing.Brushes]::Black
  $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::Black, 2)
  $lineH = $font.GetHeight($e.Graphics)
  foreach ($line in $lines) {
    if ($line -match '^-+$') {
      $mid = $y + [int]($lineH / 2)
      $e.Graphics.DrawLine($pen, $left, $mid, $left + $width, $mid)
    } else {
      $e.Graphics.DrawString($line, $font, $brush, [float]$left, [float]$y)
    }
    $y += $lineH
  }
  $font.Dispose()
  $pen.Dispose()
  $e.HasMorePages = $false
})
$doc.Print()
$doc.Dispose()
'''


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


def _encoder_ticket(texte):
    normalise = (texte or '').translate(_REMPLACEMENTS_TICKET)
    try:
        return normalise.encode('cp850', errors='replace')
    except LookupError:
        return normalise.encode('latin-1', errors='replace')


def octets_escpos(texte, compact=False):
    """Ticket ESC/POS : police native 80 mm, gras, en-tête plus grand, coupe."""
    lignes = (texte or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out = bytearray()
    out += ESC + b'@'
    out += ESC + b't' + bytes([2])
    out += ESC + b'3' + bytes([30 if compact else 36])

    en_tete = 0
    corps = False
    for ligne in lignes:
        if en_tete < 2 and ligne.strip():
            out += ESC + b'a' + bytes([1])
            out += ESC + b'E' + bytes([1])
            if len(ligne.strip()) <= LARGEUR_TICKET // 2:
                out += GS + b'!' + bytes([0x11])
            else:
                out += GS + b'!' + bytes([0x01])
            out += _encoder_ticket(ligne.strip()) + b'\n'
            en_tete += 1
            continue
        if not corps:
            out += ESC + b'a' + bytes([0])
            if compact:
                out += ESC + b'E' + bytes([0])
                out += GS + b'!' + bytes([0x00])
                out += ESC + b'!' + bytes([0x00])
            else:
                out += ESC + b'E' + bytes([1])
                out += GS + b'!' + bytes([0x01])
            corps = True
        out += _encoder_ticket(ligne) + b'\n'

    out += b'\n\n'
    out += GS + b'V' + bytes([66, 3])
    return bytes(out)


def texte_ticket(commande, groupe):
    heure = commande.date_validation or commande.date_ouverture or timezone.now()
    heure = timezone.localtime(heure)
    lignes = [
        'IBBS BAZAR',
        str(groupe['libelle']).upper(),
    ]
    if groupe.get('ajout'):
        lignes.append('AJOUT')
    lignes.extend([
        f"Commande {commande.numero}",
        f"{commande.nom_emplacement}  {commande.nom_serveur}",
        '-' * LARGEUR_TICKET,
    ])
    for ligne in groupe['lignes']:
        lignes.append(f'{ligne.quantite} x {ligne.libelle}')
        if getattr(ligne, 'note', ''):
            lignes.append(f'  ({ligne.note})')
    lignes.extend([
        '-' * LARGEUR_TICKET,
        heure.strftime('%d/%m/%Y %H:%M'),
        '',
    ])
    return '\r\n'.join(lignes)


def _powershell_fichier(script, args, timeout=30):
    resultat = subprocess.run(
        [
            'powershell',
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File',
            script,
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if resultat.returncode != 0:
        detail = (resultat.stderr or resultat.stdout or '').strip()
        raise ImpressionError(detail or 'Échec PowerShell.')
    return resultat


def _envoyer_brut_winspool(cible, payload):
    bin_fd, bin_path = tempfile.mkstemp(suffix='.bin')
    ps_fd, ps_path = tempfile.mkstemp(suffix='.ps1')
    os.close(bin_fd)
    os.close(ps_fd)
    try:
        Path(bin_path).write_bytes(payload)
        Path(ps_path).write_text(_PS_RAW, encoding='ascii')
        _powershell_fichier(ps_path, ['-Printer', cible, '-File', bin_path])
    finally:
        Path(bin_path).unlink(missing_ok=True)
        Path(ps_path).unlink(missing_ok=True)


def _envoyer_gdi_80mm(cible, texte):
    txt_fd, txt_path = tempfile.mkstemp(suffix='.txt')
    ps_fd, ps_path = tempfile.mkstemp(suffix='.ps1')
    os.close(txt_fd)
    os.close(ps_fd)
    try:
        Path(txt_path).write_text(
            (texte or '').replace('\r\n', '\n'),
            encoding='utf-8',
        )
        Path(ps_path).write_text(_PS_GDI, encoding='ascii')
        _powershell_fichier(ps_path, ['-Printer', cible, '-File', txt_path])
    finally:
        Path(txt_path).unlink(missing_ok=True)
        Path(ps_path).unlink(missing_ok=True)


def _envoyer_out_printer(cible, texte):
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
                '-ExecutionPolicy',
                'Bypass',
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
            raise ImpressionError(detail or 'Échec Out-Printer.')
    finally:
        Path(chemin).unlink(missing_ok=True)


def envoyer_texte_imprimante(nom_imprimante, texte, compact=False):
    """Envoie le ticket en ESC/POS brut (largeur native 80 mm), sinon GDI, sinon Out-Printer."""
    cible = resoudre_imprimante_windows(nom_imprimante)
    if not cible:
        raise ImpressionError(
            f'Imprimante « {nom_imprimante} » introuvable sur ce poste. '
            'Enregistrez le nom Windows exact dans Paramètres → Imprimantes.'
        )
    erreurs = []
    try:
        _envoyer_brut_winspool(cible, octets_escpos(texte, compact=compact))
        return cible
    except (ImpressionError, OSError, subprocess.TimeoutExpired) as exc:
        erreurs.append(str(exc) or 'RAW')
    try:
        _envoyer_gdi_80mm(cible, texte)
        return cible
    except (ImpressionError, OSError, subprocess.TimeoutExpired) as exc:
        erreurs.append(str(exc) or 'GDI')
    try:
        _envoyer_out_printer(cible, texte)
        return cible
    except (ImpressionError, OSError, subprocess.TimeoutExpired) as exc:
        erreurs.append(str(exc) or 'Out-Printer')
    detail = ' ; '.join(partie for partie in erreurs if partie)
    raise ImpressionError(
        f'Échec d’impression sur « {cible} »'
        + (f' : {detail}' if detail else '.')
    )


def imprimer_commande_aux_postes(commande, service=None, imprimante=None):
    """Envoie un ticket par service/imprimante. Les plats terrasse n’impriment qu’à la terrasse."""
    filtre_service = service
    filtre_imprimante = imprimante
    resultats = []
    for groupe in commande.groupes_impression():
        if filtre_service and groupe['service'] != filtre_service:
            continue
        if filtre_imprimante is not None and (groupe['imprimante'] or '') != filtre_imprimante:
            continue
        nom_imprimante = groupe['imprimante']
        item = {
            'service': groupe['service'],
            'libelle': groupe['libelle'],
            'imprimante': nom_imprimante,
            'nb_lignes': len(groupe['lignes']),
            'ok': False,
            'erreur': '',
        }
        if not groupe['lignes']:
            continue
        if not nom_imprimante:
            item['erreur'] = (
                f'Aucun nom d’imprimante enregistré pour le service {groupe["libelle"]}.'
            )
            resultats.append(item)
            continue
        try:
            item['imprimante'] = envoyer_texte_imprimante(
                nom_imprimante,
                texte_ticket(commande, groupe),
            )
            item['ok'] = True
            commande.marquer_lignes_imprimees(groupe['lignes'])
        except ImpressionError as exc:
            item['erreur'] = str(exc)
        resultats.append(item)
    return resultats
