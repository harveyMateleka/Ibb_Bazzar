from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from core.permissions import require_permission
from restauration.impression import ImpressionError
from restauration.models import Commande

from .forms import JournalForm
from .models import Etablissement, Facture
from .services import imprimer_recu_caisse


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
    try:
        cible = imprimer_recu_caisse(facture)
        if cible:
            messages.success(request, f'Reçu envoyé à l’imprimante caisse « {cible} ».')
        else:
            messages.warning(
                request,
                'Aucune imprimante caisse n’est enregistrée. '
                'Paramétrez-la dans l’établissement, ou utilisez Imprimer 80 mm.',
            )
    except ImpressionError as exc:
        messages.warning(request, str(exc))
    return redirect('facturation:recu', pk=facture.pk)
