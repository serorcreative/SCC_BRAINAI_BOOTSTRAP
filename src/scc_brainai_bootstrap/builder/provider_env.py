"""Environnement confiné & **canal d'authentification** d'un adaptateur fournisseur (JALON 3, T1/Q1).

**Étanchéité informationnelle.** Le forensique T3 a prouvé que l'auth par trousseau (barreau **B1**) transmet
``HOME`` au fournisseur, qui lit ``~/.claude.json`` (champ ``oauthAccount`` : email/identité) et l'injecte dans le
contexte du modèle — le **canal d'auth est un canal de fuite** (RS-030). Ce module centralise le calcul de
l'environnement confiné et **déclare** le canal d'auth, derrière une **bascule** :

* ``AUTH_KEYCHAIN_HOME`` (**B1, défaut**) : comportement historique — ``PATH``/``LANG`` + ``HOME``/``USER``/
  ``LOGNAME``. Auth hors-bande (trousseau). **``leaks_identity=True``** : ``~/.claude.json`` reste lisible.
* ``AUTH_EXPLICIT_TOKEN`` (**cible**) : ``HOME`` **isolé** (répertoire propre, sans ``~/.claude.json``) + jeton
  explicite (``CLAUDE_CODE_OAUTH_TOKEN``) en variable dédiée. Ni ``USER``/``LOGNAME``, ni le ``HOME`` personnel :
  aucune surface d'identité de l'opérateur. **``leaks_identity=False``** (à **prouver** empiriquement, jamais supposé).

**On ne débranche jamais B1 avant que la cible ait PASS** (RS-4) : la bascule est explicite, B1 est le défaut. Le
principe de contrat (AM6) est **indépendant de la technologie** : un autre fournisseur déclarera clé API / OAuth de
service / secret manager — le contrat impose *auth explicite + canal déclaré*, pas une techno précise. Stdlib pur ;
n'importe que ``os``. Isolation d'imports du ``builder`` respectée.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# Modes d'authentification (bascule). B1 reste le DÉFAUT tant que la cible n'a pas PASS (RS-4).
AUTH_KEYCHAIN_HOME = "keychain_home"      # barreau B1 — trousseau via HOME ; leaks_identity=True
AUTH_EXPLICIT_TOKEN = "explicit_token"    # cible — HOME isolé + jeton explicite ; leaks_identity=False (à prouver)

AUTH_MODES = (AUTH_KEYCHAIN_HOME, AUTH_EXPLICIT_TOKEN)

# Nom de la variable de jeton (choix d'implémentation Claude Code du jour — AM6 : non dogmatique).
OAUTH_TOKEN_VAR = "CLAUDE_CODE_OAUTH_TOKEN"


def confined_env(auth_mode: str = AUTH_KEYCHAIN_HOME, *, isolated_home: Optional[str] = None,
                 oauth_token: Optional[str] = None) -> Dict[str, str]:
    """Calcule l'environnement **confiné** transmis au sous-processus fournisseur, selon le mode d'auth.

    ``keychain_home`` (défaut) : ``PATH``/``LANG`` + ``HOME``/``USER``/``LOGNAME`` présents — **identique** au
    comportement historique (aucune régression du Parcours 1). ``explicit_token`` : ``PATH``/``LANG`` + ``HOME`` =
    ``isolated_home`` (répertoire propre) + ``CLAUDE_CODE_OAUTH_TOKEN`` = ``oauth_token`` ; **aucun** ``USER``/
    ``LOGNAME``, **aucun** ``HOME`` personnel. Lève si le mode cible est demandé sans ``isolated_home`` **et**
    ``oauth_token`` (on ne fabrique jamais une auth silencieuse)."""
    if auth_mode not in AUTH_MODES:
        raise ValueError(f"auth_mode inconnu : {auth_mode!r} (attendu ∈ {AUTH_MODES})")
    env: Dict[str, str] = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"), "LANG": "C.UTF-8"}
    if auth_mode == AUTH_KEYCHAIN_HOME:
        # B1 — barreau prouvé suffisant ; surface d'identité présente (leaks_identity=True), assumée jusqu'au PASS cible.
        for k in ("HOME", "USER", "LOGNAME"):
            if os.environ.get(k):
                env[k] = os.environ[k]
        return env
    # AUTH_EXPLICIT_TOKEN — cible : HOME isolé + jeton explicite, aucune surface personnelle.
    if not isolated_home or not oauth_token:
        raise ValueError("auth explicit_token exige isolated_home ET oauth_token (aucune auth fabriquée)")
    env["HOME"] = str(isolated_home)
    env[OAUTH_TOKEN_VAR] = str(oauth_token)
    return env


def auth_channel(auth_mode: str = AUTH_KEYCHAIN_HOME) -> Dict[str, Any]:
    """**Déclaration** du canal d'auth (pour le contrat d'adaptateur, T2). ``leaks_identity`` reflète la surface
    d'identité **structurellement exposée** au fournisseur — c'est une propriété de conception, la preuve empirique
    revient à la sonde (Q1)."""
    if auth_mode == AUTH_KEYCHAIN_HOME:
        return {"kind": AUTH_KEYCHAIN_HOME, "explicit": False, "leaks_identity": True,
                "detail": "trousseau via HOME (~/.claude.json lisible) — barreau B1"}
    return {"kind": AUTH_EXPLICIT_TOKEN, "explicit": True, "leaks_identity": False,
            "detail": "HOME isolé + jeton explicite (CLAUDE_CODE_OAUTH_TOKEN), aucune surface personnelle"}


def inbound_channels(auth_mode: str = AUTH_KEYCHAIN_HOME) -> List[Dict[str, Any]]:
    """**Déclaration** de tout ce que le runtime peut injecter dans le contexte du modèle (RV-2 étendue) : clés
    d'environnement transmises, fichiers de configuration de session lus par le fournisseur, ``cwd``, ``argv``.
    Ne porte **jamais** la Pursuit entière (I9)."""
    channels: List[Dict[str, Any]] = [
        {"channel": "argv", "carries": "prompt (mission bornée), flags", "pursuit_scoped": True},
        {"channel": "cwd", "carries": "workspace confiné de la Pursuit", "pursuit_scoped": True},
    ]
    if auth_mode == AUTH_KEYCHAIN_HOME:
        channels.append({"channel": "env:HOME/USER/LOGNAME", "carries": "surface d'identité opérateur",
                         "pursuit_scoped": False, "identity_surface": True})
        channels.append({"channel": "file:~/.claude.json", "carries": "oauthAccount (email/identité)",
                         "pursuit_scoped": False, "identity_surface": True,
                         "note": "lu par le binaire fournisseur, hors flux capturé (RV-1 ne le voit pas)"})
    else:
        channels.append({"channel": "env:HOME(isolé)+CLAUDE_CODE_OAUTH_TOKEN", "carries": "jeton d'auth explicite",
                         "pursuit_scoped": False, "identity_surface": False,
                         "note": "HOME isolé sans ~/.claude.json personnel — à prouver par la sonde"})
    return channels


__all__ = ["AUTH_KEYCHAIN_HOME", "AUTH_EXPLICIT_TOKEN", "AUTH_MODES", "OAUTH_TOKEN_VAR",
           "confined_env", "auth_channel", "inbound_channels"]
