"""T1b — frontière **logique** builder ↔ noyau/cognition (Arbitrage 2, JALON-ZERO).

Preuve statique (AST, aucune exécution) que la frontière tient dans les deux sens :

* le paquet ``builder`` n'importe **aucun** moteur cognitif (11–16 : reasoning, planning, decision,
  execution, memory, perception) ni **aucun** service métier du noyau (dossier, learning, router,
  session, event_bus, bootstrap, patrimony…) ;
* **aucun** module du noyau n'importe ``builder``.

``builder`` ne connaît que ses propres modules et l'infrastructure ``core`` (clock/config/errors).
Le noyau, lui, ne dépend pas encore de ``builder``. Robuste : on parse les imports absolus **et**
relatifs de chaque fichier, sans dépendre de la mise en forme.
"""

from __future__ import annotations

import ast
from pathlib import Path

import scc_brainai_bootstrap.builder as _builder_pkg

BUILDER_DIR = Path(_builder_pkg.__file__).resolve().parent
PKG_ROOT = BUILDER_DIR.parent                      # .../src/scc_brainai_bootstrap
PKG_NAME = "scc_brainai_bootstrap"

# Ce que builder a le droit d'importer DANS le namespace du projet : lui-même + infra core.
_ALLOWED_INTERNAL = (f"{PKG_NAME}.builder", f"{PKG_NAME}.core")

# Moteurs cognitifs 11–16 + services métier du noyau : interdits d'import depuis builder.
_FORBIDDEN_PARTS = frozenset({
    "reasoning", "planning", "decision", "execution", "memory", "perception",  # moteurs 11–16
    "cognition", "dossier", "dossier_link", "learning", "patrimony",           # services métier
    "router", "event_bus", "session", "subscribers", "bootstrap",
    "components", "registry", "presentation", "cli", "doctor", "perception",
})


def _imported_modules(pyfile: Path) -> set[str]:
    """Modules importés par ``pyfile`` (imports absolus ; le nom pour les imports relatifs)."""
    tree = ast.parse(pyfile.read_text(encoding="utf-8"), filename=str(pyfile))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module)               # absolu ou nom relatif (ex. « builder »)
    return mods


def _builder_files() -> list[Path]:
    return sorted(BUILDER_DIR.glob("*.py"))


def test_builder_imports_only_itself_and_core():
    """Tout import projet depuis builder pointe vers ``builder`` ou ``core`` — rien d'autre."""
    offenders = []
    for py in _builder_files():
        for mod in _imported_modules(py):
            if mod.startswith(PKG_NAME) and not mod.startswith(_ALLOWED_INTERNAL):
                offenders.append(f"{py.name} → {mod}")
    assert not offenders, f"builder importe hors de builder/core : {offenders}"


def test_builder_imports_no_cognitive_engine_or_business_service():
    """Aucun moteur 11–16 ni service métier du noyau n'est importé par builder."""
    offenders = []
    for py in _builder_files():
        for mod in _imported_modules(py):
            if _FORBIDDEN_PARTS.intersection(mod.split(".")):
                offenders.append(f"{py.name} → {mod}")
    assert not offenders, f"builder importe un moteur/service interdit : {offenders}"


def test_kernel_does_not_import_builder():
    """Aucun module du noyau (hors builder/) n'importe builder dans le périmètre actuel."""
    offenders = []
    for py in PKG_ROOT.rglob("*.py"):
        if py == BUILDER_DIR / py.name and py.parent == BUILDER_DIR:
            continue                                 # on ignore les fichiers de builder lui-même
        if BUILDER_DIR in py.parents:
            continue
        for mod in _imported_modules(py):
            parts = mod.split(".")
            if mod.startswith(f"{PKG_NAME}.builder") or parts[-1] == "builder" or "builder" in parts[:-1]:
                offenders.append(f"{py.relative_to(PKG_ROOT)} → {mod}")
    assert not offenders, f"le noyau importe builder : {offenders}"
