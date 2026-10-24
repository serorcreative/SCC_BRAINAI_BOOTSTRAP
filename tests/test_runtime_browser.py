"""Recette Chromium opt-in : BRAINAI_UI_BROWSER_TEST=1, Playwright + Chromium requis."""
import os
import subprocess
from pathlib import Path

import pytest

from test_runtime_interface import runtime, live_server


@pytest.mark.skipif(os.environ.get('BRAINAI_UI_BROWSER_TEST') != '1', reason='recette navigateur opt-in (Playwright/Chromium)')
def test_complete_browser_journey(runtime, monkeypatch, tmp_path):
    from scc_brainai_bootstrap.builder.local_site import LocalDeterministicSiteAdapter
    original = LocalDeterministicSiteAdapter.build
    def controlled_failure(self, spec, *, cwd, budget_remaining_usd):
        raw = original(self, spec, cwd=cwd, budget_remaining_usd=budget_remaining_usd)
        if 'échec' in spec['product_objective']:
            (Path(cwd) / 'index.html').write_text('<html><body>sans titre</body></html>')
        return raw
    monkeypatch.setattr(LocalDeterministicSiteAdapter, 'build', controlled_failure)
    post, _ = runtime
    env = os.environ.copy()
    env['BRAINAI_TEST_URL'] = post.url + '/?t=' + post.token
    captures = Path(os.environ.get('BRAINAI_UI_ARTIFACTS', str(tmp_path)))
    captures.mkdir(parents=True, exist_ok=True)
    env['BRAINAI_TEST_SCREENSHOT'] = str(captures / 'runtime-ui.png')
    run = subprocess.run(['node', str(Path(__file__).with_name('runtime_browser.cjs'))],
                         env=env, text=True, capture_output=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    print(run.stdout)
