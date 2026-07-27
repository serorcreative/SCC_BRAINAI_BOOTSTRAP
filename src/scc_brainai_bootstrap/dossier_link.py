"""Rattachement Entrée ↔ Dossier — le **fait de liaison** (DOSSIER-LINK-CORE-001, Tranche 1).

Un **rattachement** est un **fait gouverné, daté et attribué** qui déclare qu'une **Entrée**
donnée appartient à un **Dossier** donné. Il **n'est ni** un contenu, ni un attribut de
l'Entrée, ni un attribut du Dossier : il ne modifie **aucun** des deux. Il est **immuable**
parce qu'il constate un **acte accompli** ; toute évolution future devra être représentée par
**un autre fait** (jamais une mutation). Il est **distinct** de l'Entrée (fait perçu, immuable,
*sans état*) et du Dossier (objet gouverné, sujet durable) : il est la **relation entre eux**,
portée par aucun des deux. L'**appartenance courante** d'un Dossier n'est donc **jamais un état
stocké ni muté** : c'est une **projection** obtenue à partir des faits de rattachement.

Ce module pose **uniquement** le service métier pur et son store **durable**, sur le patron réel
de :mod:`perception` et :mod:`dossier` : store **append-only** (``data/dossier_links.jsonl``),
relu du disque à chaque appel, **identité adressée par la paire** ``(dossier_id, input_id)`` —
d'où l'**idempotence** native et l'**unicité par paire**, **sans exclusivité globale** d'une
Entrée (une même Entrée peut appartenir à plusieurs Dossiers). Stdlib pur, déterministe
(``as_of`` figé, aucune horloge, aucune composante positionnelle).

Hors périmètre de cette tranche : orchestration Bootstrap, contrat, présentation, audit
événementiel, validation d'existence Dossier/Entrée, détachement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import short_id
from scc_brainai_bootstrap.core.config import BrainAIConfig


class DossierLinkError(ValueError):
    """Rattachement invalide : ``dossier_id``, ``input_id`` ou ``actor`` manquant."""


class DossierLinkService:
    def __init__(self, config: BrainAIConfig):
        self._config = config

    @property
    def path(self) -> Path:
        return self._config.data_dir / "dossier_links.jsonl"

    # -- identité (adressée par la paire ; aucune exclusivité globale) ------- #
    @staticmethod
    def link_id(dossier_id: str, input_id: str) -> str:
        """Identité **déterministe** du fait de rattachement — dérivée **uniquement** de la
        paire ``(dossier_id, input_id)`` (jamais de l'acteur ni de l'``as_of``). Même paire →
        même identifiant (idempotence) ; l'unicité est celle de la **paire**, jamais une
        exclusivité globale de l'Entrée."""
        return short_id("doslink", {"dossier_id": dossier_id, "input_id": input_id})

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

    def _find(self, link_id: str) -> Optional[Dict[str, Any]]:
        for rec in self._load_all():
            if rec.get("link_id") == link_id:
                return rec
        return None

    def list_for_dossier(self, dossier_id: str) -> List[Dict[str, Any]]:
        """Faits de rattachement d'un Dossier — **projection** de son appartenance courante.

        Filtre par ``dossier_id``, **déduplique par ``link_id``** (une paire n'apparaît qu'une
        fois, même si le store contenait des lignes redondantes) et **ordonne de façon
        déterministe** par ``link_id`` (adressé-contenu, indépendant de l'ordre disque).
        Lecture pure : relit le disque, n'écrit rien, ne mute rien."""
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for rec in self._load_all():
            if rec.get("dossier_id") != dossier_id:
                continue
            lid = rec.get("link_id")
            if lid in seen:
                continue
            seen.add(lid)
            out.append(rec)
        out.sort(key=lambda r: r.get("link_id") or "")
        return out

    # -- écriture (append-only ; idempotente par paire) --------------------- #
    def attach(self, *, dossier_id: str, input_id: str, actor: str) -> Dict[str, Any]:
        """Pose (ou retrouve) le **fait de rattachement** d'une Entrée à un Dossier.

        Renvoie ``{outcome, link}`` avec ``outcome`` ∈ {``attached``, ``replayed``}.
        **Idempotent par paire** : ré-attacher la même ``(dossier_id, input_id)`` **ne crée
        aucune seconde ligne** et **ne mute pas** le fait initial (``attached_by`` /
        ``attached_as_of`` **figés à la première pose** — un fait ne se corrige pas). **Acteur
        explicite requis** (aucun acteur générique). Ne vérifie **pas** l'existence du Dossier
        ni de l'Entrée : cette validation est une responsabilité d'orchestration (Tranche 2)."""
        did = dossier_id.strip() if isinstance(dossier_id, str) else ""
        iid = input_id.strip() if isinstance(input_id, str) else ""
        actor_c = actor.strip() if isinstance(actor, str) else ""
        if not did:
            raise DossierLinkError("dossier_id requis")
        if not iid:
            raise DossierLinkError("input_id requis")
        if not actor_c:
            raise DossierLinkError("actor requis (aucun acteur générique par défaut)")
        lid = self.link_id(did, iid)
        existing = self._find(lid)
        if existing is not None:
            return {"outcome": "replayed", "link": existing}     # fait figé, aucune 2e ligne
        record = {
            "link_id": lid,
            "dossier_id": did,
            "input_id": iid,
            "attached_by": actor_c,                               # attribution figée
            "attached_as_of": self._config.as_of,                 # datation figée (déterministe)
        }
        self._config.ensure_directories()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"outcome": "attached", "link": record}


__all__ = ["DossierLinkService", "DossierLinkError"]
