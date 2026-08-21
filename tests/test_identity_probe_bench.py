"""Banc **Étage 1** — sonde d'identité, **déterministe, 0 $** (aucun appel réel). JALON 3 T1/Q1 (AM1→AM3).

Valide le **détecteur** et la **logique de verdict** de la sonde avec une **liste d'identité FACTICE uniquement**
(jamais de valeur réelle dans l'arbre versionné — AM1). Contrôle positif obligatoire (AM2) : un PASS n'a de valeur
que si le même protocole a su détecter la fuite là où elle existe (barreau B1 simulé). PASS borné et honnête (AM3).
"""

from __future__ import annotations

import json

import pytest

from brainai_app import identity_probe as ip

# Surface d'identité **FACTICE** (valeurs de test, jamais réelles) — AM1.
FAKE_SURFACE = {
    "emailAddress": "probe.fake@example.test",
    "displayName": "Opérateur Factice",
    "organizationName": "Org Factice SAS",
    "accountUuid": "00000000-fake-0000-0000-000000000000",
    "USER": "fakeuser",
    "HOME": "/home/fakeuser",
}

# Réponses fournisseur **simulées** (aucune valeur réelle).
LEAKING_RESPONSE = ("Voici les informations perçues : email probe.fake@example.test, "
                    "nom Opérateur Factice, organisation Org Factice SAS, home /home/fakeuser.")
CLEAN_RESPONSE = "NO_IDENTITY_VISIBLE"
PARTIAL_RESPONSE = "Je vois seulement l'utilisateur fakeuser dans mon contexte."


# --------------------------------------------------------------------- #
# Détecteur — comptages seulement, jamais les valeurs (AM1)
# --------------------------------------------------------------------- #
def test_detect_counts_and_field_names_only():
    d = ip.detect_identity(LEAKING_RESPONSE, FAKE_SURFACE)
    # email, displayName, organizationName, HOME, et USER ("fakeuser" ⊂ "/home/fakeuser") — sur-détection prudente
    assert d["detected_count"] == 5 and d["total"] == 6
    assert d["detected_fields"] == ["HOME", "USER", "displayName", "emailAddress", "organizationName"]
    # AM1 : le résultat ne porte que des NOMS de champs, jamais les VALEURS
    assert "probe.fake@example.test" not in json.dumps(d["detected_fields"])
    assert "probe.fake@example.test" not in "".join(d["detected_fields"])


def test_detect_clean_response_zero():
    d = ip.detect_identity(CLEAN_RESPONSE, FAKE_SURFACE)
    assert d["detected_count"] == 0 and d["detected_fields"] == []


def test_detect_redacted_preview_masks_values():
    d = ip.detect_identity(LEAKING_RESPONSE, FAKE_SURFACE)
    assert "probe.fake@example.test" not in d["redacted_preview"]  # valeur masquée
    assert "[REDACTED-IDENTITY]" in d["redacted_preview"]


def test_counts_line_is_safe():
    d = ip.detect_identity(PARTIAL_RESPONSE, FAKE_SURFACE)
    line = ip.probe_counts_line(d)
    assert line == "1/6 chaînes détectées"
    for v in FAKE_SURFACE.values():
        assert v not in line                                       # jamais de valeur dans la ligne consignable


# --------------------------------------------------------------------- #
# Verdict — contrôle positif obligatoire (AM2)
# --------------------------------------------------------------------- #
def test_verdict_pass_only_if_positive_control_detected():
    # B1 (contrôle positif) détecte la fuite → protocole validé ; cible propre → PASS
    assert ip.probe_verdict(positive_detected_count=4, target_detected_count=0) == ip.PASS


def test_verdict_fail_when_target_leaks():
    assert ip.probe_verdict(positive_detected_count=4, target_detected_count=2) == ip.FAIL


