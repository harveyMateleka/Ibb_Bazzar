(function () {
  function pret($) {
    var el = document.getElementById("imprimantes-par-service");
    var $service = $("#id_service");
    var $imprimante = $("#id_imprimante");
    if (!el || !$service.length || !$imprimante.length) return;

    var map = {};
    try {
      map = JSON.parse(el.textContent);
    } catch (erreur) {
      return;
    }

    function idsPour(service) {
      return (map[service] || []).map(String);
    }

    function filtrer() {
      var service = $service.val();
      var ids = idsPour(service);
      var current = $imprimante.val();
      $imprimante.find("option").each(function () {
        if (!this.value) {
          this.hidden = false;
          this.disabled = false;
          return;
        }
        var ok = !service || ids.indexOf(this.value) !== -1;
        this.hidden = !ok;
        this.disabled = !ok;
      });
      if (service && ids.length && ids.indexOf(String(current)) === -1) {
        $imprimante.val(ids[0]);
      }
    }

    $service.on("change", filtrer);
    filtrer();
  }

  if (window.django && django.jQuery) {
    django.jQuery(pret);
  }
})();
