"""BuildProvider **déterministe local** (L9) — 2ᵉ exécutant interchangeable de la capacité ``build.site``.

CONNECTER, PAS RECONSTRUIRE : implémente **exactement le même contrat** :class:`SiteBuildCapability` que
:class:`~scc_brainai_bootstrap.builder.site.ClaudeCodeSiteAdapter`, et se branche **sans modification** dans le
chemin existant ``produce_site_build`` → ``run_delivery``. Différence unique : la construction est **déterministe
et locale** — BrainAI écrit lui-même un ``index.html`` autonome dérivé **strictement** de la Spécification, sans
**aucun** LLM, **aucun** réseau, **aucun** subprocess (coût ``unavailable`` — I6, jamais fabriqué).

Invariants L9 gouvernés :
* provider **explicitement sélectionnable** (``deterministic_local``), **jamais** un fallback automatique silencieux ;
* écriture bornée au ``cwd`` (Workspace confiné) ; l'artefact est **collecté puis validé** par l'appelant
  (``collect_artifacts`` → ``Workspace.resolve_within``) exactement comme pour l'adaptateur Claude Code ;
* la sortie est un **fait ``build`` proposé** (jamais officiel) ; provenance de l'exécutant conservée
  (``ToolInvocation`` sous ``tool="deterministic_local"``).

Isolation d'imports du ``builder`` respectée : ne dépend que de ``builder`` + stdlib.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List, Optional

from scc_brainai_bootstrap.builder.adapter_contract import AdapterContract, local_build_contract
from scc_brainai_bootstrap.builder.site import SITE_ENTRYPOINT

# Identifiant provider **canonique** (registre L9) — distinct de ``claude_code`` (défaut historique) et
# volontairement qualifié (``deterministic_local``) : ``local`` seul serait trop générique pour un registre
# appelé à accueillir d'autres exécutants locaux.
PROVIDER_NAME = "deterministic_local"

_SECTIONS = [
    ("users_and_roles", "Utilisateurs et rôles"),
    ("functional_scope", "Périmètre fonctionnel"),
    ("features", "Fonctionnalités"),
    ("entities_and_data", "Entités et données"),
    ("key_journeys", "Parcours clés"),
    ("constraints", "Contraintes"),
    ("acceptance_criteria", "Critères d'acceptation"),
    ("assumptions", "Hypothèses"),
    ("open_questions", "Questions ouvertes"),
    ("out_of_scope", "Hors périmètre"),
]


def render_index_html(spec: Dict[str, Any]) -> str:
    """Rend un ``index.html`` **autonome et déterministe** dérivé **exclusivement** de la Spécification (aucun
    contenu inventé). Échappement HTML strict ; ordre des champs stable ; CSS en ligne ; aucun accès réseau."""
    objective = html.escape(str(spec.get("product_objective") or "Application"))
    parts: List[str] = [
        "<!DOCTYPE html>",
        '<html lang="fr">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="generator" content="brainai:deterministic_local">',
        f"<title>{objective}</title>",
        "<style>body{font-family:system-ui,Arial,sans-serif;margin:2rem auto;max-width:52rem;line-height:1.5;"
        "padding:0 1rem;color:#1a1a1a}h1{font-size:1.6rem}h2{font-size:1.15rem;margin-top:1.6rem}"
        "ul{padding-left:1.2rem}footer{margin-top:2rem;color:#666;font-size:.85rem}</style>",
        "</head>",
        "<body>",
        f"<h1>{objective}</h1>",
    ]
    for key, label in _SECTIONS:
        value = spec.get(key)
        items = [str(x) for x in value if isinstance(x, (str, int, float))] if isinstance(value, list) else []
        if not items:
            continue
        parts.append(f"<h2>{html.escape(label)}</h2>")
        parts.append("<ul>")
        parts.extend(f"<li>{html.escape(item)}</li>" for item in items)
        parts.append("</ul>")
    parts.append("<footer>Page statique générée localement par BrainAI (déterministe, sans LLM ni réseau) "
                 "à partir de la spécification.</footer>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"


class LocalDeterministicSiteAdapter:
    """Implémentation **locale déterministe** de :class:`SiteBuildCapability` (L9). Écrit ``index.html`` dans le
    ``cwd`` confiné, **sans** fournisseur externe. Expose le **même** contrat d'appel que l'adaptateur Claude Code
    (``build`` renvoyant ``{called, envelope, exit_code, timed_out, prompt, argv, stdout, stderr}``) afin d'être
    interchangeable **sans toucher** ``produce_site_build``/``run_delivery``. Coût ``unavailable`` (I6)."""

    capability = "build"
    name = PROVIDER_NAME
    model = "deterministic"

    def __init__(self) -> None:
        # Aucun budget à borner : construction locale déterministe à coût nul (aucun appel facturable).
        self.max_budget_usd = 0.0

    def contract(self) -> AdapterContract:
        """Contrat complet (T2) — construction locale confinée, aucun fournisseur/auth/réseau, coût ``unavailable``."""
        return local_build_contract(capability=self.capability)

    def build(self, spec: Dict[str, Any], *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        """Construit **réellement mais localement** : écrit ``index.html`` déterministe dans ``cwd`` (confiné) ;
        aucun LLM, réseau ni subprocess. Renvoie une enveloppe **succès sans coût** (``total_cost_usd`` absent ⇒
        ``extract_cost`` = ``unavailable``, I6) — l'appelant collecte/valide les artefacts et bâtit le fait.

        ``budget_remaining_usd`` est **ignoré** : la construction locale ne consomme aucun budget fournisseur
        (jamais de refus budgétaire ici). Aucune politique de fallback : ce provider ne s'active que s'il est
        **explicitement sélectionné**."""
        html_text = render_index_html(spec)
        target = Path(cwd) / SITE_ENTRYPOINT
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text, encoding="utf-8")     # écriture confinée (cwd = Workspace de la Pursuit)
        # Enveloppe "succès" SANS coût (I6) : pas de total_cost_usd ⇒ cost=unavailable ; pas d'usage.
        envelope: Dict[str, Any] = {"type": "result", "subtype": "success", "is_error": False,
                                    "api_error_status": None, "num_turns": 0}
        prompt = ("deterministic_local: rendu de index.html à partir de la spécification "
                  "(aucun LLM, aucun réseau, aucun subprocess).")
        return {"called": True, "envelope": envelope, "exit_code": 0, "timed_out": False,
                "prompt": prompt, "argv": [self.name], "stdout": "", "stderr": ""}


__all__ = ["PROVIDER_NAME", "render_index_html", "LocalDeterministicSiteAdapter"]
