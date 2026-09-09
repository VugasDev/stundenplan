// Haelt die Jetzt-Ansicht aktuell: laedt die Seite minuetlich neu, damit
// "laeuft gerade" stimmt. Das liest nur unsere eigene Datenbank — ein Abruf
// bei WebUntis passiert dabei ausdruecklich nicht.
// Im Hintergrundtab wird nicht geladen, sondern erst beim Zurueckkehren.
(function () {
  var INTERVALL = 60000;
  var faellig = Date.now() + INTERVALL;

  setInterval(function () {
    if (Date.now() < faellig) return;
    if (document.hidden) return;   // erst beim Zurueckkehren
    location.reload();
  }, 10000);

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && Date.now() >= faellig) location.reload();
  });
})();
