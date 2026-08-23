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

  /* --- Select2 : recherche dans les listes déroulantes des formulaires.
     Exclus les selects des lignes dynamiques de vente (JS vanilla dédié) et la
     barre de filtres (mise en page `.filters` conservée). */
  function initSelect2(root) {
    if (!$ || !$.fn || !$.fn.select2) return;
    $(root || document).find('select.input')
      .not('[data-article-ligne]')
      .filter(function () { return !$(this).closest('.filters').length; })
      .each(function () {
        var $sel = $(this);
        if ($sel.data('select2')) return;
        $sel.select2({ width: '100%' });
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initDataTables(document);
      initSelect2(document);
    });
  } else {
    initDataTables(document);
    initSelect2(document);
  }

  window.initSelect2 = initSelect2;
  window.initDataTables = initDataTables;
})(window, document);
