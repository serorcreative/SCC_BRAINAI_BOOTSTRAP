"""Perception — le pilier d'entrée de BrainAI (socle de lecture, INPUT-READ-001).

Une **Entrée** (Input) est un **fait acquis et normalisé** — jamais sa signification.
Elle est **immuable**, conserve une **provenance explicite**, et ne décide, ne valide,
n'exécute **jamais** (INPUT-001). Toute interprétation future sera un *enrichissement*
séparé (chantier ultérieur) : l'Entrée d'origine n'est jamais modifiée.

Ce module pose **uniquement** le socle de lecture : le modèle canonique minimal, un store
**append-only** (JSONL), la lecture par identifiant et la liste projetée. **Aucun mécanisme
d'acquisition réel** (audio, PDF, image, e-mail, OCR, ASR, adaptateur) n'est fourni ici, et
**aucune écriture publique** n'est exposée par le Contrat à ce stade.

Déterminisme : identité dérivée du contenu (jamais de l'horloge machine), `as_of` figé.
Stdlib pur, zéro dépendance — cohérent avec le reste du Bootstrap.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import digest, short_id
from scc_brainai_bootstrap.core.config import BrainAIConfig

# Longueur de l'aperçu de contenu dans la projection légère (adaptée à l'affichage).
_PREVIEW_LEN = 120


def build_input(*, modality: str, content: Any, provenance: Dict[str, Any], as_of: str,
                ingested_at: Optional[str] = None, observed_at: Optional[str] = None,
                session_id: Optional[str] = None, actor: Optional[str] = None,
                context: Optional[Dict[str, Any]] = None,
                fidelity: Optional[float] = None) -> Dict[str, Any]:
    """Construit une **Entrée canonique immuable**.

    L'identifiant est **adressé-contenu** : dérivé du contenu normalisé **et** du contexte
    d'acquisition (provenance, horodatages, session, acteur). Deux observations réellement
    distinctes obtiennent des identifiants distincts ; une observation strictement identique
    est **idempotente**. Validations structurelles minimales — le modèle reste extensible
    par ajouts futurs sans devenir générique.
    """
    if not modality or not isinstance(modality, str):
        raise ValueError("modality requise (str non vide)")
    if content is None:
        raise ValueError("content requis (contenu normalisé, indépendant du média)")
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError("provenance requise (source explicite, dict non vide)")

    ingested = ingested_at or as_of
    ctx = dict(context) if context else {}
    content_digest = digest(content)
    # Identité = contenu + contexte d'acquisition (jamais l'`as_of` de traitement seul).
    identity = {
        "modality": modality, "content_digest": content_digest, "provenance": provenance,
        "observed_at": observed_at, "ingested_at": ingested,
        "session_id": session_id, "actor": actor, "context": ctx,
    }
    return {
        "id": short_id("in", identity),
        "modality": modality,
        "content": content,
        "provenance": provenance,
        "observed_at": observed_at,
        "ingested_at": ingested,
        "as_of": as_of,
        "session_id": session_id,
        "actor": actor,
        "context": ctx,
        "integrity": {"content_digest": content_digest},
        "fidelity": fidelity,
    }


class PerceptionService:
    """Collaborateur dédié : store **append-only** + lecture + projection des Entrées.

    Le Bootstrap **orchestre et délègue** — il ne porte pas cette logique. Le store est un
    journal JSONL (`data/inputs.jsonl`) : on **ajoute** des Entrées immuables, on n'en modifie
    ni n'en supprime aucune. La lecture re-parcourt le disque à chaque appel (aucun cache
    mutable ; les Entrées rendues sont fraîches, donc immuables du point de vue de l'appelant).
    """

    def __init__(self, config: BrainAIConfig):
        self._config = config

    @property
    def path(self) -> Path:
        return self._config.data_dir / "inputs.jsonl"

    # -- écriture (append-only ; NON exposée par le Contrat à ce stade) ----- #
    def record(self, **fields: Any) -> Dict[str, Any]:
        """Ajoute une Entrée immuable au store (append-only). **Idempotent par identifiant**
        (adressage-contenu) : ré-enregistrer une Entrée identique ne crée pas de doublon.

        Méthode interne au pilier (utilisée par les tests et, plus tard, par l'acquisition) —
        **jamais** exposée comme opération d'écriture publique dans INPUT-READ-001.
        """
        entry = build_input(as_of=self._config.as_of, **fields)
        if self.read(entry["id"]) is not None:
            return entry                                   # idempotence : aucun doublon d'id
        self._config.ensure_directories()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def record_text(self, *, text: str, provenance: Dict[str, Any]) -> Dict[str, Any]:
        """Acquisition d'une **Entrée texte** (INPUT-WRITE-001). **Normalise** le texte —
        trim des espaces de bord, **aucune interprétation, aucune perte de sens** — puis
        enregistre une Entrée canonique de modalité ``text`` via :meth:`record` (append-only,
        id adressé-contenu, ``as_of`` figé, provenance conservée). Refuse un texte vide ou une
        provenance invalide (validations portées par :func:`build_input`)."""
        if not isinstance(text, str):
            raise ValueError("text requis (str)")
        normalized = text.strip()
        if not normalized:
            raise ValueError("text vide après normalisation")
        return self.record(modality="text", content=normalized, provenance=provenance)

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

    def list(self) -> List[Dict[str, Any]]:
        """Toutes les Entrées, dans l'ordre d'ajout (déterministe)."""
        return self._load_all()

    def read(self, input_id: str) -> Optional[Dict[str, Any]]:
        """Détail d'une Entrée par identifiant, ou ``None`` si absente."""
        for entry in self._load_all():
            if entry.get("id") == input_id:
                return entry
        return None

    def project(self) -> List[Dict[str, Any]]:
        """Liste **projetée** légère et déterministe, adaptée à l'affichage."""
        return [self._projection(e) for e in self._load_all()]

    @staticmethod
    def _projection(entry: Dict[str, Any]) -> Dict[str, Any]:
        content = entry.get("content")
        preview = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        if len(preview) > _PREVIEW_LEN:
            preview = preview[:_PREVIEW_LEN] + "…"
        prov = entry.get("provenance", {}) or {}
        return {
            "id": entry.get("id"),
            "modality": entry.get("modality"),
            "preview": preview,
            "provenance": prov.get("origin", prov.get("medium")),
            "observed_at": entry.get("observed_at"),
            "ingested_at": entry.get("ingested_at"),
            "session_id": entry.get("session_id"),
        }


__all__ = ["PerceptionService", "build_input"]
