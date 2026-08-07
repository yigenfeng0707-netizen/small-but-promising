"""用 Playwright 复用 Chrome 登录态，打开魔搭创空间页面，查找并点击部署/重启按钮。

借鉴 browser-login-reuse Skill：真实 profile + Junction 方式。
"""
import subprocess
import os
import time
import asyncio
from playwright.async_api import async_playwright

OWNER = "gsym236998"
NAME = "home-chem-safety-agent"
STUDIO_URL = f"https://www.modelscope.cn/studios/{OWNER}/{NAME}/summary"


async def main():
    # 0. 关闭 Chrome（释放 profile 锁）
    print("关闭 Chrome...")
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
    await asyncio.sleep(2)

    # 1. 真实 profile（魔搭 SSO 需完整 session）
    real_ud = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")

    async with async_playwright() as p:
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=real_ud,
                channel="chrome",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1440, "height": 900},
            )
        except Exception as e:
            print(f"启动失败: {e}")
            return

        page = await context.new_page()

        # 2. 访问创空间页面
        print(f"访问: {STUDIO_URL}")
        await page.goto(STUDIO_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        final_url = page.url
        title = await page.title()
        print(f"URL: {final_url}")
        print(f"标题: {title}")

        # 3. 登录态验证
        if any(k in final_url.lower() for k in ["login", "signin"]):
            print("❌ 未登录，请先在 Chrome 中登录魔搭")
            await page.screenshot(path="_studio_login_required.png")
            await context.close()
            return

        # 4. 截图看页面状态
        await page.screenshot(path="_studio_page.png", full_page=True)
        print("截图: _studio_page.png")

        # 5. 查找所有按钮和可点击元素
        buttons = await page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button, a, [role="button"], .ant-btn');
                return Array.from(btns).map(b => ({
                    text: (b.innerText || b.textContent || '').trim(),
                    class: b.className,
                    href: b.href || '',
                })).filter(b => b.text.length > 0 && b.text.length < 50);
            }
        """)
        print(f"\n找到 {len(buttons)} 个按钮/链接:")
        for b in buttons[:30]:
            print(f"  - {b['text'][:40]} | class: {b['class'][:50]}")

        # 6. 查找部署/重启相关按钮
        keywords = ["部署", "重启", "启动", "运行", "发布", "刷新", "Deploy", "Restart", "Run", "Publish", "深度"]
        deploy_btn = None
        for b in buttons:
            for kw in keywords:
                if kw in b["text"]:
                    deploy_btn = b
                    print(f"\n🎯 找到按钮: '{b['text']}' (class: {b['class'][:80]})")
                    break
            if deploy_btn:
                break

        # 7. 点击部署按钮
        if deploy_btn:
            try:
                # 用文本定位并点击
                btn_element = page.get_by_text(deploy_btn["text"], exact=False).first
                await btn_element.click(timeout=10000)
                print(f"✅ 已点击 '{deploy_btn['text']}'")
                await asyncio.sleep(5)
                await page.screenshot(path="_studio_after_click.png", full_page=True)
                print("点击后截图: _studio_after_click.png")
            except Exception as e:
                print(f"点击失败: {e}")
        else:
            print("\n❌ 未找到部署/重启按钮")
            # 尝试查找设置页面
            setting_url = f"https://www.modelscope.cn/studios/{OWNER}/{NAME}/setting"
            print(f"尝试访问设置页: {setting_url}")
            await page.goto(setting_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            await page.screenshot(path="_studio_setting.png", full_page=True)
            print("设置页截图: _studio_setting.png")

            # 再次查找按钮
            buttons2 = await page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, a, [role="button"], .ant-btn');
                    return Array.from(btns).map(b => ({
                        text: (b.innerText || b.textContent || '').trim(),
                        class: b.className,
                    })).filter(b => b.text.length > 0 && b.text.length < 50);
                }
            """)
            print(f"\n设置页找到 {len(buttons2)} 个按钮:")
            for b in buttons2[:20]:
                print(f"  - {b['text'][:40]} | class: {b['class'][:50]}")

        await context.close()


asyncio.run(main())
