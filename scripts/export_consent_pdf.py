"""
訪問用の印刷キット (PDF 3 種) をデスクトップに生成。
- 利用同意書
- インストールガイド
- クイックスタート (現場のご利用者様向け)
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

OUT_DIR = Path.home() / 'Desktop'
VERSION = '1.1.8'

# (URL, 出力ファイル名)
TARGETS = [
    ('https://lifemate-inc.github.io/hpki-signer/legal/consent.html',
     f'HPKI署名ツール_利用同意書_v{VERSION}.pdf'),
    ('https://lifemate-inc.github.io/hpki-signer/install-guide.html',
     f'HPKI署名ツール_インストールガイド_v{VERSION}.pdf'),
    ('https://lifemate-inc.github.io/hpki-signer/manuals/end-user/01_quick-start.html',
     f'HPKI署名ツール_クイックスタート_v{VERSION}.pdf'),
]


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        for url, fname in TARGETS:
            out = OUT_DIR / fname
            try:
                await page.goto(url, wait_until='networkidle')
                await page.wait_for_timeout(800)
                await page.pdf(
                    path=str(out),
                    format='A4',
                    print_background=True,
                    margin={'top': '20mm', 'bottom': '20mm', 'left': '18mm', 'right': '18mm'},
                )
                print(f'OK  {out.name}')
            except Exception as e:
                print(f'FAIL {fname}: {e}')
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
