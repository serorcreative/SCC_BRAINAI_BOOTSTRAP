"""Contrat d'adaptateur **complet** — tout adaptateur DÉCLARE sa surface (JALON 3, T2).

Formalisation du **contrat universel IA** fondateur (Phase 0 J3) et de ses garde-fous : **Doctrine 9 Isolation
Provider** (BrainAI ne parle qu'à travers l'adaptateur) et **Doctrine 10 Adaptateur = traducteur, jamais décideur**.
Tout adaptateur doit déclarer **au minimum** :

* ``capabilities_served`` — capacités servies (slugs/rôles) ;
* ``auth_channel`` — canal d'authentification (RV-2 : trousseau/HOME vs jeton explicite ; ``leaks_identity``) ;
* ``inbound_channels`` — **tout** ce que le runtime injecte dans le contexte du modèle (RV-2 étendue : env, cwd,
  argv, fichiers de session/config, historique) — **jamais** la Pursuit entière (I9) ;
* ``cost_report`` — mode de coût : ``real_from_envelope`` / ``unavailable`` ; ``fabricated`` **toujours False** (I6) ;
* ``native_budget`` — nature du plafond **réellement offert par le fournisseur** : ``usd_cap`` ∈ {``hard``,
  ``aggregate_stop``, ``none``} (RS-039 : « dur » **seulement** si nativement garanti) ; ``call_cap`` ∈
  {``enforced_by_brainai``, ``none``} ;
* ``confinement`` — workspace, outils autorisés/interdits, mode de permission, mode d'environnement.

Un adaptateur dont la déclaration est **incomplète** est **structurellement rejeté** (:func:`require_contract`). Le
contrat teste un **principe**, pas une technologie (AM6). Import-isolé : ``builder`` + ``core`` uniquement. Stdlib pur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

# Valeurs gouvernées (enum) — le contrat déclare une propriété RÉELLE, jamais désirée.
COST_MODES = ("real_from_envelope", "unavailable")
USD_CAP_KINDS = ("hard", "aggregate_stop", "none")       # « hard » seulement si nativement garanti (RS-039)
CALL_CAP_KINDS = ("enforced_by_brainai", "none")


class IncompleteContractError(ValueError):
    """Un adaptateur sans contrat complet est **structurellement rejeté** (jamais utilisé en l'état)."""


@dataclass(frozen=True)
class AdapterContract:
    """Déclaration **complète** d'un adaptateur. Aucune valeur par défaut « pratique » : tout doit être déclaré."""

    capabilities_served: Tuple[str, ...]
    auth_channel: Dict[str, Any]
    inbound_channels: Tuple[Dict[str, Any], ...]
    cost_report: Dict[str, Any]
    native_budget: Dict[str, Any]
    confinement: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capabilities_served": list(self.capabilities_served),
            "auth_channel": dict(self.auth_channel),
            "inbound_channels": [dict(c) for c in self.inbound_channels],
            "cost_report": dict(self.cost_report),
            "native_budget": dict(self.native_budget),
            "confinement": dict(self.confinement),
        }


def validate_contract(contract: Any) -> List[str]:
    """Renvoie la liste des **manquements** d'un contrat (vide = complet et conforme). Accepte un
    :class:`AdapterContract` ou un dict équivalent — une déclaration incomplète produit des erreurs (rejet)."""
    errs: List[str] = []
    c = contract.to_dict() if isinstance(contract, AdapterContract) else (contract if isinstance(contract, dict) else None)
    if c is None:
        return ["contrat absent ou de type invalide"]

    caps = c.get("capabilities_served")
    if not isinstance(caps, list) or not caps or not all(isinstance(x, str) and x.strip() for x in caps):
        errs.append("capabilities_served : liste non vide de slugs requis")

    auth = c.get("auth_channel")
    if not isinstance(auth, dict) or "kind" not in auth or not isinstance(auth.get("explicit"), bool) \
            or not isinstance(auth.get("leaks_identity"), bool):
        errs.append("auth_channel : {kind, explicit:bool, leaks_identity:bool} requis (RV-2)")

    inbound = c.get("inbound_channels")
    if not isinstance(inbound, list):
        errs.append("inbound_channels : liste requise (RV-2 étendue)")
    else:
        for ch in inbound:
            if not isinstance(ch, dict) or "channel" not in ch or not isinstance(ch.get("pursuit_scoped"), bool):
                errs.append("inbound_channels[*] : {channel, pursuit_scoped:bool, …} requis")
                break
            # I9 : un canal peut porter du contenu de Pursuit, mais **jamais** « la Pursuit entière ».
            if ch.get("carries_whole_pursuit") is True:
                errs.append("I9 violé : un canal entrant ne doit jamais porter la Pursuit entière")

    cost = c.get("cost_report")
    if not isinstance(cost, dict) or cost.get("mode") not in COST_MODES:
        errs.append(f"cost_report.mode ∈ {COST_MODES} requis")
    elif cost.get("fabricated") is not False:      # I6 : coût jamais fabriqué
        errs.append("cost_report.fabricated doit être False (I6 : coût jamais fabriqué)")

    nb = c.get("native_budget")
    if not isinstance(nb, dict) or nb.get("usd_cap") not in USD_CAP_KINDS or nb.get("call_cap") not in CALL_CAP_KINDS:
        errs.append(f"native_budget : usd_cap ∈ {USD_CAP_KINDS}, call_cap ∈ {CALL_CAP_KINDS} (RS-039)")

    conf = c.get("confinement")
    if not isinstance(conf, dict) or not isinstance(conf.get("workspace"), bool) \
            or not isinstance(conf.get("tools_allowed"), list) or not isinstance(conf.get("tools_disallowed"), list) \
            or "permission_mode" not in conf:
        errs.append("confinement : {workspace:bool, tools_allowed:list, tools_disallowed:list, permission_mode, …} requis")
    return errs


