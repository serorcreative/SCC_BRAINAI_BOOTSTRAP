"""Adaptateur **OpenAI** de la capacité « comprendre un besoin » (L6A — 2ᵉ provider réel).

CONNECTER, PAS RECONSTRUIRE. BrainAI dépend d'une **capacité** (Protocol
:class:`~scc_brainai_bootstrap.builder.understanding.NeedUnderstandingCapability`), jamais d'un outil : cet
adaptateur satisfait **exactement le même contrat** que ``ClaudeCodeUnderstandingAdapter`` et **réutilise** le
paquet provider-neutral existant — la charte/identité + la mission (:func:`build_prompt`) et le schéma structuré
(:data:`BRIEF_SCHEMA`). BrainAI **possède le contexte** ; OpenAI est un **consultant** : il reçoit une mission
bornée + un schéma, il **propose** (R5), il ne décide ni ne possède la mémoire (INV-COGNITION-PROMPT,
INV-PROVIDER-INTERCHANGEABLE).

Étanchéité & sûreté (RS-030 / RS-057 / I6) :
- **Canal d'auth propre à l'executor** : clé API serveur lue **uniquement** via ``OPENAI_API_KEY`` au moment de
  l'appel réel — jamais stockée, jamais journalisée, jamais dans Git/fixtures. ``leaks_identity=False`` (aucune
  surface HOME/trousseau, contrairement à B1 de Claude Code). Le **nom** de la variable est autorisé, sa **valeur**
  ne l'est jamais. C'est l'admission du 2ᵉ executor réel qui rend ``token_var`` pertinent au niveau adaptateur (RS-057).
- **Coût** : les Responses OpenAI renvoient des **tokens d'usage réels**, pas un coût USD par appel → le contrat
  déclare ``cost_report.mode = unavailable`` (I6 : jamais de coût fabriqué). Le plafond USD natif ``none`` ; le
  garde-fou budgétaire est **enforced_by_brainai** (refus AVANT appel).
- **Aucun retry** (R6). **Aucun fallback silencieux** vers un autre provider. **Aucune fuite** : tout texte
  d'erreur passe par :func:`redact`.

Le **client** est **injectable** (port ``respond``) : les tests fournissent un faux client déterministe (0 $, aucun
SDK requis). Le client réel (lazy-import du SDK ``openai``) n'est construit qu'au moment d'un appel réel explicite.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.adapter_contract import AdapterContract
from scc_brainai_bootstrap.builder.claude_code_runtime import redact
from scc_brainai_bootstrap.builder.tool_runner import DEFAULT_WATCHDOG_S
from scc_brainai_bootstrap.builder.understanding import BRIEF_SCHEMA, build_prompt

# Modèle par DÉFAUT — **configurable** au constructeur (aucun couplage de l'architecture à un modèle précis).
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
# Nom (jamais la valeur) de la variable portant la clé API serveur.
OPENAI_API_KEY_VAR = "OPENAI_API_KEY"


@runtime_checkable
class StructuredResponder(Protocol):
    """Port minimal **injectable** d'un client structuré : produit, pour un ``prompt`` + un ``schema``, un texte
    conforme au schéma. Retourne ``{"text": <str JSON conforme>, "usage": <dict|None>}`` ; **lève** sur erreur
    (auth/réseau/rate-limit) — l'adaptateur normalise l'exception en enveloppe d'échec, sans fuite."""

    def respond(self, *, prompt: str, schema: Dict[str, Any], model: str, timeout: float) -> Dict[str, Any]:
        ...


