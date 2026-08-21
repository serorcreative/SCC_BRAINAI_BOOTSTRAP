"""Banc **Étage 1** — environnement confiné & canal de re-crédentialisation, **déterministe, 0 $**.

JALON 3 **correctif** (benchmark externe + contradiction ClaudeS) : l'**isolation de HOME** est une politique
**générique** d'invocation d'un executor ; le **nom de la variable** par laquelle l'executor reçoit son jeton est
**propre à l'executor**, donc **injectable** (``token_var``). Ce banc prouve, sans aucun appel réel :

* la variable de credential est **injectable** (un executor fictif fournit la sienne sous HOME isolé, sans éditer le module) ;
* le **défaut Claude** (``CLAUDE_CODE_OAUTH_TOKEN``) reste **strictement inchangé** ;
* **B1 est strictement inchangé** (aucun jeton, surface d'identité historique) ;
* **aucune valeur de credential** n'est persistée ni exposée hors de l'``env`` retourné.

CONNECTER / RÉUTILISER / ADAPTER AVANT DE RECONSTRUIRE — aucune nouvelle architecture d'executor ici.
"""

from __future__ import annotations

import pytest

from scc_brainai_bootstrap.builder import provider_env as pe


# --------------------------------------------------------------------- #
# Défaut Claude strictement inchangé
# --------------------------------------------------------------------- #
def test_default_token_var_is_claude_unchanged():
    assert pe.OAUTH_TOKEN_VAR == "CLAUDE_CODE_OAUTH_TOKEN"


def test_target_mode_uses_claude_var_by_default():
    """Sans ``token_var`` explicite, la cible re-crédentialise via la variable Claude — comportement historique."""
    env = pe.confined_env(pe.AUTH_EXPLICIT_TOKEN, isolated_home="/tmp/isolated", oauth_token="tok-XYZ")
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-XYZ"
    assert env["HOME"] == "/tmp/isolated"
    assert "USER" not in env and "LOGNAME" not in env       # aucune surface personnelle (cible)


# --------------------------------------------------------------------- #
# B1 strictement inchangé (aucune régression du Parcours 1)
# --------------------------------------------------------------------- #
def test_b1_unchanged_no_token_identity_surface_present(monkeypatch):
    monkeypatch.setenv("HOME", "/home/realop")
    monkeypatch.setenv("USER", "realop")
    monkeypatch.setenv("LOGNAME", "realop")
    env = pe.confined_env(pe.AUTH_KEYCHAIN_HOME)
    assert env["HOME"] == "/home/realop" and env["USER"] == "realop" and env["LOGNAME"] == "realop"
    # B1 ne re-crédentialise jamais par variable de jeton : ni le défaut, ni quoi que ce soit
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in env
    assert not any(k not in ("PATH", "LANG", "HOME", "USER", "LOGNAME") for k in env)


def test_b1_ignores_token_var_param(monkeypatch):
    """Même si ``token_var`` est fourni, B1 n'injecte aucun jeton (le canal de re-crédential n'existe qu'en cible)."""
    monkeypatch.setenv("HOME", "/home/realop")
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("LOGNAME", raising=False)
    env = pe.confined_env(pe.AUTH_KEYCHAIN_HOME, token_var="MYTOOL_TOKEN")
    assert "MYTOOL_TOKEN" not in env and "CLAUDE_CODE_OAUTH_TOKEN" not in env


# --------------------------------------------------------------------- #
# Variable de credential INJECTABLE — executor fictif, sans éditer le module
# --------------------------------------------------------------------- #
def test_fictitious_executor_token_var_injectable():
    """Un executor fictif fournit son propre nom de variable sous HOME isolé — aucune édition de module requise."""
    env = pe.confined_env(pe.AUTH_EXPLICIT_TOKEN, isolated_home="/tmp/iso",
                          oauth_token="fake-tok-123", token_var="FICTIVE_EXECUTOR_TOKEN")
    assert env["FICTIVE_EXECUTOR_TOKEN"] == "fake-tok-123"   # canal propre à l'executor
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in env              # pas de fuite du défaut Claude
    assert env["HOME"] == "/tmp/iso"                         # isolation HOME générique, identique
    assert "USER" not in env and "LOGNAME" not in env


def test_empty_token_var_rejected():
    """On ne re-crédentialise jamais sans nommer le canal (aucune auth silencieuse)."""
    with pytest.raises(ValueError):
        pe.confined_env(pe.AUTH_EXPLICIT_TOKEN, isolated_home="/tmp/iso", oauth_token="t", token_var="  ")


def test_target_still_requires_isolated_home_and_token():
    """La généralisation ne relâche AUCUNE garde : cible sans HOME isolé + jeton ⇒ rejet (inchangé)."""
    with pytest.raises(ValueError):
        pe.confined_env(pe.AUTH_EXPLICIT_TOKEN, isolated_home=None, oauth_token="t", token_var="MYTOOL_TOKEN")
    with pytest.raises(ValueError):
        pe.confined_env(pe.AUTH_EXPLICIT_TOKEN, isolated_home="/tmp/iso", oauth_token=None, token_var="MYTOOL_TOKEN")


# --------------------------------------------------------------------- #
# Déclarations de canal cohérentes avec le nom injecté
# --------------------------------------------------------------------- #
def test_auth_channel_declares_injected_var():
    ch = pe.auth_channel(pe.AUTH_EXPLICIT_TOKEN, token_var="MYTOOL_TOKEN")
    assert ch["token_var"] == "MYTOOL_TOKEN" and "MYTOOL_TOKEN" in ch["detail"]
    # défaut inchangé
    assert pe.auth_channel(pe.AUTH_EXPLICIT_TOKEN)["token_var"] == "CLAUDE_CODE_OAUTH_TOKEN"


def test_b1_auth_channel_unchanged():
    ch = pe.auth_channel(pe.AUTH_KEYCHAIN_HOME)
    assert ch["kind"] == pe.AUTH_KEYCHAIN_HOME and ch["leaks_identity"] is True and ch["explicit"] is False


def test_inbound_channels_declare_injected_var():
    chans = pe.inbound_channels(pe.AUTH_EXPLICIT_TOKEN, token_var="MYTOOL_TOKEN")
    joined = " ".join(c["channel"] for c in chans)
    assert "MYTOOL_TOKEN" in joined
    # défaut inchangé
    assert any("CLAUDE_CODE_OAUTH_TOKEN" in c["channel"] for c in pe.inbound_channels(pe.AUTH_EXPLICIT_TOKEN))


# --------------------------------------------------------------------- #
# Aucune valeur de credential persistée / exposée (AM1 dans l'esprit)
# --------------------------------------------------------------------- #
def test_no_credential_value_persisted_in_module_source():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src" / "scc_brainai_bootstrap" / "builder"
           / "provider_env.py").read_text(encoding="utf-8")
    # le module ne contient QUE des NOMS de variables, jamais une valeur de jeton
    assert "fake-tok" not in src and "tok-XYZ" not in src
    assert "CLAUDE_CODE_OAUTH_TOKEN" in src                  # nom de variable (défaut) autorisé


def test_token_value_lives_only_in_returned_env():
    env = pe.confined_env(pe.AUTH_EXPLICIT_TOKEN, isolated_home="/tmp/iso",
                          oauth_token="secret-value", token_var="MYTOOL_TOKEN")
    # la valeur n'existe que dans l'env retourné ; la fonction n'écrit ni ne journalise rien
    assert env["MYTOOL_TOKEN"] == "secret-value"
    assert list(env.keys()) == ["PATH", "LANG", "HOME", "MYTOOL_TOKEN"]   # surface minimale, rien d'autre
