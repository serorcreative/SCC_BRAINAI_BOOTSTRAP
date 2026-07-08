"""Routeur de demandes — un point d'entrée unique.

Classe une demande de façon déterministe :

* **decide** — demande décisionnelle (« faut-il… », « choisir… », « X ou Y »…) :
  route vers la boucle Reasoning → Decision (décision candidate gouvernée) ;
* **kernel** — demande cognitive/informative : route vers le Kernel (10).

Le routage est purement lexical (mots-clés) ; il peut être forcé par l'appelant.
"""

from __future__ import annotations

# Signaux forts d'une demande décisionnelle (verbes/tournures de choix).
_DECISIONAL = [
    "faut-il", "faut il", "doit-on", "doit on", "faut‑il",
    "choisir", "décider", "decider", "trancher", "arbitrer", "opter",
    "quelle option", "quelle stratégie", "quel choix",
    "ou différer", "ou differer", "ou bien", " ou non", "vaut-il mieux",
]


def route(query: str, forced: str = None) -> str:
    """Retourne « decide » ou « kernel »."""
    if forced in ("decide", "kernel"):
        return forced
    q = (query or "").lower()
    if any(k in q for k in _DECISIONAL):
        return "decide"
    return "kernel"


__all__ = ["route"]
