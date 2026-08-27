"""L2 store-safety — SessionStore (17_BOOTSTRAP) + frontière vocabulaire memory_11_id.

Couvre le contrat L2 pour le manifeste de session et la frontière d'identité mémoire :

- concurrence par **deux vrais sous-processus** (aucun compteur perdu) ;
- verrou **intra-process** partagé par chemin canonique (RLock — cette couche seule, threads) ;
- **lock timeout** fail-closed (un tiers détient le flock du lockfile dédié) ;
- **écriture atomique** : un échec avant ``os.replace`` préserve l'ancien état, sans résidu ``.tmp`` ;
- **corruption** d'un ``session.json`` existant → fail-closed, **jamais** de reset silencieux ;
- JSON valide mais **structurellement incohérent** (sans ``session_id``) → fail-closed ;
- helper ``report_memory_ids`` (typé + alias strictement égal) ;
- **câblage réel** ``_deliver`` : ``report["memory_11_id"]`` et ``report["memory_id"]`` == ID Memory-11.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import scc_brainai_bootstrap as _pkg
from scc_brainai_bootstrap.core.config import BrainAIConfig
from scc_brainai_bootstrap.core.errors import SessionStateError
from scc_brainai_bootstrap.core.locking import LockTimeout, StoreLock
from scc_brainai_bootstrap.session import SessionStore

SRC = str(Path(_pkg.__file__).resolve().parents[1])         # .../src (importable en sous-process)


# --------------------------------------------------------------------------- concurrence 2 process

_WORKER_NOTE = """\
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[3])
from scc_brainai_bootstrap.core.config import BrainAIConfig
from scc_brainai_bootstrap.session import SessionStore
cfg = BrainAIConfig(data_dir=Path(sys.argv[1]))
store = SessionStore(cfg)
for _ in range(int(sys.argv[2])):
    store.note("runs", 1)
"""


def test_session_two_real_processes_no_lost_update(config, tmp_path):
    """Deux **vrais** sous-processus incrémentent le même compteur ; le verrou inter-process
    (flock) sérialise LOCK→RELOAD→MUTATE→WRITE : aucune mise à jour perdue."""
    store = SessionStore(config)
    seed = store.record_boot({})                            # crée la session (note() active)
    sid = seed["session_id"]

    worker = tmp_path / "worker_note.py"
    worker.write_text(_WORKER_NOTE, encoding="utf-8")
    M = 40
    procs = [subprocess.Popen([sys.executable, str(worker), str(config.data_dir), str(M), SRC])
             for _ in range(2)]
    for p in procs:
        assert p.wait(timeout=60) == 0

    final = store.summary()
    assert final["totals"]["runs"] == 2 * M                 # 80, aucun perdu
    assert final["session_id"] == sid                       # identité stable


# --------------------------------------------------------------------------- verrou intra-process

def test_session_intra_process_lock_shared_by_canonical_path(config):
    """Deux ``StoreLock`` visant le même lockfile partagent la MÊME entrée (RLock) ; des threads
    passant par des instances ``SessionStore`` distinctes n'écrasent aucun incrément."""
    config.ensure_directories()
    lock_path = config.data_dir / "session.lock"
    a = StoreLock(lock_path)
    b = StoreLock(lock_path)
    assert a._entry is b._entry                             # partage par chemin canonique (pas un lock/instance)

    SessionStore(config).record_boot({})                   # seed session
    T, K = 4, 25
    errors = []

    def worker():
        try:
            s = SessionStore(config)                        # instance distincte, même data_dir
            for _ in range(K):
                s.note("runs", 1)
        except BaseException as exc:                        # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(T)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors
    assert SessionStore(config).summary()["totals"]["runs"] == T * K   # 100, sérialisé


