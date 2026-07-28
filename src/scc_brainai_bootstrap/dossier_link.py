"""Rattachement Entrée ↔ Dossier — les **faits de liaison** (DOSSIER-LINK-CORE-001/003).

Un **rattachement** est un **fait gouverné, daté et attribué** qui déclare qu'une **Entrée**
donnée appartient à un **Dossier** donné. Il **n'est ni** un contenu, ni un attribut de
l'Entrée, ni un attribut du Dossier : il ne modifie **aucun** des deux. Il est **immuable** ;
il ne se corrige pas — il ne se complète, ou **s'annule, que par un autre fait**. Il est
**distinct** de l'Entrée (fait perçu, immuable, *sans état*) et du Dossier (objet gouverné) :
il est la **relation entre eux**, portée par aucun des deux.

Deux **types de faits** (``kind``) partagent le même store append-only (``dossier_links.jsonl``)
et la même identité de paire ``link_id`` :

* ``attached`` — pose le rattachement (``attached_by`` / ``attached_as_of``) ;
* ``detached`` — **annule** le rattachement courant, sans jamais supprimer le fait d'attache
  (``detached_by`` / ``detached_as_of``).

**Append-only strict** : aucun fait n'est supprimé ni modifié ; seuls de nouveaux faits sont
ajoutés. L'**appartenance courante** d'un Dossier n'est **jamais un état stocké** : c'est une
**projection « dernier fait gagnant »** — pour une paire, le **dernier** fait (ordre d'ajout)
détermine l'appartenance (membre ssi ``attached``). Un enregistrement **sans ``kind``** est
interprété comme ``attached`` (compatibilité ascendante). Stdlib pur, déterministe (``as_of``
figé, aucune horloge, aucune composante positionnelle).

Hors périmètre de ce module : orchestration Bootstrap, contrat, présentation, audit
événementiel, validation d'existence Dossier/Entrée.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.core.clock import short_id
from scc_brainai_bootstrap.core.config import BrainAIConfig

_ATTACHED = "attached"
_DETACHED = "detached"


def _kind(rec: Dict[str, Any]) -> str:
    """Type d'un fait — un enregistrement **sans ``kind``** vaut ``attached`` (compat ascendante)."""
    return rec.get("kind", _ATTACHED)


class DossierLinkError(ValueError):
    """Fait de liaison invalide : ``dossier_id``, ``input_id`` ou ``actor`` manquant."""


