"""Schutz der Blockpositionierung im Stundenraster.

Die Bloecke liegen absolut positioniert und werden ueber `left` und `right`
aufgespannt — so teilen sich zwei sich ueberschneidende Stunden die Spalte.
Eine zusaetzliche `width`-Angabe bricht das: bei absoluter Positionierung mit
`left` *und* `width` verwirft der Browser das `right`. Die Stunde in der
rechten Spur (left:50%) wird dann volle Spaltenbreite und ragt in den
Nachbartag hinein.
"""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "app" / "static" / "style.css"


def _regeln_fuer(auswahl: str) -> list[str]:
    """Alle Regelkoerper, deren Selektor die angegebene Klasse nennt."""
    text = CSS.read_text(encoding="utf-8")
    treffer = []
    for selektor, koerper in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        klassen = re.findall(r"\.[a-zA-Z0-9_-]+", selektor)
        if auswahl in klassen:
            treffer.append(koerper)
    return treffer


def test_der_block_im_raster_bekommt_keine_breite_zugewiesen():
    """Sonst ragt die Ersatzstunde einen halben Block in den nächsten Tag."""
    for koerper in _regeln_fuer(".tt-block"):
        assert not re.search(r"(^|[;\s])width\s*:", koerper), \
            f"width in Regel fuer .tt-block: {koerper.strip()[:120]}"


def test_der_block_bleibt_absolut_positioniert_mit_links_und_rechts():
    text = CSS.read_text(encoding="utf-8")
    grundregel = next(k for s, k in re.findall(r"([^{}]+)\{([^{}]*)\}", text)
                      if s.strip() == ".tt-block")
    assert "position:absolute" in grundregel.replace(" ", "")
    assert "left:" in grundregel and "right:" in grundregel
