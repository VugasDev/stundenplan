"""Dunkle Darstellung: folgt dem Geraet, laesst sich aber festlegen."""


def test_farben_sind_als_variablen_definiert(client):
    css = client.get("/static/style.css").data.decode()
    assert ":root" in css
    for variable in ["--bg", "--card", "--ink", "--line", "--accent"]:
        assert variable in css, variable


def test_dunkle_farben_folgen_der_geraeteeinstellung(client):
    css = client.get("/static/style.css").data.decode()
    assert "prefers-color-scheme: dark" in css


def test_festgelegte_wahl_hat_vorrang_vor_der_geraeteeinstellung(client):
    """Beide Richtungen muessen erzwingbar sein — auch hell auf einem dunklen
    Geraet, sonst ist der Umschalter nur eine halbe Sache."""
    css = client.get("/static/style.css").data.decode()
    assert '[data-theme="dark"]' in css
    assert '[data-theme="light"]' in css


def test_umschalter_ist_auf_jeder_seite_erreichbar(client):
    for pfad in ["/login", "/register", "/forgot-password"]:
        html = client.get(pfad).data.decode()
        assert 'id="theme-toggle"' in html, pfad


def test_wahl_wird_vor_dem_ersten_bild_angewendet(client):
    """Gegen das Aufblitzen der hellen Seite: die gespeicherte Wahl muss im
    Kopf der Seite gesetzt werden, nicht erst am Ende."""
    html = client.get("/login").data.decode()
    kopf = html.split("</head>")[0]
    assert "localStorage" in kopf
    assert "data-theme" in kopf


def test_farbe_der_geraeteleiste_passt_sich_an(client):
    html = client.get("/login").data.decode()
    assert html.count('name="theme-color"') >= 2      # je eine je Darstellung
    assert "prefers-color-scheme" in html
