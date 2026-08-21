"""Capacité de **conversation** — dialoguer avec l'utilisateur au sein d'une Pursuit (BRAINAI-CONVERSATION-001).

**Doctrine :** *Pursuit = unité de cognition · Fact = unité de mémoire/trace · Conversation = canal.* Le
dialogue de compréhension appartient à **la même Pursuit** que la future réalisation — il n'a **pas** d'identité
propre. Cette faculté ne construit **rien** (aucun Brief/Spécification/Manifeste) : elle **répond, questionne,
challenge, aide à réfléchir**, et **apprécie** la maturité du besoin (``readiness``).

BrainAI dépend d'une **capacité**, jamais d'un outil (R8) : l'outil concret (ici **Claude Code**) est un
adaptateur interchangeable. La ``readiness`` est une **appréciation cognitive / proposition** : elle ne déclenche
**jamais** la réalisation — **BrainAI propose, seule une confirmation humaine autorisera** le passage à l'arc
(Tâche 2). Confinement identique aux autres capacités : ``argv`` only, env minimal, timeout, **plafond coût**
contrôlé **avant** l'appel (R2/B4), **aucun retry** (R6). Primitives runtime via :mod:`claude_code_runtime`.
Stdlib pur. **Tâche 1 = contrat seul** (aucune orchestration, aucun appel réel, aucun fait produit).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from scc_brainai_bootstrap.builder.claude_code_runtime import diagnostic, extract_cost, parse_envelope
from scc_brainai_bootstrap.builder.adapter_contract import AdapterContract, claude_text_contract
from scc_brainai_bootstrap.builder.cognitive_identity import COGNITIVE_IDENTITY, compose_prompt
from scc_brainai_bootstrap.builder.provider_env import (
    AUTH_KEYCHAIN_HOME, auth_channel, confined_env, inbound_channels)
from scc_brainai_bootstrap.builder.tool_runner import run_confined

# Provenance épistémique d'un élément (EPISTEMIC-PROVENANCE, J1) — valeurs **émises par le modèle**. « vérifié »
# est **absent** de cette liste : il est **structurellement inémettable** par le modèle et réservé à une
# attribution SYSTÈME reposant sur une vérification réelle (J2+). Une hypothèse ne devient jamais un fait par
# simple survie de tours : la provenance est ré-émise à chaque tour, elle ne se durcit pas d'elle-même.
_ELEMENT_SOURCES_EMITTABLE = ("fourni_par_utilisateur", "connaissance_modele", "deduit", "suppose", "inconnu")

# Étiquettes lisibles (rendu A2), sans jamais parler de « vérifié » côté modèle.
_SOURCE_LABELS = {
    "fourni_par_utilisateur": "fourni par l'utilisateur", "connaissance_modele": "connaissance modèle",
    "deduit": "déduit", "suppose": "supposé", "inconnu": "inconnu",
}

# Élément d'un besoin mûri (C9) — extension **additive** (EPISTEMIC-PROVENANCE J1) : ``statement`` (gelé) +
# ``source`` OPTIONNELLE (provenance émise par le modèle). Jamais de remplacement destructif ; aucun champ « au
# cas où » au-delà de la provenance réellement exigée par J1.
_MATURED_ELEMENT: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "statement": {"type": "string"},
        "source": {"type": "string", "enum": list(_ELEMENT_SOURCES_EMITTABLE)},   # « vérifié » exclu du schéma
    },
    "required": ["statement"],
}

# ``matured_need`` **structuré** (C9) : sépare le besoin fondamental (invariant si la solution change) des
# solutions privilégiées, hypothèses actives et inconnues nommées. La présence d'``inconnues_nommees`` NE rend
# JAMAIS un ``ready`` invalide (C8) : une inconnue peut rester ouverte si sa résolution ne changerait pas le
# besoin fondamental.
_MATURED_NEED_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "besoin_fondamental": {"type": "string"},                       # ce que l'utilisateur cherche à résoudre
        "solutions_privilegiees": {"type": "array", "items": _MATURED_ELEMENT},  # pistes actuelles, révisables
        "inconnues_nommees": {"type": "array", "items": _MATURED_ELEMENT},       # ouvertes, non bloquantes (C8)
        "hypotheses_actives": {"type": "array", "items": _MATURED_ELEMENT},      # non confirmées
    },
    "required": ["besoin_fondamental", "solutions_privilegiees", "inconnues_nommees", "hypotheses_actives"],
}
_MATURED_LIST_KEYS = ("solutions_privilegiees", "inconnues_nommees", "hypotheses_actives")

# Schéma **structuré** de sortie d'un tour de conversation (forcé par ``--json-schema``). ``reply`` = réponse
# naturelle ; ``readiness`` = appréciation (``continue`` tant que le besoin n'est pas mûr ; ``ready`` quand il
# l'est) ; ``matured_need`` = besoin mûri **structuré** (fourni seulement quand ``ready``).
CONVERSATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {"type": "string"},                                   # réponse conversationnelle
        "readiness": {"type": "string", "enum": ["continue", "ready"]},  # appréciation cognitive
        "matured_need": _MATURED_NEED_SCHEMA,                           # besoin mûri structuré (si ready)
    },
    "required": ["reply", "readiness"],
}


def normalize_matured_need(value: Any) -> Optional[Dict[str, Any]]:
    """Normalise un ``matured_need`` en la structure C9 — **frontière de rétrocompatibilité** (D3).

    Accepte ``None``, une **chaîne legacy** (faits d'avant C9 : le besoin brut), ou la structure actuelle.
    Renvoie ``None`` si rien d'exploitable, sinon un dict aux quatre clés (listes d'éléments ``{statement}``).
    Ne réécrit **jamais** les faits persistés : c'est une conversion **en lecture**."""
    if value is None:
        return None
    if isinstance(value, str):
        besoin = value.strip()
        if not besoin:
            return None
        return {"besoin_fondamental": besoin, "solutions_privilegiees": [],
                "inconnues_nommees": [], "hypotheses_actives": []}
    if isinstance(value, dict):
        besoin_raw = value.get("besoin_fondamental")
        besoin = besoin_raw.strip() if isinstance(besoin_raw, str) else ""
        lists: Dict[str, Any] = {}
        for k in _MATURED_LIST_KEYS:
            elems = []
            for e in value.get(k) or []:
                if isinstance(e, dict) and isinstance(e.get("statement"), str) and e["statement"].strip():
                    el: Dict[str, Any] = {"statement": e["statement"].strip()}
                    src = e.get("source")                       # provenance émise conservée SI valide (5 valeurs) ;
                    if src in _ELEMENT_SOURCES_EMITTABLE:        # « vérifié »/invalide/absent → non persisté ⇒ inconnu en lecture
                        el["source"] = src
                    elems.append(el)
                elif isinstance(e, str) and e.strip():          # tolérance de lecture (legacy/edge)
                    elems.append({"statement": e.strip()})
            lists[k] = elems
        if not besoin and not any(lists.values()):
            return None
        return {"besoin_fondamental": besoin, **lists}
    return None


