"""
v1.1.7 が動いているローカルブリッジに対して、UI スモークテスト。
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

BRIDGE = 'http://localhost:14733'
OUT = Path(__file__).resolve().parent.parent / 'docs' / 'screenshots'


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})

        print('--- /api/health ---')
        await page.goto(f'{BRIDGE}/api/health')
        body = await page.text_content('body')
        print(body[:300])
        assert '"version":"1.1.7"' in body, f'v1.1.7 ではない: {body[:100]}'
        assert '"mockMode":false' in body, 'mockMode が True'
        print('  OK version=1.1.7, mock=False')

        print('--- /api/diagnostics ---')
        await page.goto(f'{BRIDGE}/api/diagnostics')
        diag = await page.text_content('body')
        assert '"pin"' not in diag.lower() or '[REDACTED]' in diag, 'diagnostics に PIN らしき文字列'
        assert '1.1.7' in diag, 'バージョンが含まれない'
        print('  OK バージョン記録、PIN なし')

        print('--- メイン UI ---')
        await page.goto(BRIDGE)
        # consent をスキップ
        await page.evaluate("localStorage.setItem('betaConsent', 'v1')")
        await page.reload()
        await page.wait_for_selector('.status-chip.ok', timeout=10000)
        print('  OK status-chip.ok (準備できています)')

        # 「カードリーダーが見つかりません」が出ないか
        body_text = await page.text_content('body')
        if 'カードドライバー' in body_text:
            print('  WARN: カードドライバー検出失敗の表示があるかも')

        # version 表示確認
        ver = await page.text_content('#versionLabel')
        print(f'  versionLabel: {ver}')
        assert '1.1.7' in ver, f'UI のバージョン表示が違う: {ver}'

        # 撮影
        await page.screenshot(path=str(OUT / '_smoke_v117.png'))
        print('  smoke screenshot saved')

        await browser.close()
        print('\n全 UI スモーク OK')


if __name__ == '__main__':
    asyncio.run(main())
