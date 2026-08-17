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
