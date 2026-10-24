// Aucun fournisseur distant : le serveur de recette injecte ses fakes cognitives.
const assert = require('node:assert/strict');
const {chromium} = require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES ?
  process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES + '/playwright' : 'playwright');
(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.BRAINAI_CHROMIUM || undefined, args:['--no-sandbox']});
  const page = await browser.newPage({viewport:{width:1280,height:1000}});
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  try {
    await page.goto(process.env.BRAINAI_TEST_URL);
    await page.selectOption('#mode-select','real');
    await page.selectOption('#builder','deterministic_local');
    async function message(text) {
      await page.fill('#need', text); await page.click('#send');
      await page.waitForFunction(() => !document.querySelector('main').inert);
    }
    async function prepare() {
      await page.click('#realize-btn');
      await page.waitForSelector('#gate-panel:not([hidden])');
      assert.equal(await page.isDisabled('#deliver-btn'), true);
    }
    async function approve() {
      await page.click('#approve-btn');
      await page.waitForFunction(() => !document.querySelector('main').inert);
    }
    await message('Un site pour un refuge'); await message('Une page statique');
    await prepare(); await approve(); await page.click('#deliver-btn');
    await page.waitForFunction(() => document.querySelector('#delivery-status').textContent.includes('Livraison vérifiée'));
    const first = JSON.parse(await page.textContent('#delivery-content'));
    assert.equal(first.test_result.status,'passed'); assert.ok(first.memory_11_id);
    await page.click('#new-btn');
    await message('Un second site'); await message('échec contrôlé');
    await prepare(); await approve(); await page.click('#deliver-btn');
    await page.waitForFunction(() => document.querySelector('#delivery-status').textContent.includes('non aboutie'));
    const failed = JSON.parse(await page.textContent('#delivery-content'));
    assert.equal(failed.test_result.status,'failed'); assert.equal(failed.delivered, undefined);
    await page.fill('#correction-text','Ajouter un titre'); await page.click('#propose-correction-btn');
    await page.waitForFunction(() => document.querySelector('#correction-status').textContent.includes('consignée'));
    await message('Page corrigée avec titre'); await prepare(); await approve();
    assert.equal(await page.isHidden('#execute-correction-btn'), true);
    await page.click('#approve-correction-btn'); await page.click('#execute-correction-btn');
    await page.waitForFunction(() => document.querySelector('#delivery-status').textContent.includes('Livraison vérifiée'));
    const fixed = JSON.parse(await page.textContent('#delivery-content'));
    assert.equal(fixed.provenance.parent_run_ref, failed.provenance.run_id);
    assert.equal(fixed.test_result.status,'passed');
    const ref = await page.textContent('#p-id');
    await page.reload(); await page.fill('#resume-id',ref); await page.click('#resume-btn');
    await page.waitForFunction(() => document.querySelector('#conv').textContent.includes('Contexte relu'));
    assert.equal(await page.isVisible('#gate-panel'),false);
    assert.equal(await page.isVisible('#execute-correction-btn'),false);
    await page.click('#learning-btn');
    await page.waitForFunction(() => document.querySelector('#learning-status').textContent.includes('aucune application automatique'));
    const learning = JSON.parse(await page.textContent('#learning-content'));
    assert.equal(learning.preuves.length,2); assert.ok(learning.recommandations.length);
    assert.deepEqual(errors,[]);
    if (process.env.BRAINAI_TEST_SCREENSHOT) {
      await page.screenshot({path:process.env.BRAINAI_TEST_SCREENSHOT,fullPage:true});
      await page.setViewportSize({width:390,height:844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
      await page.screenshot({path:process.env.BRAINAI_TEST_SCREENSHOT.replace('.png','-mobile.png'),fullPage:true});
    }
    console.log('BROWSER_E2E_OK success failure correction reload recall learning; no JS errors');
  } catch (error) {
    if (process.env.BRAINAI_TEST_SCREENSHOT) {
      await page.screenshot({path:process.env.BRAINAI_TEST_SCREENSHOT.replace('.png','-failure.png'),fullPage:true}).catch(() => {});
    }
    throw error;
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exit(1)});
