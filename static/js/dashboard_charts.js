(function () {
  var couleurs = ["#8a0b27", "#111111", "#c4a35a", "#2d6a4f", "#6b081e", "#3d5a80"];

  function maxSerie(series) {
    var haut = 1;
    series.forEach(function (serie) {
      serie.values.forEach(function (valeur) {
        if (Number(valeur) > haut) haut = Number(valeur);
      });
    });
    return haut;
  }

  function dessiner(canvas, data) {
    var ctx = canvas.getContext("2d");
    var largeur = canvas.width;
    var hauteur = canvas.height;
    var labels = data.labels || [];
    var series = data.series || [];
    var margeG = 42;
    var margeD = 16;
    var margeH = 18;
    var margeB = 56;
    var zoneW = largeur - margeG - margeD;
    var zoneH = hauteur - margeH - margeB;
    var groupes = labels.length || 1;
    var nbSeries = series.length || 1;
    var largeurGroupe = zoneW / groupes;
    var barre = Math.max(10, (largeurGroupe - 28) / nbSeries);
    var max = maxSerie(series);

    ctx.clearRect(0, 0, largeur, hauteur);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, largeur, hauteur);

    ctx.strokeStyle = "#e6e6ea";
    ctx.beginPath();
    ctx.moveTo(margeG, margeH);
    ctx.lineTo(margeG, margeH + zoneH);
    ctx.lineTo(largeur - margeD, margeH + zoneH);
    ctx.stroke();

    ctx.fillStyle = "#5c5c5c";
    ctx.font = "12px Source Sans 3, Segoe UI, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(String(max), margeG - 6, margeH + 4);
    ctx.fillText("0", margeG - 6, margeH + zoneH);

    labels.forEach(function (label, index) {
      var x0 = margeG + index * largeurGroupe + 14;
      series.forEach(function (serie, s) {
        var valeur = Number(serie.values[index] || 0);
        var h = zoneH * (valeur / max);
        var x = x0 + s * barre;
        var y = margeH + zoneH - h;
        ctx.fillStyle = couleurs[s % couleurs.length];
        ctx.fillRect(x, y, barre - 4, Math.max(h, 0));
      });
      ctx.fillStyle = "#111111";
      ctx.textAlign = "center";
      ctx.fillText(label, x0 + ((nbSeries * barre) / 2), margeH + zoneH + 18);
    });

    var legendX = margeG;
    var legendY = hauteur - 18;
    series.forEach(function (serie, s) {
      ctx.fillStyle = couleurs[s % couleurs.length];
      ctx.fillRect(legendX, legendY - 8, 10, 10);
      ctx.fillStyle = "#111111";
      ctx.textAlign = "left";
      ctx.fillText(serie.label, legendX + 14, legendY);
      legendX += ctx.measureText(serie.label).width + 36;
    });
  }

  document.querySelectorAll("[data-dashboard-chart]").forEach(function (canvas) {
    var source = document.getElementById(canvas.getAttribute("data-dashboard-chart"));
    if (!source) return;
    try {
      dessiner(canvas, JSON.parse(source.textContent));
    } catch (erreur) {
      canvas.replaceWith(document.createTextNode("Graphique indisponible."));
    }
  });
})();
