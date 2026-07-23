"""Dossier — l'unité **durable** de travail de BrainAI (WORK-CONTINUITY-ARCHITECTURE-001).

Un **Dossier** rassemble, par **appartenance et sans duplication**, le travail cohérent relatif à
un même **sujet** — de l'exploration à sa résolution éventuelle. Son **identité est stable**,
distincte de ses **attributs évolutifs** (``label``, ``status``, plus tard un objectif).

Identité (DOSSIER-CORE-001). L'acte fondateur est une **demande gouvernée d'ouverture** dont
l'identité technique dérive **UNIQUEMENT** de la paire ``{actor, correlation_key}`` — la
``correlation_key`` étant une **clé d'idempotence fournie par le client**, jamais par le serveur.
Le **contenu canonique** (``seed``, ``opened_as_of``) est **enregistré séparément** et **figé à la
première réception**. Le Dossier **dérive son id de la requête**. Ainsi :

* rejeu **même paire + même contenu** → **même Dossier** (idempotent) ;
* **même paire + contenu différent** → **conflit d'idempotence** (refus, aucune création) ;
* **deux intentions distinctes** → **deux `correlation_key`** → deux Dossiers.

Store **append-only** (``data/dossiers.jsonl``). Stdlib pur, déterministe (``as_of`` figé, aucune
composante positionnelle ni horloge).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import short_id
from scc_brainai_bootstrap.core.config import BrainAIConfig


def _canonical(text: str) -> str:
    """Forme **canonique** d'une chaîne d'identité/de contenu : **trim des bords**, sans
    interprétation ni perte de sens (même normalisation que Perception). La comparaison de rejeu
    s'appuie sur cette forme, afin de ne pas dépendre d'écarts de représentation non significatifs."""
    return text.strip()


class DossierOpenError(ValueError):
    """Ouverture invalide : acteur, clé de corrélation ou sujet manquant."""


class DossierConflict(Exception):
    """Réutilisation d'une même clé d'idempotence avec un **contenu canonique différent**."""

    def __init__(self, request_id: str, message: str):
        super().__init__(message)
        self.request_id = request_id


class DossierService:
    def __init__(self, config: BrainAIConfig):
        self._config = config

    @property
    def path(self) -> Path:
        return self._config.data_dir / "dossiers.jsonl"

    # -- identité (adressée genèse : paire d'intention uniquement) ----------- #
    @staticmethod
    def request_id(actor: str, correlation_key: str) -> str:
        """Identité de la **demande d'ouverture** — dérivée **uniquement** de
        ``{actor, correlation_key}`` (jamais du contenu métier, jamais de l'``as_of``)."""
        return short_id("dosreq", {"actor": _canonical(actor),
                                   "correlation_key": _canonical(correlation_key)})

    # -- lecture ------------------------------------------------------------ #
    def _load_all(self) -> List[Dict[str, Any]]:
        p = self.path
        if not p.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def _by_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        for d in self._load_all():
            if d.get("request_id") == request_id:
                return d
        return None

    def read(self, dossier_id: str) -> Optional[Dict[str, Any]]:
        for d in self._load_all():
            if d.get("dossier_id") == dossier_id:
                return d
        return None

    @staticmethod
    def _projection(d: Dict[str, Any]) -> Dict[str, Any]:
        return {"dossier_id": d.get("dossier_id"), "label": d.get("label"),
                "status": d.get("status"), "opened_by": d.get("opened_by"),
                "opened_as_of": d.get("opened_as_of")}

    def list(self) -> List[Dict[str, Any]]:
        """Tous les Dossiers, dans l'ordre d'ajout (déterministe), projetés."""
        return [self._projection(d) for d in self._load_all()]

    # -- ouverture (idempotente par clé ; conflit sur contenu divergent) ---- #
    def open(self, *, seed: str, correlation_key: str, actor: str) -> Dict[str, Any]:
        """Ouvre (ou retrouve) un Dossier. Renvoie ``{outcome, dossier}`` avec
        ``outcome`` ∈ {``opened``, ``replayed``}. Lève :class:`DossierConflict` si la clé est
        réutilisée avec un ``seed`` canonique différent ; :class:`DossierOpenError` si acteur,
        clé ou sujet est manquant. **Aucun acteur générique** — l'acteur doit être fourni."""
        actor_c = _canonical(actor) if isinstance(actor, str) else ""
        key_c = _canonical(correlation_key) if isinstance(correlation_key, str) else ""
        seed_c = _canonical(seed) if isinstance(seed, str) else ""
        if not actor_c:
            raise DossierOpenError("actor requis (aucun acteur générique par défaut)")
        if not key_c:
            raise DossierOpenError("correlation_key requise (fournie par le client, jamais le serveur)")
        if not seed_c:
            raise DossierOpenError("seed (sujet initial) requis")
        rid = self.request_id(actor_c, key_c)
        existing = self._by_request(rid)
        if existing is not None:
            if existing.get("seed") == seed_c:                       # rejeu idempotent
                return {"outcome": "replayed", "dossier": existing}
            raise DossierConflict(                                   # même clé, contenu différent
                rid, "conflit d'idempotence : la clé est déjà liée à un contenu différent")
        record = {
            "dossier_id": short_id("dos", {"request": rid}),         # id dérivé de la requête
            "request_id": rid,
            "correlation_key": key_c,
            "opened_by": actor_c,
            "seed": seed_c,                                          # contenu canonique **figé**
            "label": seed_c,                                         # attribut mutable (== seed à l'ouverture)
            "status": "open",
            "opened_as_of": self._config.as_of,                     # figé à la première réception
        }
        self._config.ensure_directories()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"outcome": "opened", "dossier": record}


__all__ = ["DossierService", "DossierConflict", "DossierOpenError"]
