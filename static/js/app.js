/* IBBS BAZAR — standardisation frontend DataTable + Select2 (design conservé).
   Les bibliothèques (jQuery/DataTables/Select2) sont chargées en CDN. Si elles
   sont indisponibles, l'application reste fonctionnelle : tout est gardé. */
(function (window, document) {
  'use strict';

  var $ = window.jQuery;

  /* --- DataTable : tri + recherche + pagination + info côté client.
     Les tableaux restent paginés côté serveur (25/page) ; DataTable applique
     ses contrôles sur la page serveur courante (recherche/tri/pagination
     client), la pagination Django et la recherche serveur restent actives. */
  function initDataTables(root) {
    if (!$ || !$.fn || !$.fn.DataTable) return;
    $(root || document).find('table[data-datatable]').each(function () {
      var table = $(this);
      if ($.fn.DataTable.isDataTable(table)) return;
      // Les lignes « Aucune… » à <td colspan=N> provoquent l'erreur DataTable
      // « Incorrect column count » (tn/18) : on les retire avant l'init
      // (DataTable affiche alors « Aucun résultat » via zeroRecords).
      table.find('tbody tr').each(function () {
        var $td = $(this).children('td');
        if ($td.length === 1 && $td.attr('colspan')) {
          $(this).remove();
        }
      });
      table.DataTable({
        paging: true,
        searching: true,
        info: true,
        ordering: true,
        order: [],
        pageLength: 25,
        lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
        language: {
          search: 'Rechercher :',
          lengthMenu: 'Afficher _MENU_ éléments',
          info: 'Affichage de _START_ à _END_ sur _TOTAL_ élément(s)',
          infoEmpty: 'Aucun élément',
          infoFiltered: '(filtré sur _MAX_ éléments au total)',
          zeroRecords: 'Aucun résultat',
          loadingRecords: 'Chargement…',
          paginate: { first: '«', last: '»', next: '›', previous: '‹' }
        }
      });
    });
  }

  /* --- Select2 : recherche dans toutes les listes déroulantes des formulaires
     (article, variante, succursale, service, etc.). Seule la barre de filtres
     (mise en page `.filters`) est conservée telle quelle. */
  function initSelect2(root) {
    if (!$ || !$.fn || !$.fn.select2) return;
    var $root = $(root || document);
    var $selects = $root.is('select') ? $root : $root.find('select');
    $selects
      .not('[data-article-ligne]')  // lignes de vente : sélection via le panneau droit
      .not('[data-skip-select2]')
      .filter(function () { return !$(this).closest('.filters').length; })
      .each(function () {
        var $sel = $(this);
        if ($sel.data('select2')) return;
        $sel.select2({ width: '100%' });
      });
  }

  function signalerSelect2Pret() {
    document.dispatchEvent(new CustomEvent('ibbs:select2:init'));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initDataTables(document);
      initSelect2(document);
      signalerSelect2Pret();
    });
  } else {
    initDataTables(document);
    initSelect2(document);
    signalerSelect2Pret();
  }

  window.initSelect2 = initSelect2;
  window.initDataTables = initDataTables;
})(window, document);
