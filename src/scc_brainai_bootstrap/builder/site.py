"""Capacité de **build réel** — le fournisseur ÉCRIT une petite application dans le Workspace confiné (JALON 2).

Différence majeure avec :mod:`scc_brainai_bootstrap.builder.build` (qui produit un *manifeste* JSON, outils
fichier **désactivés**) : ici le fournisseur dispose d'outils lui permettant d'**écrire sur le disque** (``Write``),
afin de fabriquer un artefact **réellement servable** (un site statique : ``index.html`` autonome). Cette
nouvelle surface **doit être confinée et prouvée** (A1) — la simple existence de PREUVE-A ne suffit pas :

* ``cwd`` **imposé** au Workspace de la Pursuit (``run_confined``) ;
* **argv-only** (jamais de shell) ; **environnement minimal** (aucun secret, aucun héritage global) ;
* écriture bornée au répertoire de travail (``--permission-mode acceptEdits`` ; réseau coupé) ;
* **toute référence d'artefact passe par** :meth:`Workspace.resolve_within` **avant persistance** ;
* une écriture hors Workspace (``..``/absolu/symlink sortant) est **bloquée OU détectée** et matérialisée par
  un fait de build ``failed`` — **jamais silencieuse** ; l'artefact n'est **jamais exécuté**.

BrainAI dépend d'une **capacité** (R8), jamais d'un outil concret : :class:`ClaudeCodeSiteAdapter` est un
adaptateur interchangeable. Un modèle **propose** (R5) : la sortie est un **fait ``build`` proposé**, jamais
officiel. Stdlib pur ; primitives runtime via l'API publique :mod:`claude_code_runtime`. Isolation d'imports du
``builder`` respectée (n'importe que ``builder`` + ``core``).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.build import _failure_reason, validate_spec_source
from scc_brainai_bootstrap.builder.claude_code_runtime import diagnostic, extract_cost, parse_envelope
from scc_brainai_bootstrap.builder.tool_runner import run_confined
from scc_brainai_bootstrap.builder.workspace import Workspace, WorkspaceError
from scc_brainai_bootstrap.core.clock import digest

# Point d'entrée **imposé par BrainAI** — jamais fourni par le modèle. Le site doit être servable ici.
SITE_ENTRYPOINT = "index.html"
# Taille maximale acceptée pour un artefact individuel (garde-fou anti-débordement, en octets).
MAX_ARTIFACT_BYTES = 2_000_000


class SiteBuildError(ValueError):
    """Échec structurel du build de site (avant toute frontière) — source invalide, etc."""


def site_prompt(spec: Dict[str, Any]) -> str:
    """Prompt déterministe : fabriquer un **site statique autonome** dérivé **exclusivement** de la Spécification.

    Contraintes imposées : écrire ``index.html`` (et éventuels fichiers ``.css``/``.js`` locaux) dans le
    **répertoire courant uniquement**, avec des **chemins relatifs** ; aucun accès réseau, aucune ressource
    externe (tout en ligne dans les fichiers) ; ne pas inventer de contenu hors Spécification ; ne rien exécuter."""
    spec_json = json.dumps(spec, sort_keys=True, ensure_ascii=False, indent=2)
    return (
        "Tu es un constructeur de site statique. À partir de la SPÉCIFICATION produit fournie, écris une petite "
        "application web STATIQUE et AUTONOME. Règles STRICTES :\n"
        f"- Écris un fichier d'entrée nommé EXACTEMENT « {SITE_ENTRYPOINT} » à la racine du répertoire courant.\n"
        "- N'écris QUE des fichiers en CHEMINS RELATIFS dans le répertoire courant (jamais de chemin absolu, "
        "jamais « .. », jamais en dehors du dossier courant).\n"
        "- Tout doit être autonome : AUCUN accès réseau, AUCune ressource externe (CSS/JS en ligne dans les "
        "fichiers ou en fichiers locaux). N'exécute rien, n'installe rien.\n"
        "- Appuie-toi EXCLUSIVEMENT sur la SPÉCIFICATION : n'invente aucune fonctionnalité, entité ou donnée "
        "absente. Le résultat est une page de présentation lisible, pas une application dynamique.\n\n"
        f"SPÉCIFICATION (source, ne pas contredire) :\n{spec_json}"
    )


@runtime_checkable
class SiteBuildCapability(Protocol):
    """**Capacité** « construire une application réelle à partir d'une Spéc » (R8)."""

    capability: str
    name: str
    model: str

    def build(self, spec: Dict[str, Any], *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        ...


class ClaudeCodeSiteAdapter:
    """Implémentation **Claude Code non-interactif** de :class:`SiteBuildCapability` (R8), outils fichier **activés**
    mais **confinés** au ``cwd`` (Workspace). Le fournisseur écrit de vrais fichiers ; BrainAI les collecte et les
    valide (:meth:`Workspace.resolve_within`) avant toute persistance."""

    capability = "build"
    name = "claude_code"

    def __init__(self, *, model: str = "haiku", max_budget_usd: float = 0.50,
                 timeout: float = 180.0, claude_bin: str = "claude"):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.claude_bin = claude_bin

    def build_argv(self, prompt: str) -> List[str]:
        """argv **only** : print non-interactif ; modèle explicite ; plafond coût **natif** du fournisseur ;
        écriture **auto-acceptée dans le répertoire courant uniquement** (``acceptEdits``) ; ``Write``/``Read``
        autorisés, ``Bash``/réseau **désactivés** (BrainAI, pas le modèle, versionne le workspace)."""
        return [
            self.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--model", self.model,
            "--max-budget-usd", str(self.max_budget_usd),
            "--permission-mode", "acceptEdits",
            "--allowedTools", "Write", "Read",
            "--disallowedTools", "Bash", "WebSearch", "WebFetch",
        ]

    def _env(self) -> Dict[str, str]:
        # Env minimal confiné, identique aux autres capacités : PATH/LANG + HOME/USER/LOGNAME si présents.
        # Aucun secret, aucun token ; l'environnement du parent n'est jamais hérité en bloc.
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"), "LANG": "C.UTF-8"}
        for k in ("HOME", "USER", "LOGNAME"):
            if os.environ.get(k):
                env[k] = os.environ[k]
        return env

    def build(self, spec: Dict[str, Any], *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable**. Garde budget AVANT (R2) : refuse sans appel si le reste ne couvre pas le
        plafond natif d'une invocation. Renvoie ``{called, envelope, exit_code, timed_out, prompt, argv, stdout,
        stderr}`` — ne construit ni ne matérialise le fait, ne collecte pas les artefacts (rôle de l'appelant)."""
        prompt = site_prompt(spec)
        argv = self.build_argv(prompt)
        if budget_remaining_usd < self.max_budget_usd:
            return {"called": False, "envelope": None, "exit_code": None, "timed_out": False,
                    "prompt": prompt, "argv": argv, "stdout": None, "stderr": None,
                    "refused": "budget insuffisant"}
        result = run_confined(argv, cwd=cwd, timeout=self.timeout, env=self._env())
        envelope = None if result["timed_out"] else parse_envelope(result["stdout"])
        return {"called": True, "envelope": envelope, "exit_code": result["exit_code"],
                "timed_out": result["timed_out"], "prompt": prompt, "argv": argv,
                "stdout": result["stdout"], "stderr": result["stderr"]}


# --------------------------------------------------------------------- #
# Collecte confinée des artefacts — A1 : tout passe par resolve_within, l'évasion est DÉTECTÉE (jamais silencieuse)
# --------------------------------------------------------------------- #
def collect_artifacts(workspace: Workspace) -> List[Dict[str, Any]]:
    """Recense les fichiers **réellement écrits** dans le Workspace, chacun **validé par**
    :meth:`Workspace.resolve_within` avant d'être retenu. Détecte toute **évasion** (symlink sortant du
    Workspace, chemin résolu hors racine) → lève :class:`WorkspaceError` (l'appelant en fait un fait ``failed``,
    jamais silencieux). Chaque artefact : ``{relative_path, sha256, byte_size}`` (hash des octets sur disque).

    ``.git`` (versionnage du Workspace par BrainAI) est ignoré : ce n'est pas un artefact produit par le modèle."""
    root = Path(workspace.path).resolve()
    artifacts: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # ne pas descendre dans .git (versionnage interne, pas un livrable)
        dirnames[:] = [d for d in dirnames if d != ".git"]
        # une entrée-répertoire symbolique sortante est une évasion → détecter, ne jamais suivre en silence
        for d in list(dirnames):
            p = Path(dirpath) / d
            if p.is_symlink() and root not in p.resolve().parents and p.resolve() != root:
                raise WorkspaceError(f"symlink-répertoire sortant du workspace détecté : {d}")
        for name in sorted(filenames):
            abs_path = Path(dirpath) / name
            resolved = abs_path.resolve()
            # symlink-fichier sortant → évasion détectée
            if abs_path.is_symlink() and root not in resolved.parents and resolved != root:
                raise WorkspaceError(f"symlink sortant du workspace détecté : {name}")
            rel = abs_path.relative_to(root).as_posix()
            # ceinture-et-bretelles : toute référence retenue repasse par resolve_within (lève si évasion)
            workspace.resolve_within(rel)
            data = resolved.read_bytes()
            if len(data) > MAX_ARTIFACT_BYTES:
                raise WorkspaceError(f"artefact {rel!r} trop volumineux ({len(data)} o)")
            artifacts.append({"relative_path": rel,
                              "sha256": hashlib.sha256(data).hexdigest(),
                              "byte_size": len(data)})
    return sorted(artifacts, key=lambda a: a["relative_path"])


def _entrypoint_of(artifacts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for a in artifacts:
        if a["relative_path"] == SITE_ENTRYPOINT:
            return a
    return None


def build_site_fact(*, spec_source: Dict[str, Any], prompt: str, capability: str, adapter: str, model: str,
                    envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool, as_of: str,
                    artifacts: Optional[List[Dict[str, Any]]] = None, tool_ref: Optional[str] = None,
                    escape: Optional[str] = None, argv: Any = None, stdout: Any = None,
                    stderr: Any = None) -> Dict[str, Any]:
    """Construit un **fait ``build``** honnête (pur, testable). ``proposed`` uniquement si : appel abouti,
    **pas d'évasion**, artefacts collectés ET ``index.html`` présent (non vide). Sinon ``failed`` (``error``
    jamais ``"success"``, ``diagnostic`` RV-1, ``artefacts=[]``). Le :class:`BuildStore` adresse l'``id``."""
    sid, spec = validate_spec_source(spec_source)
    spec_sha256 = digest(spec)
    cost = extract_cost(envelope)
    usage = envelope.get("usage") if envelope else None
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    entry = _entrypoint_of(artifacts or [])
    base: Dict[str, Any] = {
        "fact_type": "build",
        "kind": "site",
        "capability": capability,
        "adapter": adapter,
        "model": model,
        "spec_ref": sid,
        "spec_sha256": spec_sha256,
        "prompt_sha256": prompt_sha256,
        "params": {"output_format": "json", "tools": ["Write", "Read"], "permission_mode": "acceptEdits"},
        "usage": usage if usage is not None else "unavailable",
        "cost": cost,
        "tool_ref": tool_ref,
        "as_of": as_of,
        # ``artefact`` (singulier) = point d'entrée servable → participe à l'adressage du build_id (BuildStore).
        "artefact": entry,
    }
    diag = diagnostic(argv=argv, stdout=stdout, stderr=stderr, exit_code=exit_code,
                      timed_out=timed_out, envelope=envelope)
    if escape is not None:                                   # A1 : évasion détectée → échec explicite, jamais tu
        return {**base, "status": "failed", "artefacts": [], "artefact": None,
                "error": f"évasion hors workspace détectée : {escape}", "diagnostic": diag}
    reason = _failure_reason(envelope, exit_code, timed_out)
    if reason is not None:
        return {**base, "status": "failed", "artefacts": [], "artefact": None,
                "error": reason, "diagnostic": diag}
    if entry is None or entry.get("byte_size", 0) <= 0:
        return {**base, "status": "failed", "artefacts": list(artifacts or []), "artefact": None,
                "error": f"point d'entrée « {SITE_ENTRYPOINT} » absent ou vide", "diagnostic": diag}
    return {**base, "status": "proposed", "artefacts": list(artifacts), "error": None, "diagnostic": None}


def _system_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def produce_site_build(*, spec_source: Dict[str, Any], adapter: SiteBuildCapability, store: Any,
                       tool_store: Any, workspace: Workspace, project_id: str,
                       budget_remaining_usd: float, cwd: Path,
                       clock: Callable[[], str] = _system_clock) -> Dict[str, Any]:
    """**Chemin normal unique** Spécification → **site réel confiné**. Séquence : (1) valide la Spéc (refus AVANT
    toute frontière) ; (2) ``adapter.build`` (garde budget incluse) ; (3) refus budget ⇒ **aucun fait** ; (4)
    horodatage réel ; **enregistre le fait ToolInvocation** de l'appel ; (5) si l'appel a abouti, **collecte
    confinée** des artefacts (toute évasion ⇒ fait ``failed``, jamais silencieux) ; (6) **un seul** fait
    ``build``, **aucun retry** (R6)."""
    _, spec = validate_spec_source(spec_source)                       # (1)
    raw = adapter.build(spec, cwd=cwd, budget_remaining_usd=budget_remaining_usd)  # (2)
    if not raw.get("called"):                                         # (3)
        return {"attempted": False, "recorded": False, "refused": raw.get("refused"), "fact": None}
    as_of = clock()                                                   # (4)
    envelope = raw["envelope"]
    exit_code = raw["exit_code"]
    timed_out = raw["timed_out"]

    # (4bis) Fait ToolInvocation de l'appel réel — succès/échec/timeout, jamais fabriqué.
    tool_status = "timeout" if timed_out else ("succeeded" if exit_code == 0 else "failed")
    tool_fact = tool_store.record(project_id=project_id, tool=adapter.name,
                                  argv=raw.get("argv") or [adapter.name], cwd=str(cwd),
                                  status=tool_status, exit_code=exit_code,
                                  stdout=raw.get("stdout") or "", stderr=raw.get("stderr") or "",
                                  timed_out=timed_out, as_of=as_of)

    # (5) Collecte confinée seulement si l'appel a abouti ; toute évasion devient un fait failed (jamais tu).
    escape: Optional[str] = None
    artifacts: List[Dict[str, Any]] = []
    if _failure_reason(envelope, exit_code, timed_out) is None:
        try:
            artifacts = collect_artifacts(workspace)
        except WorkspaceError as exc:
            escape = str(exc)

    fact = build_site_fact(
        spec_source=spec_source, prompt=raw["prompt"], capability=adapter.capability, adapter=adapter.name,
        model=adapter.model, envelope=envelope, exit_code=exit_code, timed_out=timed_out, as_of=as_of,
        artifacts=artifacts, tool_ref=tool_fact["invocation_id"], escape=escape,
        argv=raw.get("argv"), stdout=raw.get("stdout"), stderr=raw.get("stderr"))
    recorded = store.record(fact)                                    # (6) un seul fait, jamais de retry
    return {"attempted": True, "recorded": True, "refused": None, "fact": recorded}


__all__ = ["SITE_ENTRYPOINT", "MAX_ARTIFACT_BYTES", "SiteBuildError", "site_prompt",
           "SiteBuildCapability", "ClaudeCodeSiteAdapter", "collect_artifacts",
           "build_site_fact", "produce_site_build"]
