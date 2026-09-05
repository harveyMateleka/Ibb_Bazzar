(function () {
  const langueFr = {
    search: "Rechercher :",
    lengthMenu: "Afficher _MENU_ lignes",
    info: "Affichage de _START_ à _END_ sur _TOTAL_ lignes",
    infoEmpty: "Aucune ligne à afficher",
    infoFiltered: "(filtré sur _MAX_ lignes)",
    zeroRecords: "Aucun résultat",
    emptyTable: "Aucune donnée disponible",
    paginate: {
      first: "Premier",
      last: "Dernier",
      next: "Suivant",
      previous: "Précédent",
    },
  };

  function estTableSaisie(table) {
    return Boolean(
      table.closest("form") && table.querySelector("input:not([type='hidden']), select, textarea")
    );
  }

  function colonnesNonTriables(table) {
    const indexes = [];
    table.querySelectorAll("thead th").forEach(function (th, index) {
      if (th.classList.contains("_nosort")) indexes.push(index);
    });
    return indexes;
  }

  if (window.jQuery) {
    jQuery(function ($) {
      $("table.js-datatable").each(function () {
        const table = this;
        const tbody = table.tBodies[0];
        if (!tbody || !tbody.rows.length) return;
        if (tbody.rows[0].querySelector("td[colspan]")) return;
        if ($.fn.DataTable.isDataTable(table)) return;

        const options = {
          language: langueFr,
          order: [],
          autoWidth: false,
          pageLength: 10,
          lengthMenu: [10, 25, 50, 100],
        };
        const nonTriables = colonnesNonTriables(table);
        if (nonTriables.length) {
          options.columnDefs = [{ orderable: false, targets: nonTriables }];
        }
        if (estTableSaisie(table)) {
          return;
        }
        try {
          $(table).DataTable(options);
        } catch (erreur) {
          console.error("DataTable :", erreur);
        }
      });
    });
  }

  function jquerySelect2() {
    var $ = window.jQuery;
    if ($ && $.fn && $.fn.select2) return $;
    return null;
  }

  function selectsProduits(form) {
    return Array.from(form.querySelectorAll("select[data-produit-ligne]"));
  }

  function idsDejaChoisis(selects, sauf) {
    return selects
      .filter(function (select) { return select !== sauf; })
      .map(function (select) { return String(select.value); })
      .filter(Boolean);
  }

  function filtrerOptions(form) {
    var selects = selectsProduits(form);
    selects.forEach(function (select) {
      var exclus = idsDejaChoisis(selects, select);
      Array.from(select.options).forEach(function (option) {
        if (!option.value) return;
        var pris = exclus.indexOf(String(option.value)) !== -1;
        option.hidden = pris;
        option.disabled = pris;
      });
    });
    return selects;
  }

  function activerSelect2Produits(form) {
    var $ = jquerySelect2();
    var selects = filtrerOptions(form);
    if (!$ || !selects.length) return;
    selects.forEach(function (select) {
      var $sel = $(select);
      try {
        if ($sel.data("select2")) {
          $sel.select2("destroy");
        }
        $sel.select2({
          width: "100%",
          dropdownParent: $(document.body),
          placeholder: select.options[0] && !select.options[0].value
            ? select.options[0].text
            : "Sélectionnez un produit",
          allowClear: true,
          language: {
            noResults: function () { return "Aucun produit"; },
            searching: function () { return "Recherche…"; },
          },
          matcher: function (params, data) {
            if (!data.id) return data;
            if (idsDejaChoisis(selectsProduits(form), select).indexOf(String(data.id)) !== -1) {
              return null;
            }
            var terme = String(params.term || "").trim().toLowerCase();
            if (!terme) return data;
            if (String(data.text || "").toLowerCase().indexOf(terme) !== -1) return data;
            return null;
          },
        });
      } catch (erreur) {
        if (!$sel.data("select2")) {
          $sel.select2({ width: "100%" });
        }
      }
    });
  }

  function syncPortionsLigne(row) {
    var produit = row.querySelector("select[data-produit-ligne]");
    var zone = row.querySelector(".portions-zone");
    var input = zone && zone.querySelector("input");
    if (!produit || !zone || !input) return;
    var option = produit.options[produit.selectedIndex];
    var defaut = Number((option && option.dataset.nombrePortions) || 0);
    var visible = defaut > 0;
    zone.hidden = !visible;
    input.disabled = !visible;
    if (visible) {
      input.min = "1";
      if (!input.value || Number(input.value) === 0) {
        input.value = defaut;
      }
    } else {
      input.min = "0";
      input.value = 0;
    }
  }

  function lierFormulaireProduits(form) {
    form.querySelectorAll("[data-ligne]").forEach(syncPortionsLigne);
    if (form.dataset.produitsExclusifsPret) {
      filtrerOptions(form);
      return;
    }
    form.dataset.produitsExclusifsPret = "1";
    activerSelect2Produits(form);
    function apresChoix(event) {
      var cible = event.target;
      if (!cible || !cible.matches || !cible.matches("select[data-produit-ligne]")) return;
      var row = cible.closest("[data-ligne]");
      if (row) syncPortionsLigne(row);
      filtrerOptions(form);
    }
    form.addEventListener("change", apresChoix);
    var $ = jquerySelect2();
    if ($) {
      $(form).on("select2:select select2:clear select2:unselect", "select[data-produit-ligne]", apresChoix);
    }
  }

  function initLignesProduits() {
    document.querySelectorAll("form[data-produits-exclusifs]").forEach(lierFormulaireProduits);
  }

  function lancerInitProduits() {
    if (jquerySelect2()) {
      initLignesProduits();
      return;
    }
    window.setTimeout(initLignesProduits, 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", lancerInitProduits);
  } else {
    lancerInitProduits();
  }
  document.addEventListener("ibbs:select2:init", lancerInitProduits);

  document.addEventListener("click", function (event) {
    const openBtn = event.target.closest("[data-open-dialog]");
    if (openBtn) {
      event.preventDefault();
      const dialog = document.getElementById(openBtn.getAttribute("data-open-dialog"));
      if (dialog && typeof dialog.showModal === "function") {
        dialog.showModal();
      }
      return;
    }
    const closeBtn = event.target.closest("[data-close-dialog]");
    if (closeBtn) {
      const dialog = closeBtn.closest("dialog");
      if (dialog) dialog.close();
    }
  });
})();
