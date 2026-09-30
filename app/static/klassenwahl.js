/* Klassenwahl: Namen mitschicken und die Spendenfrage nur dort zeigen, wo
 * noch kein Zugang vorliegt. */
(function () {
  "use strict";
  var wahl = document.getElementById("klassenwahl");
  if (!wahl) return;

  var name = document.getElementById("klassenname");
  var spende = document.getElementById("spende-block");
  var versorgt = document.getElementById("schon-versorgt");

  function uebernehmen() {
    var gewaehlt = wahl.selectedOptions[0];
    if (!gewaehlt) return;
    // Der Name geht mit, damit die Anzeige ohne zweiten Abruf stimmt.
    if (name) name.value = gewaehlt.dataset.name || "";
    var hatQuelle = gewaehlt.dataset.hatQuelle === "ja";
    if (spende) {
      spende.hidden = hatQuelle;
      if (hatQuelle) {
        // Sonst blieb ein zuvor gesetztes Haekchen unsichtbar gesetzt.
        var kasten = spende.querySelector('input[name="spenden"]');
        if (kasten) kasten.checked = false;
      }
    }
    if (versorgt) versorgt.hidden = !hatQuelle;
  }

  wahl.addEventListener("change", uebernehmen);
  uebernehmen();
})();