def build_responses_request(prompt: str, schema: Dict[str, Any], model: str) -> Dict[str, Any]:
    """Kwargs de ``client.responses.create(**kwargs)`` pour l'**API Responses** (SDK ``openai`` ≥ 1.x) avec
    **Structured Outputs**. Forme correcte de la Responses API : le schéma vit sous ``text.format`` (type
    ``json_schema``, ``name``/``schema``/``strict``) — **et non** le paramètre ``response_format`` de
    *Chat Completions*. Fonction **pure** → testable à 0 $ sans SDK ni réseau (banc de contrat des arguments)."""
    return {
        "model": model,
        "input": prompt,
        "text": {"format": {"type": "json_schema", "name": "brief", "schema": schema, "strict": True}},
    }


def _build_real_client(api_key: str, api_key_var: str) -> StructuredResponder:
    """Construit le client OpenAI **réel** (lazy-import du SDK). N'est appelé qu'à un appel réel explicite —
    jamais en test $0. Le SDK n'étant pas une dépendance de base (extra ``openai``), son absence est un **échec
    normalisé** (``sdk_absent``), pas un crash. La clé n'est ni journalisée ni retournée."""
    try:
        from openai import OpenAI  # type: ignore  # lazy — SDK en extra, importé seulement ici
    except Exception as exc:  # noqa: BLE001 - ImportError ou autre : échec normalisé en amont
        raise RuntimeError("sdk_absent") from exc

    class _OpenAIResponder:
        def __init__(self) -> None:
            self._client = OpenAI(api_key=api_key)      # la valeur de clé reste locale à cette instance

        def respond(self, *, prompt: str, schema: Dict[str, Any], model: str, timeout: float) -> Dict[str, Any]:
            # API Responses + Structured Outputs (text.format json_schema). Timeout par appel via with_options
            # (mécanisme SDK documenté). Chemin exercé uniquement au test réel gated (GO-secrets). Aucun retry (R6).
            client = self._client.with_options(timeout=timeout) if hasattr(self._client, "with_options") else self._client
            resp = client.responses.create(**build_responses_request(prompt, schema, model))
            text = getattr(resp, "output_text", None)
            usage = getattr(resp, "usage", None)
            usage_d = usage.model_dump() if hasattr(usage, "model_dump") else (dict(usage) if usage else None)
            return {"text": text, "usage": usage_d}

    return _OpenAIResponder()