def element_source(element: Any) -> str:
    """Provenance épistémique d'un élément, **en lecture**. Absence de ``source`` (faits historiques d'avant J1,
    ou champ non émis) ⇒ ``inconnu`` — jamais fabriquée, jamais « vérifié ». Toute valeur hors des 5 valeurs
    émettables est traitée comme ``inconnu`` (aucune garde ne peut promouvoir en « vérifié »)."""
    if isinstance(element, dict):
        src = element.get("source")
        if src in _ELEMENT_SOURCES_EMITTABLE:
            return src
    return "inconnu"


def matured_need_present(matured: Any) -> bool:
    """Helper **unique** : un ``matured_need`` est-il effectivement présent ET valide (C8) — c.-à-d. porte un
    ``besoin_fondamental`` non vide ? Jamais fondé sur la simple truthiness d'un dict. Accepte la forme legacy
    (normalisée à la volée)."""
    m = normalize_matured_need(matured)
    return bool(m and m.get("besoin_fondamental"))


def matured_need_to_need_text(matured: Any) -> str:
    """**Pont de compatibilité** (A2) vers les facultés qui consomment encore un ``need: str`` (understanding).

    Rend un texte **explicitement typé** : la fonction de chaque élément reste lisible en toutes lettres — le
    besoin ne se confond jamais avec les solutions, hypothèses ou inconnues. Ne qualifie **pas** une inconnue de
    « phase suivante » : le routage futur n'appartient pas à Conversation.

    NB architectural : ce texte n'est **pas** l'interface cognitive définitive. Quand EXPLORATION existera, elle
    consommera le ``matured_need`` **structuré depuis le fait persisté** — l'objet est la vérité, ce texte n'est
    qu'un adaptateur temporaire pour la chaîne actuelle."""
    m = normalize_matured_need(matured) or {"besoin_fondamental": "", "solutions_privilegiees": [],
                                             "inconnues_nommees": [], "hypotheses_actives": []}
    lines = ["BESOIN FONDAMENTAL — ce que l'utilisateur cherche réellement à obtenir ou résoudre :",
             m.get("besoin_fondamental") or "(non précisé)"]
    sections = [
        ("solutions_privilegiees", "SOLUTIONS PRIVILÉGIÉES À CE STADE (pistes actuelles, révisables ; ne constituent pas le besoin) :"),
        ("hypotheses_actives", "HYPOTHÈSES ACTIVES (non confirmées) :"),
        ("inconnues_nommees", "INCONNUES NOMMÉES (ouvertes, non bloquantes pour la définition du besoin) :"),
    ]
    for key, header in sections:
        elems = m.get(key) or []
        if elems:
            lines.append("")
            lines.append(header)
            # Chaque élément porte sa provenance en toutes lettres (EPISTEMIC-PROVENANCE) — jamais « vérifié ».
            lines.extend(f"- {e['statement']}  [{_SOURCE_LABELS[element_source(e)]}]" for e in elems)
    return "\n".join(lines)

