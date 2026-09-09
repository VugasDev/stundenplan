// Zeichnet die Linie der aktuellen Uhrzeit in Wochen- und Tagesansicht.
// Rechnet ausschliesslich mit den Achsendaten, die der Server mitliefert —
// es geht dafuer keine Anfrage an den Server oder gar an WebUntis raus.
(function () {
  var daten = document.getElementById("tt-axis-daten");
  var linie = document.querySelector(".tt-now");
  if (!daten || !linie) return;

  var achse = JSON.parse(daten.textContent);
  var anzeige = linie.querySelector(".tt-now-zeit");

  // Dieselbe Abbildung wie Axis.y() auf dem Server: massstabsgetreue
  // Abschnitte linear, gestauchte Luecken anteilig.
  function y(minute) {
    for (var i = 0; i < achse.segments.length; i++) {
      var s = achse.segments[i];
      if (minute < s.start || minute > s.end) continue;
      if (s.kind === "gap") {
        var spanne = s.end - s.start;
        return s.top + (spanne ? (minute - s.start) / spanne * s.height : 0);
      }
      return s.top + (minute - s.start) * (s.height / (s.end - s.start));
    }
    return null; // ausserhalb des dargestellten Zeitraums
  }

  function zweistellig(n) { return (n < 10 ? "0" : "") + n; }

  function setzen() {
    var jetzt = new Date();
    var minute = jetzt.getHours() * 60 + jetzt.getMinutes();
    var pos = y(minute);
    if (pos === null) {
      linie.hidden = true;
      return;
    }
    linie.style.top = pos.toFixed(1) + "px";
    if (anzeige) anzeige.textContent = zweistellig(jetzt.getHours()) + ":" + zweistellig(jetzt.getMinutes());
    linie.hidden = false;
  }

  setzen();
  setInterval(setzen, 30000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) setzen();
  });
})();