class DossierLinkService:
    def __init__(self, config: BrainAIConfig):
        self._config = config

    @property
    def path(self) -> Path:
        return self._config.data_dir / "dossier_links.jsonl"

    # -- identité (adressée par la paire ; aucune exclusivité globale) ------- #
    @staticmethod
    def link_id(dossier_id: str, input_id: str) -> str:
        """Identité **déterministe** de la paire ``(dossier_id, input_id)`` — dérivée **uniquement**
        de la paire (jamais de l'acteur, de l'``as_of`` ni du type de fait). Les faits ``attached``
        et ``detached`` d'une même paire **partagent** ce ``link_id`` ; ils se distinguent par
        ``kind`` et par leur **ordre d'ajout**."""
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

    def _current_fact(self, link_id: str) -> Optional[Dict[str, Any]]:
        """**Dernier** fait d'une paire (ordre d'ajout = ordre du disque), ou ``None`` si aucun.
        C'est lui qui **gouverne l'appartenance courante** (« dernier fait gagnant »)."""
        current: Optional[Dict[str, Any]] = None
        for rec in self._load_all():
            if rec.get("link_id") == link_id:
                current = rec
        return current

    def list_for_dossier(self, dossier_id: str) -> List[Dict[str, Any]]:
        """Faits **courants** de rattachement d'un Dossier — **projection « dernier gagnant »**.

        Pour chaque paire du Dossier, seul le **dernier** fait compte : la paire est **membre**
        ssi ce dernier fait est ``attached`` (le fait ``attached`` gouvernant est alors renvoyé).
        Ordre **déterministe** par ``link_id`` (adressé-contenu, indépendant de l'ordre disque).
        Lecture pure : relit le disque, n'écrit rien, ne mute rien."""
        latest: Dict[str, Dict[str, Any]] = {}
        for rec in self._load_all():
            if rec.get("dossier_id") != dossier_id:
                continue
            latest[rec.get("link_id")] = rec               # dernier vu (ordre d'ajout) l'emporte
        members = [f for f in latest.values() if _kind(f) == _ATTACHED]
        members.sort(key=lambda r: r.get("link_id") or "")
        return members

    # -- écriture (append-only ; idempotence fondée sur l'appartenance) ------ #
    def _validate(self, dossier_id: str, input_id: str, actor: str) -> tuple:
        did = dossier_id.strip() if isinstance(dossier_id, str) else ""
        iid = input_id.strip() if isinstance(input_id, str) else ""
        actor_c = actor.strip() if isinstance(actor, str) else ""
        if not did:
            raise DossierLinkError("dossier_id requis")
        if not iid:
            raise DossierLinkError("input_id requis")
        if not actor_c:
            raise DossierLinkError("actor requis (aucun acteur générique par défaut)")
        return did, iid, actor_c

    def _append(self, record: Dict[str, Any]) -> None:
        self._config.ensure_directories()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def attach(self, *, dossier_id: str, input_id: str, actor: str) -> Dict[str, Any]:
        """Pose (ou retrouve) le rattachement courant d'une Entrée à un Dossier.

        Renvoie ``{outcome, link}`` avec ``outcome`` ∈ {``attached``, ``replayed``}.
        **Idempotence fondée sur l'appartenance courante** : si la paire est **déjà rattachée**
        (dernier fait ``attached``), rejeu → aucune seconde ligne, fait courant **figé** renvoyé.
        Si elle **n'est pas rattachée** (jamais liée, ou **dernier fait ``detached``**), un
        **nouveau fait ``attached``** est ajouté (ré-attachement après détachement). **Acteur
        explicite requis**. Ne vérifie pas l'existence Dossier/Entrée (orchestration)."""
        did, iid, actor_c = self._validate(dossier_id, input_id, actor)
        lid = self.link_id(did, iid)
        current = self._current_fact(lid)
        if current is not None and _kind(current) == _ATTACHED:
            return {"outcome": "replayed", "link": current}   # déjà rattaché : fait figé, aucune 2e ligne
        record = {
            "link_id": lid,
            "dossier_id": did,
            "input_id": iid,
            "kind": _ATTACHED,
            "attached_by": actor_c,                            # attribution figée
            "attached_as_of": self._config.as_of,              # datation figée (déterministe)
        }
        self._append(record)
        return {"outcome": "attached", "link": record}

    def detach(self, *, dossier_id: str, input_id: str, actor: str) -> Dict[str, Any]:
        """**Annule** le rattachement courant par un **nouveau fait ``detached``** — jamais une
        suppression (le fait d'attache demeure).

        Renvoie ``{outcome, link}`` avec ``outcome`` ∈ {``detached``, ``noop``}.
        **Idempotent** : si la paire **n'est pas rattachée** (jamais liée, ou **déjà détachée**),
        aucune ligne n'est ajoutée → ``noop`` (rien à annuler), avec le dernier fait connu (ou
        ``None``). Sinon un fait ``detached`` est ajouté. **Acteur explicite requis**. Ne vérifie
        pas l'existence Dossier/Entrée (orchestration)."""
        did, iid, actor_c = self._validate(dossier_id, input_id, actor)
        lid = self.link_id(did, iid)
        current = self._current_fact(lid)
        if current is None or _kind(current) == _DETACHED:
            return {"outcome": "noop", "link": current}       # rien à détacher (jamais lié / déjà détaché)
        record = {
            "link_id": lid,
            "dossier_id": did,
            "input_id": iid,
            "kind": _DETACHED,
            "detached_by": actor_c,                            # attribution figée
            "detached_as_of": self._config.as_of,              # datation figée (déterministe)
        }
        self._append(record)
        return {"outcome": "detached", "link": record}


__all__ = ["DossierLinkService", "DossierLinkError"]
