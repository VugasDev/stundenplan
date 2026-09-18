/* Detailfenster fuer einen Unterrichtsblock.
 *
 * Alle Angaben stehen als data-Attribute am Block selbst. Das Fenster liest
 * sie beim Klick aus — ohne Abfrage beim Server, damit die Details auch dann
 * aufgehen, wenn das Geraet gerade offline ist.
 */
(function () {
  "use strict";

  var dialog = document.getElementById("stunden-dialog");
  if (!dialog) return;

  var STATUS_TEXT = {
    substitution: "Vertretung",
    cancelled: "Entfällt",
    exam: "Klausur"
  };

  function zeile(liste, bezeichnung, wert) {
    if (!wert) return;
    var dt = document.createElement("dt");
    dt.textContent = bezeichnung;
    var dd = document.createElement("dd");
    dd.textContent = wert;
    liste.appendChild(dt);
    liste.appendChild(dd);
  }

  function oeffnen(block) {
    var d = block.dataset;

    var marke = document.getElementById("sd-marke");
    var beschriftung = STATUS_TEXT[d.status];
    marke.textContent = beschriftung || "";
    marke.hidden = !beschriftung;
    marke.className = "sd-marke tt-" + d.status;

    document.getElementById("sd-fach").textContent = d.fach || "Unterricht";

    var liste = document.getElementById("sd-liste");
    liste.textContent = "";
    zeile(liste, "Wann", (d.tag || "") + (d.zeit ? ", " + d.zeit : ""));
    zeile(liste, "Dauer", d.stunden > 1 ? d.stunden + " Stunden" : "");
    zeile(liste, "Raum", d.raum);
    zeile(liste, "Lehrkraft", d.lehrer);
    zeile(liste, "Klasse", d.klasse);

    var notiz = document.getElementById("sd-notiz");
    notiz.textContent = d.notiz || "";
    notiz.hidden = !d.notiz;

    var konferenz = document.getElementById("sd-konferenz");
    if (d.konferenz) {
      konferenz.href = d.konferenz;
      konferenz.hidden = false;
    } else {
      konferenz.removeAttribute("href");
      konferenz.hidden = true;
    }

    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
  }

  document.addEventListener("click", function (ereignis) {
    var block = ereignis.target.closest("[data-fach]");
    if (block) {
      oeffnen(block);
      return;
    }
    // Klick auf den Hintergrund schliesst das Fenster.
    if (ereignis.target === dialog) dialog.close();
  });
})();