# Champs requis d'un tour valide + valeurs d'appréciation admises (garde-fou du contrat).
_TURN_REQUIRED = tuple(CONVERSATION_SCHEMA["required"])
_READINESS_VALUES = tuple(CONVERSATION_SCHEMA["properties"]["readiness"]["enum"])


# Mission du tour de dialogue — la **tâche**, préfixée par l'**identité** (nature) via ``compose_prompt``.
# Les consignes actuelles sont conservées intégralement ; les QUATRE dernières phrases sont des traductions
# locales des mécanismes M3/M4/M6/M8 (archéologie) — aucune règle nouvelle, aucune méthode récitée. La voix
# (habiter une nature, prendre position, chasser les angles morts) vit dans ``COGNITIVE_IDENTITY`` ; ici, la
# mission ne fait que dire ce que ce tour attend et rappeler comment répondre.
_CONVERSATION_MISSION = (
    "MISSION DU TOUR — dialogue de compréhension. Ce tour est du dialogue, pas une réalisation : "
    "NE CONSTRUIS RIEN (aucun brief, aucune spécification, aucun manifeste). Dialogue naturellement, à partir "
    "de l'historique relu ci-dessous et du message de l'utilisateur. Apprécie la maturité du besoin : "
    "``readiness='continue'`` tant qu'il n'est pas réellement mûr ; ``readiness='ready'`` seulement lorsqu'il "
    "l'est vraiment — et fournis alors ``matured_need`` (le besoin reformulé, prêt à réaliser). La ``readiness`` "
    "est une APPRÉCIATION : elle ne lance jamais la réalisation ; seule une confirmation humaine l'autorisera.\n\n"
    "À chaque tour, ta réponse fait progresser la réflexion : une reformulation, une hypothèse, un angle mort, "
    "une contradiction relevée, une piste, un arbitrage provisoire — ou une question de clarification courte et "
    "parfaitement justifiée quand c'est la meilleure contribution. Ce qui est exclu, c'est l'interrogatoire : une "
    "suite de questions sans pensée offerte en retour.\n\n"
    "Avant de répondre, envisage plusieurs lectures possibles de la situation et choisis la contribution qui "
    "réduit le plus l'incertitude ; sur les choix structurants, montre les lectures envisagées et motive ton "
    "choix.\n\n"
    "Quand plusieurs pistes deviennent suffisamment étayées, ne reste pas neutre : indique celle que tu "
    "privilégies et pourquoi ; si elles se valent réellement, dis-le.\n\n"
    "Si deux tours consécutifs n'ont apporté ni matière nouvelle ni correction, ne pose pas une question de "
    "plus : propose — une restitution à confirmer, un arbitrage, ou le constat honnête que la conversation "
    "piétine et ce qu'il faudrait pour la débloquer.\n\n"
    # C8 — calibration de convergence (D5) : distinguer l'inconnue bloquante de l'inconnue non bloquante.
    "Distingue une inconnue bloquante — sa résolution pourrait changer le besoin fondamental lui-même — d'une "
    "inconnue non bloquante — le besoin fondamental est déjà suffisamment défini et l'inconnue peut rester "
    "ouverte. Ne diffère pas la maturité pour des inconnues non bloquantes : lorsque les conditions de maturité "
    "sont réunies et que seules subsistent des inconnues dont la résolution ne changerait pas le besoin "
    "fondamental, déclare le besoin mûr tout en conservant explicitement ces inconnues ouvertes.\n\n"
    # C9 — remplissage du besoin mûri structuré quand ready.
    "Quand tu déclares le besoin mûr (readiness='ready'), structure ``matured_need`` en distinguant : le besoin "
    "fondamental (ce que l'interlocuteur cherche réellement à obtenir ou résoudre — il reste invariant si la "
    "solution privilégiée change) ; les solutions privilégiées à ce stade (pistes actuelles, révisables, qui ne "
    "sont pas le besoin) ; les hypothèses actives (non confirmées) ; les inconnues nommées (ouvertes, non "
    "bloquantes pour la définition du besoin).\n\n"
    # EPISTEMIC-PROVENANCE (J1) — chaque élément porte sa provenance émise.
    "Pour CHAQUE solution, hypothèse ou inconnue, renseigne son champ ``source`` — sa provenance — parmi : "
    "``fourni_par_utilisateur`` (l'interlocuteur l'a dit) · ``connaissance_modele`` (savoir général, non propre "
    "à ce dialogue) · ``deduit`` (conclusion logique tirée de l'échange) · ``suppose`` (hypothèse non confirmée) "
    "· ``inconnu`` (provenance incertaine). N'emploie JAMAIS « vérifié » : ce statut est réservé à une "
    "vérification réelle du système, pas à ton appréciation. Une hypothèse ne devient pas un fait parce qu'elle "
    "a traversé plusieurs tours : garde sa provenance réelle.\n\n"
    "Réponds UNIQUEMENT via le schéma imposé."
)


