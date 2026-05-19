"""
ドキュメント用スクリーンショットを自動撮影する。

前提: bridge が localhost:14733 で動いていること。
出力: docs/screenshots/*.png
"""
import asyncio
import time
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'screenshots'
OUT.mkdir(parents=True, exist_ok=True)

BRIDGE = 'http://localhost:14733'

DESKTOP = {'width': 1280, 'height': 900}
WIDE = {'width': 1280, 'height': 1400}    # 縦長: 詳細設定展開時など
NARROW = {'width': 720, 'height': 900}    # 端末風


async def shot(page, name: str, full_page=False):
    path = OUT / f'{name}.png'
    await page.screenshot(path=str(path), full_page=full_page)
    print(f'  OK {path.name}')
    return path


async def wait_connected(page, timeout=10000):
    """ヘッダーの接続ステータスが緑（ok）になるまで待つ"""
    await page.wait_for_selector('.status-chip.ok', timeout=timeout)


async def accept_beta_consent(page):
    """ベータ同意ダイアログをチェック→同意"""
    await page.click('#betaConsentCheck')
    await page.click('#betaConsentBtn')
    await page.wait_for_function(
        "document.getElementById('betaConsentOverlay').style.display === 'none'",
        timeout=3000,
    )


async def clear_beta_consent(page):
    """同意フラグをクリアしてダイアログを再表示できるようにする"""
    await page.evaluate("localStorage.removeItem('betaConsent'); localStorage.removeItem('betaConsentAt')")


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(
            viewport=DESKTOP,
            locale='ja-JP',
            timezone_id='Asia/Tokyo',
        )
        page = await context.new_page()

        # ─── ① 未接続状態（bridge にアクセスできない想定）─────────────
        print('① 未接続状態')
        await page.goto('about:blank')
        # bridge は動いているので、わざと存在しないポート（14999）に向ける小細工
        # → BRIDGE 定数を書き換えても location.origin の判定で戻るので
        # 代わりに、HTML を直接読んで JS の検出を握りつぶす
        # 実装上、checkBridge が常時 polling なので「最初の1秒」だけが未接続
        # → 簡単に取れないので、別アプローチ: HTML ファイルを直接開く
        index_html = ROOT / 'docs' / 'index.html'
        await page.goto(f'file:///{str(index_html).replace(chr(92), "/")}')
        await page.wait_for_timeout(2000)
        await shot(page, '00-disconnected')

        # ─── ② ベータ同意ダイアログ（接続済み）──────────────────────
        print('② ベータ同意ダイアログ')
        await page.goto(BRIDGE)
        # localStorage に同意フラグが残っているとダイアログが出ないので必ずクリア
        await page.evaluate("localStorage.clear()")
        await page.reload()
        await wait_connected(page)
        await page.wait_for_selector('#betaConsentOverlay', state='visible', timeout=5000)
        await page.wait_for_timeout(800)
        await shot(page, '01-beta-consent-dialog')

        # ─── ③ メインUI（同意後・カード選択前）──────────────────────
        print('③ メインUI - カード選択画面')
        await accept_beta_consent(page)
        await page.wait_for_timeout(500)
        await shot(page, '05-main-ui')

        # ─── ④ 詳細設定を開いた状態 ───────────────────────────────
        print('④ 詳細設定を開いた状態')
        await page.set_viewport_size(WIDE)
        await page.click('#advToggle')
        await page.wait_for_timeout(500)
        await shot(page, '06-advanced-settings', full_page=True)

        # ─── ⑤ DLL カスタム入力を開いた状態 ───────────────────────
        print('⑤ DLL カスタム入力')
        await page.set_viewport_size(DESKTOP)
        await page.click('#advToggle')   # 詳細設定を閉じる
        await page.wait_for_timeout(200)
        await page.click('#dllToggle')
        await page.wait_for_timeout(300)
        await shot(page, '07-custom-dll-input')

        # ─── ⑥ セキュリティ説明ページ ──────────────────────────────
        print('⑥ セキュリティ説明ページ')
        await page.set_viewport_size(WIDE)
        await page.goto(f'{BRIDGE}/security')
        await page.wait_for_load_state('networkidle')
        await shot(page, '20-security-page', full_page=True)

        # ─── ⑦ セットアップウィザード - ようこそ ──────────────────
        print('⑦ セットアップ - ようこそ')
        await page.set_viewport_size(DESKTOP)
        await page.goto(f'{BRIDGE}/setup')
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(1500)
        await shot(page, '10-setup-welcome')

        # ─── ⑧ セットアップ - 環境確認 ───────────────────────────
        print('⑧ セットアップ - 環境確認')
        # 「次へ」を押してステップ1へ
        try:
            await page.click('button.btn-primary:has-text("次へ")')
            await page.wait_for_timeout(3000)   # 環境チェック処理を待つ
            await shot(page, '11-setup-environment', full_page=True)
        except Exception as e:
            print(f'    setup step1 skip: {e}')

        # ─── ⑨ 完了画面のモック（JS でDOM直接操作）───────────────
        print('⑨ 完了画面のモック')
        await page.goto(BRIDGE)
        await page.evaluate("localStorage.setItem('betaConsent', 'v1')")   # スキップ
        await page.reload()
        await wait_connected(page)
        await page.evaluate("""
            // 完了カードを表示状態にする
            S.files = new Array(4).fill(null);
            document.getElementById('mainForm').classList.add('hidden');
            const card = document.getElementById('doneCard');
            card.classList.add('show');
            document.getElementById('doneEmoji').textContent = '✅';
            document.getElementById('doneTitle').textContent = '署名が完了しました!';
            const now = new Date();
            document.getElementById('doneSub').textContent =
              now.toLocaleDateString('ja-JP', {year:'numeric',month:'long',day:'numeric',hour:'2-digit',minute:'2-digit'});
            document.getElementById('doneNum').textContent = '4';
        """)
        await page.wait_for_timeout(500)
        await shot(page, '30-done-success')

        # ─── ⑩ エラー画面のモック ─────────────────────────────────
        print('⑩ エラー画面のモック')
        await page.evaluate("""
            const errArea = document.getElementById('doneErrArea');
            const box = document.createElement('div');
            box.className = 'done-errs';
            box.innerHTML = '<div class="done-errs-title">⚠️ エラーが発生したファイル（1件）</div>';
            const it = document.createElement('div');
            it.className = 'err-item';
            it.textContent = '記録_20260519_山田さん.pdf: ❌ PINが違います。HPKIカードのPINを確認してください。';
            box.appendChild(it);
            errArea.appendChild(box);
            document.getElementById('doneEmoji').textContent = '⚠️';
            document.getElementById('doneTitle').textContent = '一部の署名に失敗しました';
            document.getElementById('doneNum').textContent = '3';
        """)
        await page.wait_for_timeout(300)
        await shot(page, '31-done-with-error')

        # ─── ⑪ 処理中画面のモック ─────────────────────────────────
        print('⑪ 処理中画面のモック')
        await page.evaluate("""
            // リセットしてオーバーレイ表示
            document.getElementById('doneCard').classList.remove('show');
            document.getElementById('mainForm').classList.remove('hidden');
            const ov = document.getElementById('signingOverlay');
            ov.classList.add('show');
            document.getElementById('signingFile').textContent = '記録_20260519_山田さん.pdf  2 / 4件';
            document.getElementById('signingBar').style.width = '50%';
        """)
        await page.wait_for_timeout(500)
        await shot(page, '40-signing-progress')

        # ─── ⑫ モバイル幅でのメインUI ─────────────────────────────
        print('⑫ モバイル幅メインUI')
        await page.set_viewport_size(NARROW)
        await page.goto(BRIDGE)
        await page.evaluate("localStorage.setItem('betaConsent', 'v1')")
        await page.reload()
        await wait_connected(page)
        await page.wait_for_timeout(500)
        await shot(page, '50-mobile-main-ui')

        await context.close()
        await browser.close()

        print(f'\n📁 {len(list(OUT.glob("*.png")))} 件のスクリーンショットを {OUT} に保存しました')


if __name__ == '__main__':
    asyncio.run(main())
