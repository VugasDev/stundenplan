// Service Worker: macht die App installierbar und ohne Netz benutzbar.
//
// Zwei Strategien, absichtlich getrennt:
//   Oberflaeche (CSS, Skripte, Icons) -> aus dem Cache, im Hintergrund erneuert.
//   Seiten (Plan, Klassen)            -> erst Netz, bei Fehlschlag der letzte
//                                        gespeicherte Stand.
// So ist der Plan im Funkloch da, zeigt online aber immer den frischen Stand.
//
// Beim Abmelden schickt der Server "Clear-Site-Data" — der Browser leert Cache
// und Speicher dann selbst, damit auf einem geteilten Geraet nichts zurueckbleibt.

const VERSION = "v1";
const HUELLE = `huelle-${VERSION}`;   // Oberflaeche
const SEITEN = `seiten-${VERSION}`;   // besuchte Seiten

const GRUNDGERUEST = [
  "/offline",
  "/static/style.css",
  "/static/icons/icon-192.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(HUELLE)
      .then((c) => c.addAll(GRUNDGERUEST))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((namen) => Promise.all(
        namen.filter((n) => !n.endsWith(VERSION)).map((n) => caches.delete(n))
      ))
      .then(() => self.clients.claim())
  );
});

function istOberflaeche(url) {
  return url.pathname.startsWith("/static/");
}

self.addEventListener("fetch", (e) => {
  const anfrage = e.request;
  // Nur einfache Abrufe behandeln. Formulare (POST) muessen immer ans Netz,
  // sonst gingen Anmeldung, Beitritt und Aktualisieren ins Leere.
  if (anfrage.method !== "GET") return;

  const url = new URL(anfrage.url);
  if (url.origin !== self.location.origin) return;

  if (istOberflaeche(url)) {
    // Aus dem Cache antworten, parallel erneuern.
    e.respondWith(
      caches.match(anfrage).then((treffer) => {
        const holen = fetch(anfrage).then((antwort) => {
          if (antwort.ok) {
            const kopie = antwort.clone();
            caches.open(HUELLE).then((c) => c.put(anfrage, kopie));
          }
          return antwort;
        });
        return treffer || holen;
      })
    );
    return;
  }

  // Seiten: erst das Netz, damit der Plan online immer aktuell ist.
  e.respondWith(
    fetch(anfrage)
      .then((antwort) => {
        // Weiterleitungen (etwa zur Anmeldung) nicht speichern — sonst haengt
        // man offline auf einer Seite fest, die nicht mehr gilt.
        if (antwort.ok && antwort.type === "basic") {
          const kopie = antwort.clone();
          caches.open(SEITEN).then((c) => c.put(anfrage, kopie));
        }
        return antwort;
      })
      .catch(() =>
        caches.match(anfrage).then((treffer) => treffer || caches.match("/offline"))
      )
  );
});