def test_session_canonical_key_stable_across_symlink_and_parent_creation(tmp_path):
    """Invariant §5 niveau-1 : la clé canonique (donc le RLock partagé) est STABLE quelle que soit
    l'existence préalable du parent et à travers un symlink/alias. Régression du défaut où ``_canonical``
    gardait le chemin BRUT quand le parent n'existait pas encore (clés distinctes -> RLock distincts ->
    la réentrance ``with a: with b:`` ouvrait un 2e fd et un ``flock`` sur le même inode -> self-deadlock)."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    lp_link = link / "sub" / "session.lock"
    lp_real = real / "sub" / "session.lock"

    # 1. Construire AVANT existence du parent (link vs real distincts en chemin brut).
    a = StoreLock(lp_link, timeout=2.0)
    b = StoreLock(lp_real, timeout=2.0)
    assert a.canonical == b.canonical                       # résolution inconditionnelle non-stricte
    assert a._entry is b._entry                             # MÊME RLock partagé (invariant §5 niveau-1)

    # 2. Créer explicitement le parent, sans passer par StoreLock.
    (real / "sub").mkdir(parents=True)

    # 3. Construire APRÈS création : même clé, même entrée de registre.
    c = StoreLock(lp_real, timeout=2.0)
    assert c.canonical == a.canonical
    assert c._entry is a._entry

    # 4. Réentrance à travers la divergence : partage du fd (depth), aucun self-deadlock.
    with a:
        with b:
            pass


# --------------------------------------------------------------------------- lock timeout fail-closed

_WORKER_HOLD = """\
import sys, os, fcntl, time
from pathlib import Path
fd = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
Path(sys.argv[3]).write_text("ready")
time.sleep(float(sys.argv[2]))
"""


def test_session_lock_timeout_fail_closed(config, tmp_path):
    """Un tiers détient le flock du lockfile dédié : toute mutation borne son attente et
    échoue par :class:`LockTimeout` (fail-closed, jamais d'attente infinie ni d'écriture)."""
    config.ensure_directories()
    lock_path = config.data_dir / "session.lock"
    ready = tmp_path / "ready.flag"
    holder = tmp_path / "worker_hold.py"
    holder.write_text(_WORKER_HOLD, encoding="utf-8")

    proc = subprocess.Popen([sys.executable, str(holder), str(lock_path), "5.0", str(ready)])
    try:
        deadline = time.monotonic() + 15
        while not ready.exists():
            assert time.monotonic() < deadline, "le détenteur du verrou n'a jamais signalé 'ready'"
            assert proc.poll() is None, "le détenteur s'est arrêté prématurément"
            time.sleep(0.02)

        store = SessionStore(config, lock_timeout=0.4)
        t0 = time.monotonic()
        with pytest.raises(LockTimeout):
            store.record_boot({})
        assert time.monotonic() - t0 < 4.0                  # a bien renoncé (borné), pas attendu 5s
    finally:
        proc.wait(timeout=15)


# --------------------------------------------------------------------------- atomic-write failure

def test_session_atomic_write_failure_preserves_old_and_no_residual(config, monkeypatch):
    """Un échec **avant** ``os.replace`` laisse l'ancien ``session.json`` intact et ne laisse
    aucun fichier temporaire résiduel."""
    store = SessionStore(config)
    store.record_boot({})                                   # état valide (boots == 1)
    before = store.path.read_bytes()

    def boom(src, dst):
        raise OSError("crash simulé avant os.replace")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.record_boot({})                               # load ok, mutate, save -> replace explose

    assert store.path.read_bytes() == before                # ancien contenu complet préservé
    residuals = list(config.data_dir.glob("session.json.*.tmp"))
    assert residuals == []                                  # temp nettoyé (finally)


# --------------------------------------------------------------------------- corruption fail-closed

def test_session_corrupt_existing_file_fail_closed_no_reset(config):
    """Un ``session.json`` existant mais corrompu (JSON invalide) est **fail-closed** partout :
    aucune mutation, aucun reset silencieux de l'identité/compteurs."""
    store = SessionStore(config)
    store.record_boot({})                                   # session valide d'abord
    store.path.write_text("{ ceci n'est pas du JSON valide", encoding="utf-8")
    before = store.path.read_bytes()

    with pytest.raises(SessionStateError):
        store.record_boot({})
    with pytest.raises(SessionStateError):
        store.note("runs", 1)
    with pytest.raises(SessionStateError):
        store.summary()                                     # ne présente JAMAIS "aucune session"

    assert store.path.read_bytes() == before                # jamais réinitialisé


def test_session_valid_json_without_session_id_fail_closed(config):
    """JSON valide mais structurellement incohérent (objet sans ``session_id`` non vide) →
    fail-closed, sans reset."""
    store = SessionStore(config)
    config.ensure_directories()
    store.path.write_text(json.dumps({"boots": 3, "totals": {"runs": 7}}), encoding="utf-8")
    before = store.path.read_bytes()

    with pytest.raises(SessionStateError):
        store.record_boot({})
    assert store.path.read_bytes() == before


# --------------------------------------------------------------------------- frontière memory_11_id

def test_report_memory_ids_typed_and_alias():
    """Le helper expose l'ID canonique sous ``memory_11_id`` et ``memory_id`` comme alias strictement égal."""
    from brainai_app.delivery.memory import report_memory_ids

    class _Entry:
        id = "mem_00000000002a"

    out = report_memory_ids(_Entry())
    assert out == {"memory_11_id": "mem_00000000002a", "memory_id": "mem_00000000002a"}


def test_deliver_exposes_memory_11_id_and_alias(tmp_path, monkeypatch):
    """Câblage **réel** de la composition : le vrai bloc ``_deliver`` (statut ``delivered``) publie
    ``report["memory_11_id"]`` et ``report["memory_id"]``, tous deux == l'ID retourné par Memory-11.
    Seuls le build lourd et les stores sont stubbés (intégration minimale par monkeypatch)."""
    from brainai_app import composition, providers

    class _Entry:
        id = "mem_00000000002a"

    class _Outcome:
        pursuit_id = "pursuit_x"
        as_of = "2026-07-06T00:00:00+00:00"

    monkeypatch.setattr(composition, "_spec_fact_for",
                        lambda stores, outcome: {"specification": {"product_objective": "obj"}})
    monkeypatch.setattr(providers, "real_delivery",
                        lambda: type("Caps", (), {"site_build": None, "preview": None})())
    monkeypatch.setattr(composition, "run_delivery",
                        lambda **kw: {"status": "delivered", "build": {"artefact": "a"},
                                      "preview_ref": "p", "provenance": {}})
    monkeypatch.setattr(composition, "open_memory_store", lambda *a, **k: object())
    monkeypatch.setattr(composition, "write_delivery_memory", lambda *a, **k: _Entry())

    report = composition._deliver(tmp_path, _Outcome(), actor=None, budget_usd=2.0)

    assert report["memory_11_id"] == "mem_00000000002a"     # ID canonique Memory-11
    assert report["memory_id"] == report["memory_11_id"]    # alias strictement égal
