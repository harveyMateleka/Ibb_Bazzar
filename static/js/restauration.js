(function () {
  function nombre(valeur) {
    const n = parseInt(valeur, 10);
    return Number.isFinite(n) ? n : 0;
  }

  function afficherStockModal(nom, disponible, platId) {
    const dialog = document.getElementById("dialog-stock");
    const message = document.getElementById("dialog-stock-msg");
    if (!dialog) return;
    const reste = nombre(disponible);
    if (message) {
      if (reste <= 0) {
        message.textContent =
          nom + " : plus aucune portion disponible. Impossible d’ajouter ce plat.";
      } else {
        message.textContent =
          nom +
          " : il ne reste que " +
          reste +
          " portion(s) disponible(s). Saisissez une quantité inférieure.";
      }
    }
    if (platId) {
      const champ = document.querySelector(
        '.js-ajout-plat[data-plat-id="' + platId + '"] .js-qte-plat'
      );
      if (champ) champ.value = "0";
    }
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    }
  }

  function controlerStock(form) {
    const champ = form.querySelector(".js-qte-plat");
    const demande = nombre(champ && champ.value);
    const reste = nombre(form.getAttribute("data-reste"));
    const deja = nombre(form.getAttribute("data-deja"));
    const nom = form.getAttribute("data-nom") || "Ce plat";
    const platId = form.getAttribute("data-plat-id");
    if (reste <= 0) {
      if (champ) champ.value = "0";
      afficherStockModal(nom, 0, platId);
      return false;
    }
    if (demande <= 0) {
      if (champ) champ.value = "0";
      return false;
    }
    const reserve = form.getAttribute("data-stock-reserve") === "1";
    const utilise = reserve ? 0 : deja;
    if (utilise + demande > reste) {
      if (champ) champ.value = "0";
      afficherStockModal(nom, reste, platId);
      return false;
    }
    return true;
  }

  document.addEventListener("submit", function (event) {
    const ajout = event.target.closest(".js-ajout-plat");
    if (ajout) {
      if (!controlerStock(ajout)) event.preventDefault();
      return;
    }
    const plus = event.target.closest(".js-ligne-plus");
    if (!plus) return;
    const reste = nombre(plus.getAttribute("data-reste"));
    const deja = nombre(plus.getAttribute("data-deja"));
    const nom = plus.getAttribute("data-nom") || "Ce plat";
    const platId = plus.getAttribute("data-plat-id");
    const reserve = plus.getAttribute("data-stock-reserve") === "1";
    if (reste <= 0 || (!reserve && deja + 1 > reste)) {
      event.preventDefault();
      afficherStockModal(nom, reste, platId);
    }
  });

  document.addEventListener("change", function (event) {
    const champ = event.target.closest(".js-qte-plat");
    if (!champ) return;
    const form = champ.closest(".js-ajout-plat");
    if (!form) return;
    const demande = nombre(champ.value);
    if (demande <= 0) {
      champ.value = "0";
      return;
    }
    controlerStock(form);
  });

  const dialog = document.getElementById("dialog-stock");
  if (dialog && dialog.getAttribute("data-open") === "1") {
    afficherStockModal(
      dialog.getAttribute("data-nom") || "Ce plat",
      dialog.getAttribute("data-disponible"),
      dialog.getAttribute("data-plat-id")
    );
  }

  const PLATS_PAR_PAGE = 8;
  const plats = document.querySelectorAll(".menu-plat");
  const blocs = document.querySelectorAll(".menu-bloc");
  const onglets = document.querySelectorAll(".js-menu-tab");
  const menuListe = document.querySelector(".js-menu-liste");
  const pagination = document.querySelector(".js-menu-pagination");
  const pagesEl = document.querySelector(".js-menu-pages");
  const infoEl = document.querySelector(".js-menu-page-info");
  const btnPrev = document.querySelector(".js-menu-page-prev");
  const btnNext = document.querySelector(".js-menu-page-next");
  const champRecherche = document.querySelector(".js-menu-recherche");
  const videEl = document.querySelector(".js-menu-vide");
  let serviceFiltre = "";
  let recherche = "";
  let pageCourante = 1;

  function normaliser(texte) {
    return String(texte || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim();
  }

  function cleEtat() {
    const id = menuListe && menuListe.getAttribute("data-commande-id");
    return id ? "restauration-menu-" + id : "";
  }

  function sauverEtat() {
    const cle = cleEtat();
    if (!cle || !window.sessionStorage) return;
    sessionStorage.setItem(
      cle,
      JSON.stringify({
        service: serviceFiltre,
        page: pageCourante,
        recherche: recherche,
      })
    );
  }

  function restaurerEtat() {
    const cle = cleEtat();
    if (!cle || !window.sessionStorage) return;
    try {
      const etat = JSON.parse(sessionStorage.getItem(cle) || "{}");
      if (typeof etat.service === "string") serviceFiltre = etat.service;
      if (typeof etat.recherche === "string") recherche = etat.recherche;
      if (etat.page) pageCourante = nombre(etat.page) || 1;
    } catch (erreur) {
      pageCourante = 1;
    }
    if (champRecherche) champRecherche.value = recherche;
  }

  function platsFiltres() {
    const terme = normaliser(recherche);
    const resultat = [];
    plats.forEach(function (plat) {
      const service = plat.getAttribute("data-service") || "";
      if (serviceFiltre && service !== serviceFiltre) return;
      if (terme) {
        const nom = normaliser(plat.getAttribute("data-nom"));
        const bloc = plat.closest(".menu-bloc");
        const categorie = normaliser(
          bloc && bloc.getAttribute("data-categorie-nom")
        );
        if (nom.indexOf(terme) === -1 && categorie.indexOf(terme) === -1) return;
      }
      resultat.push(plat);
    });
    return resultat;
  }

  function rendrePagination(total, totalPages) {
    if (!pagination) return;
    pagination.hidden = total <= 0;
    if (total <= 0) {
      if (infoEl) infoEl.textContent = "";
      if (pagesEl) pagesEl.replaceChildren();
      return;
    }

    const debut = (pageCourante - 1) * PLATS_PAR_PAGE + 1;
    const fin = Math.min(pageCourante * PLATS_PAR_PAGE, total);
    if (infoEl) {
      infoEl.textContent = "Plats " + debut + "–" + fin + " sur " + total;
    }
    if (btnPrev) btnPrev.disabled = pageCourante <= 1;
    if (btnNext) btnNext.disabled = pageCourante >= totalPages;
    if (!pagesEl) return;

    pagesEl.replaceChildren();
    for (let page = 1; page <= totalPages; page += 1) {
      const bouton = document.createElement("button");
      bouton.type = "button";
      bouton.className = "menu-page-btn" + (page === pageCourante ? " is-active" : "");
      bouton.textContent = String(page);
      bouton.setAttribute("aria-label", "Page " + page);
      if (page === pageCourante) bouton.setAttribute("aria-current", "page");
      bouton.addEventListener("click", function () {
        pageCourante = page;
        afficherMenu();
      });
      pagesEl.appendChild(bouton);
    }
  }

  function afficherMenu() {
    const liste = platsFiltres();
    const totalPages = Math.max(1, Math.ceil(liste.length / PLATS_PAR_PAGE));
    if (pageCourante > totalPages) pageCourante = totalPages;
    if (pageCourante < 1) pageCourante = 1;

    const debut = (pageCourante - 1) * PLATS_PAR_PAGE;
    const fin = debut + PLATS_PAR_PAGE;
    const pagePlats = new Set(liste.slice(debut, fin));

    plats.forEach(function (plat) {
      plat.hidden = !pagePlats.has(plat);
      plat.classList.remove("is-highlight");
    });

    blocs.forEach(function (bloc) {
      const aUneCarte = Array.prototype.some.call(
        bloc.querySelectorAll(".menu-plat"),
        function (plat) {
          return !plat.hidden;
        }
      );
      bloc.hidden = !aUneCarte;
    });

    if (videEl) {
      videEl.hidden = !plats.length || liste.length > 0;
    }

    rendrePagination(liste.length, totalPages);
    sauverEtat();
  }

  function activerOnglet() {
    onglets.forEach(function (onglet) {
      const service = onglet.getAttribute("data-service") || "";
      onglet.classList.toggle("is-active", service === serviceFiltre);
    });
  }

  restaurerEtat();
  activerOnglet();
  afficherMenu();

  onglets.forEach(function (onglet) {
    onglet.addEventListener("click", function (event) {
      event.preventDefault();
      serviceFiltre = onglet.getAttribute("data-service") || "";
      pageCourante = 1;
      activerOnglet();
      afficherMenu();
    });
  });

  if (champRecherche) {
    champRecherche.addEventListener("input", function () {
      recherche = champRecherche.value;
      pageCourante = 1;
      afficherMenu();
    });
    champRecherche.addEventListener("search", function () {
      recherche = champRecherche.value;
      pageCourante = 1;
      afficherMenu();
    });
  }

  if (btnPrev) {
    btnPrev.addEventListener("click", function () {
      pageCourante -= 1;
      afficherMenu();
    });
  }
  if (btnNext) {
    btnNext.addEventListener("click", function () {
      pageCourante += 1;
      afficherMenu();
    });
  }
})();
