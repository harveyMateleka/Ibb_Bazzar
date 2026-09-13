(function (window, document) {
  'use strict';

  var $ = window.jQuery;

  function rafraichirSelect2(cible) {
    if (!$ || !$.fn || !$.fn.select2) return;
    var $cible = $(cible);
    if ($cible.data('select2')) {
      $cible.select2('destroy');
    }
    $cible.select2({
      width: '100%',
      matcher: function (params, data) {
        if (data.disabled || (data.element && data.element.hidden)) {
          return null;
        }
        if ($.trim(params.term) === '') return data;
        var terme = params.term.toLowerCase();
        if ((data.text || '').toLowerCase().indexOf(terme) > -1) return data;
        return null;
      }
    });
  }

  function filtrerEmplacements(serviceSelect) {
    var cibleId = serviceSelect.getAttribute('data-filtre-emplacements');
    var cible = cibleId ? document.getElementById(cibleId) : null;
    if (!cible) return;
    var serviceId = serviceSelect.value;
    Array.prototype.forEach.call(cible.options, function (opt) {
      if (!opt.value) {
        opt.hidden = false;
        opt.disabled = false;
        return;
      }
      var ok = Boolean(serviceId) && opt.getAttribute('data-service') === String(serviceId);
      opt.hidden = !ok;
      opt.disabled = !ok;
    });
    var selected = cible.options[cible.selectedIndex];
    if (selected && selected.disabled) {
      cible.value = '';
    }
    rafraichirSelect2(cible);
  }

  function initFiltres(root) {
    (root || document).querySelectorAll('[data-filtre-emplacements]').forEach(function (select) {
      if (select.dataset.filtreEmplacementsPret === '1') return;
      select.dataset.filtreEmplacementsPret = '1';
      filtrerEmplacements(select);
      if ($ && $.fn) {
        $(select).on('change', function () {
          filtrerEmplacements(select);
        });
      } else {
        select.addEventListener('change', function () {
          filtrerEmplacements(select);
        });
      }
    });
  }

  function initChoisirCasse(root) {
    var zone = root || document;
    var form = zone.querySelector('[data-choix-affectation]');
    if (!form) return;
    var idInput = form.querySelector('[name="affectation_id"]');
    var svc = form.querySelector('[name="service_affiche"]');
    var emp = form.querySelector('[name="emplacement_affiche"]');
    var qte = form.querySelector('[name="quantite"]');
    var boutons = zone.querySelectorAll('[data-choisir-affectation]');

    function marquerLigne(btn) {
      boutons.forEach(function (b) {
        var ligne = b.closest('tr');
        if (ligne) ligne.classList.toggle('is-chosen', b === btn);
      });
    }

    boutons.forEach(function (btn) {
      if (btn.dataset.choisirPret === '1') return;
      btn.dataset.choisirPret = '1';
      btn.addEventListener('click', function () {
        if (idInput) idInput.value = btn.getAttribute('data-id') || '';
        if (svc) svc.value = btn.getAttribute('data-service') || '';
        if (emp) emp.value = btn.getAttribute('data-emplacement') || '';
        var max = btn.getAttribute('data-quantite');
        if (qte && max) {
          qte.setAttribute('max', max);
          if (!qte.value || Number(qte.value) > Number(max)) {
            qte.value = max;
          }
        }
        marquerLigne(btn);
      });
    });

    if (idInput && idInput.value) {
      boutons.forEach(function (btn) {
        if (btn.getAttribute('data-id') === String(idInput.value)) {
          marquerLigne(btn);
        }
      });
    }
  }

  function lancer() {
    initFiltres(document);
    initChoisirCasse(document);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', lancer);
  } else {
    lancer();
  }
  document.addEventListener('ibbs:select2:init', lancer);
})(window, document);
