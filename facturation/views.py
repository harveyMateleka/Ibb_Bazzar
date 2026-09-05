from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from core.permissions import require_permission
from core.stats import bornes_deux_mois, comparaison_mois, compter_entre
from restauration.forms import EncaissementForm
from restauration.impression import ImpressionError
from restauration.models import Commande

from .forms import JournalForm
from .models import Etablissement, Facture
from .services import encaisser_et_facturer, imprimer_recu_caisse


def _journal_queryset(jour):
    return (
        Facture.objects.filter(date_facture__date=jour)
        .select_related('commande', 'utilisateur')
        .prefetch_related('lignes')
    )


def _totaux_journal(factures):
    par_mode = {
        code: {'code': code, 'libelle': libelle, 'nb': 0, 'montants': {}}
        for code, libelle in Commande.ModePaiement.choices
    }
    par_devise = {}
    for facture in factures:
        info = par_mode.get(facture.mode_paiement)
        if info is None:
            continue
        info['nb'] += 1
        for devise, montant in facture.totaux_par_devise.items():
            info['montants'][devise] = info['montants'].get(devise, 0) + montant
            par_devise[devise] = par_devise.get(devise, 0) + montant
    return {
        'par_mode': [info for info in par_mode.values() if info['nb']],
        'par_devise': par_devise,
        'nb': len(factures),
    }


@require_permission('facturation.view_facture')
def journal(request):
    jour = parse_date(request.GET.get('date') or '') or timezone.localdate()
    factures = list(_journal_queryset(jour))
    a_encaisser = list(
        Commande.objects.filter(statut__in=[Commande.Statut.VALIDEE, Commande.Statut.SERVIE])
        .select_related('table', 'table__salle', 'utilisateur')
        .prefetch_related('lignes')
        .order_by('date_ouverture')
    )
    debut_p, debut_c, fin_c = bornes_deux_mois()
    factures_qs = Facture.objects.all()
    comparaison = comparaison_mois([
        {
            'label': 'Reçus',
            'precedent': compter_entre(factures_qs, 'date_facture', debut_p, debut_c),
            'courant': compter_entre(factures_qs, 'date_facture', debut_c, fin_c),
        },
        {
            'label': 'Encaissements espèces',
            'precedent': compter_entre(
                factures_qs.filter(mode_paiement=Commande.ModePaiement.ESPECES),
                'date_facture', debut_p, debut_c,
            ),
            'courant': compter_entre(
                factures_qs.filter(mode_paiement=Commande.ModePaiement.ESPECES),
                'date_facture', debut_c, fin_c,
            ),
        },
        {
            'label': 'Mobile money',
            'precedent': compter_entre(
                factures_qs.filter(mode_paiement=Commande.ModePaiement.MOBILE),
                'date_facture', debut_p, debut_c,
            ),
            'courant': compter_entre(
                factures_qs.filter(mode_paiement=Commande.ModePaiement.MOBILE),
                'date_facture', debut_c, fin_c,
            ),
        },
    ])
    return render(
        request,
        'facturation/journal.html',
        {
            'form': JournalForm(initial={'date': jour}),
            'jour': jour,
            'factures': factures,
            'a_encaisser': a_encaisser,
            'resume': _totaux_journal(factures),
            'etablissement': Etablissement.actuel(),
            'comparaison': comparaison,
        },
    )


@require_permission('facturation.view_facture')
def journal_imprimer(request):
    jour = parse_date(request.GET.get('date') or '') or timezone.localdate()
    factures = list(_journal_queryset(jour))
    return render(
        request,
        'facturation/journal_impression.html',
        {
            'jour': jour,
            'factures': factures,
            'resume': _totaux_journal(factures),
            'etablissement': Etablissement.actuel(),
        },
    )


@require_permission('restauration.encaisser_commande')
def encaisser(request, pk):
    commande = get_object_or_404(
        Commande.objects.select_related(
            'table', 'table__salle', 'utilisateur'
        ).prefetch_related('lignes__plat'),
        pk=pk,
    )
    if not commande.peut_encaisser:
        messages.error(request, 'Cette commande ne peut pas être encaissée.')
        return redirect('facturation:journal')
    formulaire = EncaissementForm(request.POST or None)
    if request.method == 'POST':
        if not formulaire.is_valid():
            messages.error(request, 'Choisissez un mode de paiement.')
        else:
            try:
                facture = encaisser_et_facturer(
                    commande,
                    request.user,
                    formulaire.cleaned_data['mode_paiement'],
                )
                messages.success(
                    request,
                    f'{commande.numero} payée. Table libérée. Reçu {facture.numero} : '
                    'vérifiez l’aperçu avant d’imprimer.',
                )
                return redirect(f"{reverse('facturation:recu', args=[facture.pk])}?auto=0")
            except ValidationError as exc:
                messages.error(
                    request,
                    exc.messages[0] if getattr(exc, 'messages', None) else str(exc),
                )
    return render(
        request,
        'facturation/encaissement.html',
        {
            'commande': commande,
            'form': formulaire,
            'etablissement': Etablissement.actuel(),
        },
    )


@require_permission('facturation.view_facture')
def recu(request, pk):
    facture = get_object_or_404(
        Facture.objects.select_related(
            'commande', 'commande__table', 'commande__table__salle', 'utilisateur'
        ).prefetch_related('lignes'),
        pk=pk,
    )
    return render(
        request,
        'facturation/recu.html',
        {
            'facture': facture,
            'etablissement': Etablissement.actuel(),
            'auto_print': request.GET.get('auto') == '1',
        },
    )


@require_permission('facturation.view_facture')
@require_POST
def recu_imprimer(request, pk):
    facture = get_object_or_404(
        Facture.objects.select_related('commande'),
        pk=pk,
    )
    niveau = 'success'
    texte = ''
    try:
        cible = imprimer_recu_caisse(facture)
        if cible:
            texte = f'Reçu envoyé à l’imprimante caisse « {cible} ».'
        else:
            niveau = 'warning'
            texte = (
                'Aucune imprimante caisse n’est enregistrée. '
                'Indiquez son nom Windows dans l’établissement.'
            )
    except ImpressionError as exc:
        niveau = 'warning'
        texte = str(exc)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': niveau == 'success', 'niveau': niveau, 'message': texte})
    if niveau == 'success':
        messages.success(request, texte)
    else:
        messages.warning(request, texte)
    return redirect('facturation:recu', pk=facture.pk)