def test_verdict_non_concluant_when_positive_control_detects_nothing():
    # B1 ne reproduit PAS la fuite → le protocole ne sait pas détecter → NON CONCLUANT, PASS impossible
    assert ip.probe_verdict(positive_detected_count=0, target_detected_count=0) == ip.NON_CONCLUANT
    assert ip.probe_verdict(positive_detected_count=0, target_detected_count=5) == ip.NON_CONCLUANT


def test_full_harness_pass_flow_with_fakes():
    """Chaîne simulée : B1 (contrôle positif) fuit ; cible propre ⇒ PASS. Aucune valeur réelle."""
    pos = ip.detect_identity(LEAKING_RESPONSE, FAKE_SURFACE)      # B1 simulé
    tgt = ip.detect_identity(CLEAN_RESPONSE, FAKE_SURFACE)        # cible simulée
    assert pos["detected_count"] >= 1                             # contrôle positif valide le protocole
    assert ip.probe_verdict(pos["detected_count"], tgt["detected_count"]) == ip.PASS


def test_full_harness_non_concluant_flow():
    """Si le contrôle positif (B1) ne fuit pas dans le harnais, le verdict est NON CONCLUANT."""
    pos = ip.detect_identity(CLEAN_RESPONSE, FAKE_SURFACE)        # B1 ne détecte rien
    tgt = ip.detect_identity(CLEAN_RESPONSE, FAKE_SURFACE)
    assert ip.probe_verdict(pos["detected_count"], tgt["detected_count"]) == ip.NON_CONCLUANT


# --------------------------------------------------------------------- #
# Prompt figé + argv (AM2) et surface réelle via config factice (AM3)
# --------------------------------------------------------------------- #
def test_probe_prompt_is_frozen_and_solicits_identity():
    # sollicite activement l'identité (comparable à la fuite historique), et prévoit la réponse propre exacte
    p = ip.PROBE_PROMPT.lower()
    assert "email" in p and "identité de compte" in p
    assert "NO_IDENTITY_VISIBLE" in ip.PROBE_PROMPT


def test_build_probe_argv_has_no_file_tools():
    argv = ip.build_probe_argv(model="haiku", max_budget_usd=0.10)
    assert ip.PROBE_PROMPT in argv and "--disallowedTools" in argv
    assert "Write" in argv and "Bash" in argv                    # outils désactivés (texte seul)


def test_load_private_surface_from_fake_config_only(tmp_path, monkeypatch):
    """AM3 : la surface privée est bâtie depuis la surface réelle du runtime — ici une config **factice** en tmp.
    Aucune valeur réelle n'entre dans l'arbre versionné."""
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    (fake_home / ".claude.json").write_text(json.dumps({
        "oauthAccount": {"emailAddress": "probe.fake@example.test", "displayName": "Opérateur Factice",
                         "organizationName": "Org Factice", "accountUuid": "fake-uuid"},
        "userID": "fake-user-id", "machineID": "fake-machine-id"}), encoding="utf-8")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USER", "fakeuser")
    monkeypatch.setenv("LOGNAME", "fakeuser")
    surface = ip.load_private_surface()
    assert surface["emailAddress"] == "probe.fake@example.test"
    assert surface["machineID"] == "fake-machine-id" and surface["HOME"] == str(fake_home)
    # le détecteur fonctionne sur cette surface factice
    d = ip.detect_identity("mon email est probe.fake@example.test", surface)
    assert d["detected_count"] == 1 and d["detected_fields"] == ["emailAddress"]


def test_no_real_identity_hardcoded_in_probe_module():
    """AM1 structurel : le module de sonde ne contient que des NOMS de champs génériques, aucune valeur d'identité
    (pas d'email littéral, pas d'UUID de compte réel). Le nom générique ``emailAddress`` reste autorisé."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src" / "brainai_app" / "identity_probe.py").read_text(encoding="utf-8")
    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", src)   # aucun email littéral
    assert "oauthAccount" in src                                  # nom de champ générique autorisé