class OpenAIUnderstandingAdapter:
    """Implémentation **OpenAI** de ``NeedUnderstandingCapability`` (même contrat que l'adaptateur Claude Code)."""

    capability = "understanding"
    name = "openai"

    def __init__(self, *, model: str = DEFAULT_OPENAI_MODEL, max_budget_usd: float = 0.50,
                 timeout: float = DEFAULT_WATCHDOG_S, api_key_var: str = OPENAI_API_KEY_VAR,
                 client: Optional[StructuredResponder] = None):
        self.model = model                          # configurable — aucun modèle codé en dur dans l'architecture
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.api_key_var = api_key_var              # NOM de la variable (jamais la valeur)
        self._client = client                       # port injectable (tests $0) ; None => client réel à l'appel

    def build_argv(self, prompt: str) -> Optional[List[str]]:
        """OpenAI est appelé en HTTP : **aucun** ``argv`` de sous-processus (parité de forme avec l'adaptateur CLI)."""
        return None

    def contract(self) -> AdapterContract:
        """Contrat **complet** (T2) déclarant la surface RÉELLE de cet adaptateur : auth par **clé API explicite**
        (aucune fuite d'identité, RS-030/RS-057), coût **unavailable** (I6 : OpenAI ne renvoie pas de coût USD),
        plafond USD natif ``none`` + plafond d'appel **enforced_by_brainai**, aucun outil, aucun workspace fichier."""
        return AdapterContract(
            capabilities_served=(self.capability,),
            auth_channel={"kind": "api_key", "explicit": True, "leaks_identity": False,
                          "token_var": self.api_key_var,
                          "detail": "clé API serveur (OPENAI_API_KEY) — aucune surface HOME/trousseau/identité"},
            inbound_channels=(
                {"channel": "api:request", "carries": "prompt (mission bornée) + json_schema",
                 "pursuit_scoped": True},
                {"channel": f"env:{self.api_key_var}", "carries": "clé API serveur",
                 "pursuit_scoped": False, "identity_surface": False,
                 "note": "lue au moment de l'appel réel uniquement ; jamais journalisée ni persistée"},
            ),
            cost_report={"mode": "unavailable", "fabricated": False},
            native_budget={"usd_cap": "none", "call_cap": "enforced_by_brainai"},
            confinement={"workspace": False, "tools_allowed": [], "tools_disallowed": [],
                         "permission_mode": "api_no_tools", "env_mode": "api_key"},
        )

    def _refused(self, prompt: str, reason: str) -> Dict[str, Any]:
        """Refus AVANT tout appel (budget / clé absente) : aucun appel, aucune enveloppe, motif honnête."""
        return {"called": False, "envelope": None, "exit_code": None, "timed_out": False,
                "prompt": prompt, "argv": None, "stdout": None, "stderr": None, "refused": reason}

    def _fail_envelope(self, prompt: str, *, subtype: str, api_error_status: str) -> Dict[str, Any]:
        """Échec d'appel **normalisé** dans l'enveloppe attendue en amont (``build_proposal`` la traite comme
        ``failed``) : ``is_error=True``, ``subtype`` de classe, ``api_error_status`` assaini. Aucun secret."""
        return {"called": True, "prompt": prompt, "argv": None, "stdout": None, "stderr": None,
                "exit_code": 0, "timed_out": False,
                "envelope": {"subtype": subtype, "is_error": True, "result": None,
                             "api_error_status": redact(str(api_error_status))}}

    def propose(self, need: str, *, cwd: Path, budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable** (si sélectionné). Réutilise le paquet provider-neutral (charte+mission+schéma)
        via :func:`build_prompt`. Vérifie le budget AVANT (garde BrainAI) ; refuse sans appel si insuffisant. Lit la
        clé **uniquement** ici, via ``api_key_var`` ; absence => refus fail-closed (aucun appel). Normalise la réponse
        OpenAI dans l'**enveloppe** attendue (``result`` = JSON conforme au Brief) — l'amont ignore tout d'OpenAI.
        Aucun retry, aucun fallback silencieux, aucune fuite (``redact``)."""
        prompt = build_prompt(need)                 # même charte/identité/mission/schéma que le chemin Claude
        if budget_remaining_usd < self.max_budget_usd:
            return self._refused(prompt, "budget insuffisant")

        client = self._client
        if client is None:
            key = os.environ.get(self.api_key_var)
            if not key:
                return self._refused(prompt, f"{self.api_key_var} absent")   # fail-closed, aucun appel
            try:
                client = _build_real_client(key, self.api_key_var)
            except Exception as exc:  # noqa: BLE001 - ex. SDK absent
                return self._fail_envelope(prompt, subtype="sdk_error", api_error_status=type(exc).__name__)

        try:
            raw = client.respond(prompt=prompt, schema=BRIEF_SCHEMA, model=self.model, timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001 - auth/réseau/rate-limit : normalisé, jamais propagé
            return self._fail_envelope(prompt, subtype="api_error", api_error_status=type(exc).__name__)

        text = raw.get("text") if isinstance(raw, dict) else None
        usage = raw.get("usage") if isinstance(raw, dict) else None
        envelope = {"subtype": "success", "is_error": False, "result": text,
                    "usage": usage if usage is not None else "unavailable",
                    "api_error_status": None}       # pas de total_cost_usd => extract_cost renvoie unavailable (I6)
        return {"called": True, "envelope": envelope, "exit_code": 0, "timed_out": False,
                "prompt": prompt, "argv": None, "stdout": None, "stderr": None}


__all__ = ["OpenAIUnderstandingAdapter", "StructuredResponder", "build_responses_request",
           "DEFAULT_OPENAI_MODEL", "OPENAI_API_KEY_VAR"]