def is_conformant(adapter: Any) -> bool:
    """Vrai si l'adaptateur **expose** un contrat (méthode ``contract()``) **complet**."""
    fn = getattr(adapter, "contract", None)
    if not callable(fn):
        return False
    try:
        return not validate_contract(fn())
    except Exception:  # noqa: BLE001
        return False


def require_contract(adapter: Any) -> AdapterContract:
    """Renvoie le contrat de l'adaptateur ou **rejette structurellement** (:class:`IncompleteContractError`) s'il
    est absent/incomplet. À appeler à la résolution : aucun adaptateur non conforme n'est utilisé."""
    fn = getattr(adapter, "contract", None)
    if not callable(fn):
        raise IncompleteContractError(
            f"adaptateur {getattr(adapter, 'name', adapter)!r} : aucune méthode contract() — rejeté")
    contract = fn()
    errs = validate_contract(contract)
    if errs:
        raise IncompleteContractError(
            f"adaptateur {getattr(adapter, 'name', adapter)!r} : contrat incomplet — {errs}")
    return contract if isinstance(contract, AdapterContract) else contract


# --------------------------------------------------------------------- #
# Fabriques de contrat — déclarent la surface RÉELLE d'un type d'adaptateur (les adaptateurs les appellent)
# --------------------------------------------------------------------- #
def claude_text_contract(*, capability: str, auth_channel: Dict[str, Any], inbound_channels: List[Dict[str, Any]],
                         tools_disallowed: List[str], extra_inbound: List[Dict[str, Any]] = None) -> AdapterContract:
    """Contrat d'un adaptateur **texte** Claude Code (understanding/specification/conversation/build-manifeste) :
    coût réel via enveloppe (I6) ; plafond USD = **arrêt agrégé** (RS-039) ; **aucun outil fichier** ; confinement cwd.
    ``extra_inbound`` : canaux spécifiques (ex. historique de dialogue, **scopé Pursuit**, I9)."""
    channels = list(inbound_channels) + list(extra_inbound or [])
    return AdapterContract(
        capabilities_served=(capability,),
        auth_channel=dict(auth_channel),
        inbound_channels=tuple(channels),
        cost_report={"mode": "real_from_envelope", "fabricated": False},
        native_budget={"usd_cap": "aggregate_stop", "call_cap": "enforced_by_brainai"},
        confinement={"workspace": True, "tools_allowed": [], "tools_disallowed": list(tools_disallowed),
                     "permission_mode": "default", "env_mode": auth_channel.get("kind")},
    )


def claude_site_contract(*, capability: str, auth_channel: Dict[str, Any], inbound_channels: List[Dict[str, Any]],
                         tools_allowed: List[str], tools_disallowed: List[str],
                         permission_mode: str) -> AdapterContract:
    """Contrat de l'adaptateur **build de site** Claude Code : écriture fichiers **auto-acceptée dans le cwd**
    (``acceptEdits``) ; coût réel (I6) ; plafond USD = arrêt agrégé (RS-039)."""
    return AdapterContract(
        capabilities_served=(capability,),
        auth_channel=dict(auth_channel),
        inbound_channels=tuple(inbound_channels),
        cost_report={"mode": "real_from_envelope", "fabricated": False},
        native_budget={"usd_cap": "aggregate_stop", "call_cap": "enforced_by_brainai"},
        confinement={"workspace": True, "tools_allowed": list(tools_allowed),
                     "tools_disallowed": list(tools_disallowed), "permission_mode": permission_mode,
                     "env_mode": auth_channel.get("kind")},
    )


def local_surface_contract(*, capability: str) -> AdapterContract:
    """Contrat d'une capacité **locale** (preview loopback) : **aucun** appel fournisseur, **aucun** canal d'auth
    fournisseur, coût ``unavailable`` (rien de facturable), confinement par ``resolve_within``."""
    return AdapterContract(
        capabilities_served=(capability,),
        auth_channel={"kind": "none", "explicit": True, "leaks_identity": False,
                      "detail": "surface locale (loopback) — aucun fournisseur externe"},
        inbound_channels=(),
        cost_report={"mode": "unavailable", "fabricated": False},
        native_budget={"usd_cap": "none", "call_cap": "none"},
        confinement={"workspace": True, "tools_allowed": [], "tools_disallowed": [],
                     "permission_mode": "loopback+token+default-deny", "env_mode": "none"},
    )


__all__ = ["AdapterContract", "IncompleteContractError", "validate_contract", "is_conformant", "require_contract",
           "claude_text_contract", "claude_site_contract", "local_surface_contract",
           "COST_MODES", "USD_CAP_KINDS", "CALL_CAP_KINDS"]
