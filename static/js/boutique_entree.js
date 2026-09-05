(function (window, document) {
  'use strict';

  var $ = window.jQuery;
  var champsAuto = [
    'genre', 'taille', 'couleur', 'marque', 'modele', 'categorie', 'unite',
    'type_tissu', 'rayon', 'emplacement', 'devise', 'prix_achat',
    'prix_unitaire', 'prix_minimum', 'seuil_alerte',
  ];

  function payload() {
    try {
      return JSON.parse(document.getElementById('variantes-entree-data').textContent || '{}');
    } catch (e) {
      return {};
    }
  }

  function champ(name) {
    return document.getElementById('id_' + name);
  }

  function verrouiller(actif) {
    champsAuto.forEach(function (name) {
      var el = champ(name);
      if (!el) return;
      el.disabled = actif;
      el.classList.toggle('is-locked', actif);
    });
  }

  function vider() {
    champsAuto.forEach(function (name) {
      var el = champ(name);
      if (!el) return;
      el.value = '';
    });
    var aide = document.getElementById('stock-variante-actuel');
    if (aide) aide.textContent = '';
  }

  function remplir(info) {
    if (!info) {
      vider();
      verrouiller(false);
      return;
    }
    champsAuto.forEach(function (name) {
      var el = champ(name);
      if (!el) return;
      var valeur = info[name];
      el.value = valeur === undefined || valeur === null ? '' : valeur;
    });
    var succ = champ('succursale');
    var qte = (succ && info.stocks && info.stocks[succ.value]) || 0;
    var aide = document.getElementById('stock-variante-actuel');
    if (aide) {
      aide.textContent = 'Stock actuel de cette variante : ' + qte + '. Seule la quantité à ajouter est à saisir.';
    }
    verrouiller(true);
  }

  function filtrerOptions($variante, articleId) {
    $variante.find('option').each(function () {
      var opt = this;
      if (!opt.value) {
        opt.hidden = false;
        opt.disabled = false;
        return;
      }
      var info = payload()[opt.value];
      var ok = Boolean(articleId) && info && String(info.article) === String(articleId);
      opt.hidden = !ok;
      opt.disabled = !ok;
    });
  }

  function initSelect2Variante($variante) {
    if (!$ || !$.fn || !$.fn.select2) return;
    if ($variante.data('select2')) {
      $variante.select2('destroy');
    }
    $variante.select2({
      width: '100%',
      placeholder: $variante.find('option[value=""]').text(),
      allowClear: true,
      language: {
        noResults: function () {
          return 'Aucune variante. Laissez vide pour en créer une.';
        },
        searching: function () { return 'Recherche…'; },
      },
      matcher: function (params, data) {
        if (data.disabled || data.element && data.element.hidden) {
          return null;
        }
        if ($.trim(params.term) === '') return data;
        var terme = params.term.toLowerCase();
        var texte = (data.text || '').toLowerCase();
        if (texte.indexOf(terme) > -1) return data;
        return null;
      },
    });
  }

  function demarrer() {
    var article = champ('article');
    var variante = champ('variante');
    if (!article || !variante) return;
    var $variante = $ ? $(variante) : null;

    function onArticle() {
      filtrerOptions($variante || $(variante), article.value);
      variante.value = '';
      vider();
      verrouiller(false);
      if ($variante) {
        initSelect2Variante($variante);
        $variante.val(null).trigger('change.select2');
      }
    }

    function onVariante() {
      var info = variante.value ? payload()[variante.value] : null;
      if (info) {
        remplir(info);
      } else {
        vider();
        verrouiller(false);
      }
    }

    filtrerOptions($variante, article.value);
    if ($variante) initSelect2Variante($variante);
    if (variante.value) onVariante();

    if ($ && $variante) {
      $(article).on('change', onArticle);
      $variante.on('change', onVariante);
    } else {
      article.addEventListener('change', onArticle);
      variante.addEventListener('change', onVariante);
    }

    var succ = champ('succursale');
    if (succ) {
      succ.addEventListener('change', function () {
        if (variante.value) onVariante();
      });
    }

    var form = variante.form;
    if (form) {
      form.addEventListener('submit', function () {
        verrouiller(false);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})(window, document);