def build_prompt(message: str, history: List[Dict[str, Any]]) -> str:
    """Prompt déterministe d'un tour de dialogue = **identité** (nature, ``COGNITIVE_IDENTITY``) puis **mission**
    (tâche du tour) via :func:`compose_prompt`, suivies de l'historique et du message. ``history`` : tours
    antérieurs (``{role, content}``) relus par le moteur depuis le ``pursuit_id`` — jamais depuis l'UI. BrainAI
    **dialogue** et **apprécie** la maturité ; il ne construit rien et n'autorise rien. La Constitution, elle,
    n'est jamais envoyée au modèle : seuls l'identité et la mission l'atteignent."""
    lines: List[str] = []
    for turn in history or []:
        role = "Utilisateur" if turn.get("role") == "user" else "BrainAI"
        lines.append(f"{role}: {turn.get('content', '')}")
    convo = "\n".join(lines)
    body = (f"HISTORIQUE :\n{convo}\n\n" if convo else "") + f"MESSAGE : {message}"
    return compose_prompt(COGNITIVE_IDENTITY, f"{_CONVERSATION_MISSION}\n\n{body}")


def build_turn(*, message: str, prompt: str, capability: str, adapter: str, model: Optional[str],
               envelope: Optional[Dict[str, Any]], exit_code: Any, timed_out: bool, as_of: str,
               argv: Any = None, stdout: Any = None, stderr: Any = None,
               pursuit_ref: Optional[str] = None) -> Dict[str, Any]:
    """Construit un **fait tour** honnête (pur, testable) — miroir de :func:`build_proposal`.

    ``proposed`` uniquement si : pas de timeout, ``exit_code == 0`` (ou ``None``), enveloppe lisible, non
    ``is_error``, ``subtype == "success"``, ET tour conforme (``reply`` chaîne, ``readiness`` ∈ enum). Sinon
    ``failed`` — sans crash, avec ``error`` (jamais ``"success"``) et un ``diagnostic`` brut borné assaini.
    Coût toujours enregistré (réel ou ``unavailable``). ``diagnostic = None`` sur un fait ``proposed``. Porte
    ``fact_type='turn'`` et un ``pursuit_ref`` (ancrage de provenance vers la Pursuit). **Ne construit rien**
    (aucun brief/spéc/manifeste) : un tour n'est que du dialogue et une **appréciation** de maturité."""
    cost = extract_cost(envelope)
    usage = envelope.get("usage") if envelope else None
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    base: Dict[str, Any] = {
        "fact_type": "turn",
        "capability": capability,
        "adapter": adapter,
        "model": model,
        "message": message,
        "pursuit_ref": pursuit_ref,
        "prompt": prompt,
        "prompt_sha256": prompt_sha256,
        "params": {"output_format": "json", "json_schema": "CONVERSATION_SCHEMA"},
        "usage": usage if usage is not None else "unavailable",
        "cost": cost,
        "as_of": as_of,
    }
    diag = diagnostic(argv=argv, stdout=stdout, stderr=stderr, exit_code=exit_code,
                      timed_out=timed_out, envelope=envelope)
    nonzero_exit = exit_code is not None and exit_code != 0
    # Échec d'appel : timeout / exit non nul / enveloppe illisible / erreur cerveau / subtype ≠ success.
    if (timed_out or envelope is None or nonzero_exit
            or envelope.get("is_error") or envelope.get("subtype") != "success"):
        if timed_out:
            reason = "timeout"
        elif envelope is None:
            reason = "enveloppe illisible"
        elif nonzero_exit:
            reason = f"exit non nul ({exit_code})"
        elif envelope.get("is_error") and envelope.get("subtype") == "success":
            reason = "erreur client sans détail (voir diagnostic)"
        else:
            reason = str(envelope.get("api_error_status") or envelope.get("subtype") or "erreur d'appel")
        if reason == "success":     # garde-fou : ``error`` ne peut jamais afficher "success"
            reason = "erreur client sans détail (voir diagnostic)"
        return {**base, "status": "failed", "reply": None, "readiness": None, "matured_need": None,
                "error": reason, "diagnostic": diag}
    # Réponse présente : valider le format du tour.
    result = envelope.get("result")
    turn: Optional[Dict[str, Any]] = None
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                turn = parsed
        except json.JSONDecodeError:
            turn = None
    elif isinstance(result, dict):
        turn = result
    valid = (isinstance(turn, dict) and all(k in turn for k in _TURN_REQUIRED)
             and isinstance(turn.get("reply"), str) and turn.get("readiness") in _READINESS_VALUES)
    if not valid:
        return {**base, "status": "failed", "reply": None, "readiness": None, "matured_need": None,
                "error": "format tour invalide", "diagnostic": diag}
    matured = normalize_matured_need(turn.get("matured_need"))   # structure C9 (ou None), lecture legacy tolérée
    has_matured = matured is not None                            # le modèle a fourni un contenu de besoin mûri
    # Garde de cohérence A4-2 : un ``matured_need`` n'a de sens qu'avec une appréciation ``ready``. Un besoin
    # « mûri » porté par un tour ``continue`` est une incohérence cognitive (maturité affirmée sans l'avoir
    # jugée) ⇒ tour **non conforme**, ``failed``. Ainsi un ``matured_need`` ne vit jamais que sur un ``ready`` —
    # ce que la garde de convergence de ``realize`` (A4-1) suppose côté relecture.
    if has_matured and turn["readiness"] != "ready":
        return {**base, "status": "failed", "reply": None, "readiness": None, "matured_need": None,
                "error": "matured_need sans appréciation ready", "diagnostic": diag}
    # Garde de cohérence C8/C9 : un besoin **mûr** doit être **définissable**. Un ``ready`` sans ``besoin
    # fondamental`` non vide est incohérent ⇒ ``failed``. La présence d'``inconnues_nommees`` NE bloque PAS un
    # ``ready`` (C8) : seules comptent la présence et la non-vacuité du besoin fondamental (helper unique).
    if turn["readiness"] == "ready" and not matured_need_present(turn.get("matured_need")):
        return {**base, "status": "failed", "reply": None, "readiness": None, "matured_need": None,
                "error": "ready sans besoin fondamental", "diagnostic": diag}
    return {**base, "status": "proposed", "reply": turn["reply"], "readiness": turn["readiness"],
            "matured_need": matured, "error": None, "diagnostic": None}


