"""Capacité **observabilité en LECTURE SEULE** typée (L10 — Variante MIN) — Software Control Plane, classe R.

CONNECTER, PAS RECONSTRUIRE : une capacité sémantique ``observability.health`` qui **consomme** la façade
existante ``scc_control_plane.ControlPlane`` (09_CONTROL_PLANE, sibling **INCHANGÉ**) et n'appelle QUE deux
primitives **strictement passives** : ``global_state()`` et ``component_health()``. Aucune autre méthode.

Surface **FERMÉE** et typée (N1) : jamais un proxy générique ``control_plane.call(method_name, ...)``. BrainAI ne
reçoit jamais un accès arbitraire à ControlPlane ; le nom de méthode n'est jamais choisi par un LLM.

Zéro effet de bord observable (Variante MIN) :
* aucun ``RuntimeProbe`` (aucune méthode runtime/health/snapshot/alerts/diagnostics appelée) ;
* aucun ``ensure_directories()`` / ``mkdir`` (aucune méthode self_check/state_report/snapshot appelée) ;
* aucune écriture fichier (``write_state_report`` JAMAIS appelée) ;
* aucun subprocess, aucun réseau, aucune mutation, aucune credential.

N6 : ``network_required=false`` ≠ ``network_isolation=proven``. 09 est stdlib pur (``dependencies=[]``) : aucune
opération réseau. Import du sibling via le chemin **canonique** ``BrainAIConfig.control_plane_src`` (aucune
technique d'import nouvelle ; même patron que ``cognition.py``). L'ajout du ``src/`` de 09 (et, à l'usage de
``global_state``/``component_health``, de 08_API) à ``sys.path`` est un effet **process** nécessaire à l'import,
**déclaré** (ce n'est pas une isolation OS).

Import-isolé : ``builder`` + ``core`` + stdlib + ``scc_control_plane`` (aucun pont 13/15/16 — N5 ; aucun
SAB/NEXUS/Base44). ``09_CONTROL_PLANE`` n'est JAMAIS modifié : connecté, jamais reconstruit — une seule source de
vérité d'observabilité (aucun monitoring parallèle).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List

from scc_brainai_bootstrap.builder.adapter_contract import AdapterContract
from scc_brainai_bootstrap.builder.claude_code_runtime import DIAG_MAX, redact

# Identifiant de l'exécutant (registre) — local, déterministe, sans réseau ni credential.
PROVIDER_NAME = "local_control_plane"

# Slug de capacité (``domaine.action``) — vocabulaire typé, classe R. EXACTEMENT un (Variante MIN).
OBS_HEALTH = "observability.health"
OBSERVABILITY_READ_CAPABILITIES = (OBS_HEALTH,)

# Allow-list STRICTE des méthodes ControlPlane appelables (Variante MIN). Toute autre est interdite.
_ALLOWED_METHODS = ("global_state", "component_health")


class ObservabilityReadError(ValueError):
    """Refus **fail-closed** d'une lecture d'observabilité (09 absent/illisible, config invalide, structure
    inattendue, capacité invalide, primitive attendue absente)."""


def _observability_contract(*, capabilities) -> AdapterContract:
    """Contrat T2 complet — observabilité locale confinée (lecture passive), réseau non requis (isolation non
    prouvée, N6). Aucun fournisseur externe, aucune credential, coût ``unavailable`` (I6)."""
    return AdapterContract(
        capabilities_served=tuple(capabilities),
        auth_channel={"kind": "none", "explicit": True, "leaks_identity": False,
                      "detail": "observabilité locale — façade ControlPlane, aucun fournisseur externe, aucune credential"},
        inbound_channels=(),
        cost_report={"mode": "unavailable", "fabricated": False},
        native_budget={"usd_cap": "none", "call_cap": "none"},
        confinement={"workspace": True,
                     "tools_allowed": ["control_plane:read-only:global_state",
                                       "control_plane:read-only:component_health"],
                     "tools_disallowed": ["control_plane:runtime-probe", "control_plane:write",
                                          "control_plane:snapshot", "control_plane:self_check",
                                          "shell", "network"],
                     "permission_mode": "local+read-only+passive", "env_mode": "none",
                     "network": {"required": False, "isolation": "not_proven"}},
    )


def _import_control_plane(control_plane_src: Any):
    """Import **canonique** du sibling 09 via ``BrainAIConfig.control_plane_src`` (aucune technique nouvelle).
    Fail-closed : chemin ``None``/non-absolu/inexistant ⇒ :class:`ObservabilityReadError` ; import impossible ⇒
    :class:`ObservabilityReadError`. Ajout ``sys.path`` idempotent (effet process déclaré)."""
    if control_plane_src is None:
        raise ObservabilityReadError("control_plane_src obligatoire (chemin du src de 09_CONTROL_PLANE)")
    src = Path(control_plane_src)
    if not src.is_absolute() or not src.is_dir():
        raise ObservabilityReadError(f"control_plane_src invalide (absolu + répertoire requis) : {src}")
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        return importlib.import_module("scc_control_plane")
    except Exception as exc:                                    # ImportError et dérivés — fail-closed
        raise ObservabilityReadError(f"import scc_control_plane impossible : {exc}") from exc


def _redact_tree(value: Any) -> Any:
    """SEC-3 : redaction **récursive** des chaînes (les ``detail``/noms peuvent porter des chemins), bornage
    ``DIAG_MAX``. Les scalaires non user-controlled (bool/int/float/None) sont préservés (contrat)."""
    if isinstance(value, str):
        return (redact(value) or "")[:DIAG_MAX]
    if isinstance(value, dict):
        return {k: _redact_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_tree(v) for v in value]
    return value


class LocalControlPlaneReadAdapter:
    """Exécutant **INERTE** (miroir F-6.1 de ``LocalGitReadAdapter``). AUCUNE méthode d'exécution (ni publique ni
    « privée » ``_``) : impossible d'appeler ControlPlane via l'adaptateur, **même** via ``h._adapter``. Expose
    uniquement du non-exécutable : identité (``name``/``capability``/``model``) et ``contract()`` (T2). L'exécution
    réelle vit exclusivement dans :func:`produce_observability_read`."""

    capability = "observability.read"           # famille (le contrat déclare le slug réellement servi)
    name = PROVIDER_NAME
    model = "control_plane"

    def __init__(self) -> None:
        self.max_budget_usd = 0.0               # observabilité locale : aucun coût facturable (jamais fabriqué, I6)

    def contract(self) -> AdapterContract:
        return _observability_contract(capabilities=OBSERVABILITY_READ_CAPABILITIES)


def _read_health(module: Any) -> Dict[str, Any]:
    """Appelle **EXACTEMENT** les deux primitives passives allow-listées (``global_state`` + ``component_health``),
    directement — jamais une méthode plus large filtrée. Fail-closed sur contrat 09 inattendu / structure inattendue."""
    ControlPlane = getattr(module, "ControlPlane", None)
    load_config = getattr(module, "load_config", None)
    if ControlPlane is None or load_config is None:
        raise ObservabilityReadError("scc_control_plane.ControlPlane/load_config introuvables (contrat 09 inattendu)")
    config = load_config()
    cp = ControlPlane(config)
    for m in _ALLOWED_METHODS:                                  # garde d'allow-list (les 2 seules méthodes)
        if not callable(getattr(cp, m, None)):
            raise ObservabilityReadError(f"primitive ControlPlane attendue absente : {m}")
    gs = cp.global_state()                                      # passive : lecture 08_API ; aucun RuntimeProbe/mkdir
    ch = cp.component_health()                                  # passive : idem
    if not isinstance(gs, dict) or not isinstance(ch, dict):
        raise ObservabilityReadError("structure d'observabilité inattendue (global_state/component_health non-dict)")
    return {"global_state": gs, "component_health": ch}


def produce_observability_read(*, capability: str, adapter: LocalControlPlaneReadAdapter,
                               control_plane_src: Any, scc_root: Any, tool_store: Any,
                               project_id: str, clock: Any) -> Dict[str, Any]:
    """**Chemin normal unique** d'une lecture d'observabilité typée (Variante MIN). Étapes : (1) import canonique de
    09 ; (2) appel **exclusif** de ``global_state()``+``component_health()`` (allow-list, aucune autre méthode, aucun
    effet de bord) ; (3) horodatage + **fait ToolInvocation** append-only (provenance N4, résultat redacté/borné,
    même sur refus) ; (4) résultat **typé** redacté (SEC-3) OU refus fail-closed. Réutilise ``ToolInvocationStore`` ;
    aucun nouveau journal, aucune seconde source de vérité."""
    if capability not in OBSERVABILITY_READ_CAPABILITIES:
        raise ObservabilityReadError(
            f"capacité observability inconnue : {capability!r} (admis ∈ {OBSERVABILITY_READ_CAPABILITIES})")
    argv: List[str] = [f"{adapter.name}:{capability}", "global_state", "component_health"]  # descripteur provenance NON exécutable
    cwd = str(scc_root) if scc_root is not None else ""
    try:
        module = _import_control_plane(control_plane_src)
        raw = _read_health(module)
        status = "succeeded"
        result: Any = _redact_tree(raw)
        err_text = ""
    except ObservabilityReadError as exc:
        status = "failed"
        result = None
        err_text = str(exc)
    as_of = clock()
    tool_fact = tool_store.record(
        project_id=project_id, tool=f"{adapter.name}:{capability}", argv=argv, cwd=cwd,
        status=status, exit_code=(0 if status == "succeeded" else 1),
        stdout=("" if status != "succeeded" else (redact(str(result)) or "")[:DIAG_MAX]),
        stderr=(redact(err_text) or "")[:DIAG_MAX],
        timed_out=False, as_of=as_of)
    if status != "succeeded":                                  # provenance enregistrée PUIS refus (aucun fallback silencieux)
        raise ObservabilityReadError(err_text or "lecture observabilité échouée")
    return {"capability": capability, "provider": adapter.name, "ok": True, "status": status,
            "result": result, "tool_ref": tool_fact["invocation_id"], "as_of": as_of}


class ObservabilityReadHandle:
    """**Voie d'exécution PUBLIQUE unique** d'une capacité observability-read (miroir F-6.1). Renvoyée par
    ``brainai_app.providers.resolve_observability_read``. N'expose **aucun** ``run()``/``_run`` nu : la seule
    exécution possible est :meth:`read`, qui passe **obligatoirement** par :func:`produce_observability_read`
    (import canonique + allow-list + provenance N4 + SEC-3). L'adaptateur interne reste **privé**."""

    def __init__(self, adapter: LocalControlPlaneReadAdapter, capability: str) -> None:
        self._adapter = adapter
        self.capability = capability
        self.provider = adapter.name
        self.name = adapter.name                # compat résolution (nom de provider) — aucune voie d'exécution exposée

    def contract(self) -> AdapterContract:
        return self._adapter.contract()

    def read(self, *, control_plane_src: Any, scc_root: Any, tool_store: Any,
             project_id: str, clock: Any) -> Dict[str, Any]:
        """Unique exécution publique. Délègue à :func:`produce_observability_read` — import canonique + allow-list +
        provenance **toujours** appliqués."""
        return produce_observability_read(
            capability=self.capability, adapter=self._adapter, control_plane_src=control_plane_src,
            scc_root=scc_root, tool_store=tool_store, project_id=project_id, clock=clock)


__all__ = ["PROVIDER_NAME", "OBS_HEALTH", "OBSERVABILITY_READ_CAPABILITIES", "ObservabilityReadError",
           "LocalControlPlaneReadAdapter", "ObservabilityReadHandle", "produce_observability_read"]