@runtime_checkable
class ConversationCapability(Protocol):
    """**Capacité** « dialoguer » (R8) — BrainAI en dépend, jamais d'un outil concret.

    Contrat minimal : produire, pour un ``message`` et un ``history`` (tours antérieurs de la **même** Pursuit),
    la matière brute d'un tour (enveloppe/exit/timeout/prompt), **après** contrôle du budget. L'implémentation
    concrète (ici Claude Code) est interchangeable ; le reste du système ne connaît que ce Protocol."""

    capability: str
    name: str
    model: str

    def propose(self, message: str, *, history: List[Dict[str, Any]], cwd: Path,
                budget_remaining_usd: float) -> Dict[str, Any]:
        ...


class ClaudeCodeConversationAdapter:
    """Implémentation **Claude Code non-interactif** de :class:`ConversationCapability` (R8)."""

    capability = "conversation"
    name = "claude_code"

    def __init__(self, *, model: str = "haiku", max_budget_usd: float = 0.50,
                 timeout: float = 120.0, claude_bin: str = "claude",
                 auth_mode: str = AUTH_KEYCHAIN_HOME, isolated_home: Optional[str] = None,
                 oauth_token: Optional[str] = None):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.claude_bin = claude_bin
        self.auth_mode = auth_mode              # bascule d'auth (B1 défaut) — étanchéité J3/T1
        self.isolated_home = isolated_home
        self.oauth_token = oauth_token

    def build_argv(self, prompt: str) -> List[str]:
        """argv **only** (jamais shell) : print non-interactif, JSON structuré, modèle explicite, plafond coût,
        outils fichier/bash **désactivés** — un tour de dialogue est du texte seul, il ne construit rien."""
        return [
            self.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--json-schema", json.dumps(CONVERSATION_SCHEMA, ensure_ascii=False),
            "--model", self.model,
            "--max-budget-usd", str(self.max_budget_usd),
            "--disallowedTools", "Bash", "Edit", "Write", "Read", "WebSearch", "WebFetch",
        ]

    def _env(self) -> Dict[str, str]:
        # Env confiné **centralisé** (provider_env) selon la bascule d'auth : B1 (défaut) = comportement
        # historique ; cible = HOME isolé + jeton explicite (étanchéité J3/T1, RS-030). Canal d'auth déclaré (AM6).
        return confined_env(self.auth_mode, isolated_home=self.isolated_home, oauth_token=self.oauth_token)

    def contract(self) -> AdapterContract:
        """Contrat d'adaptateur complet (T2). Déclare un **canal entrant supplémentaire** : l'historique — **scopé
        à CETTE Pursuit uniquement** (I9 : jamais la Pursuit entière portée dans un canal fournisseur)."""
        return claude_text_contract(
            capability=self.capability, auth_channel=auth_channel(self.auth_mode),
            inbound_channels=inbound_channels(self.auth_mode),
            tools_disallowed=["Bash", "Edit", "Write", "Read", "WebSearch", "WebFetch"],
            extra_inbound=[{"channel": "argv:history", "carries": "tours (message/reply) de CETTE Pursuit uniquement",
                            "pursuit_scoped": True, "carries_whole_pursuit": False}])

    def propose(self, message: str, *, history: List[Dict[str, Any]], cwd: Path,
                budget_remaining_usd: float) -> Dict[str, Any]:
        """**Appel réel facturable**. Vérifie le budget AVANT (R2/B4) ; refuse sans appel si le reste ne couvre
        pas le plafond (``run_confined`` **non atteint**). Renvoie ``{called, envelope, exit_code, timed_out,
        prompt, argv, stdout, stderr}`` — ne construit pas le fait (séparation)."""
        prompt = build_prompt(message, history)
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


__all__ = ["CONVERSATION_SCHEMA", "build_prompt", "build_turn", "ConversationCapability",
           "ClaudeCodeConversationAdapter", "normalize_matured_need", "matured_need_present",
           "matured_need_to_need_text", "element_source"]
