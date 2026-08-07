"""
自动配置魔搭创空间环境变量
使用 Playwright 浏览器自动化，通过 cookie 认证

运行方式:
    python _configure_ms.py

需要环境变量:
    MODELSCOPE_COOKIE - 魔搭登录 cookie
"""
import os
import sys
import time
from playwright.sync_api import sync_playwright

# Fix Windows console encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

COOKIE = os.getenv("MODELSCOPE_COOKIE", "")
STUDIO_URL = "https://www.modelscope.cn/studios/gsym236998/home-chem-safety-agent/setting"
SERVICE_URL = "https://gsym236998-home-chem-safety-agent.ms.show"

ENV_VARS = {
    "DASHSCOPE_API_KEY": "sk-ws-H.EIRDHML.1AHp.MEQCIGfD_6V_frAVyWiFA-ZWTjM7LRwmEvS731atmPSxgtZtAiAU9no7HB8nrG1DSrOY9BRLASNRShBBKQ1Meel5UAG_yQ",
    "DASHSCOPE_API_BASE": "https://llm-uarugoa0rqgduef5.cn-beijing.maas.aliyuncs.com/api/v1",
    "PORT": "7860",
    "QWEN3_MODEL": "qwen-plus",
    "QWEN_VL_MODEL": "qwen-vl-plus",
}


def parse_cookies(cookie_str: str) -> list:
    """Parse cookie string into Playwright cookie format."""
    cookies = []
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" in pair:
            name, value = pair.split("=", 1)
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".modelscope.cn",
                "path": "/"
            })
    return cookies


def main():
    if not COOKIE:
        print("[ERROR] MODELSCOPE_COOKIE not set")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # Set cookies
        cookies = parse_cookies(COOKIE)
        context.add_cookies(cookies)

        page = context.new_page()
        print(f"[INFO] Navigating to: {STUDIO_URL}")
        page.goto(STUDIO_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Check if login is required
        if "login" in page.url.lower():
            print("[ERROR] Login required - cookie may be expired")
            print("[INFO] Please update MODELSCOPE_COOKIE")
            browser.close()
            return False

        title = page.title()
        url = page.url
        print(f"[INFO] Page title: {title}")
        print(f"[INFO] Current URL: {url}")

        # Take screenshot
        page.screenshot(path="/tmp/ms_setting_page.png")
        print("[INFO] Screenshot saved: /tmp/ms_setting_page.png")

        # Look for env var configuration elements
        # ModelScope uses a dynamic form - look for common patterns
        page.wait_for_timeout(2000)

        # Try to find and click "环境变量" or "Env Vars" section
        env_keywords = ["环境变量", "Env", "配置", "Setting", "变量"]
        for kw in env_keywords:
            elem = page.locator(f"text={kw}").first
            if elem.count() > 0:
                print(f"[FOUND] '{kw}' element")
                elem.click()
                time.sleep(1)
                break

        # Try to find input fields
        inputs = page.locator("input[type=text], input:not([type]), textarea").all()
        print(f"[INFO] Found {len(inputs)} input fields")

        for i, inp in enumerate(inputs):
            attrs = {}
            for attr in ["name", "placeholder", "value", "type"]:
                val = inp.get_attribute(attr)
                if val:
                    attrs[attr] = val
            print(f"  [{i}] {attrs}")

        # Try to add env vars by clicking "添加" or "+" button
        add_selectors = [
            "button:has-text('添加')",
            "button:has-text('新增')",
            "button:has-text('Add')",
            "button:has-text('+')",
            "button:has-text('添加变量')",
        ]

        added_count = 0
        for key, value in ENV_VARS.items():
            # Try to find existing input for this key
            existing = page.locator(f"input[name='{key}'], input[placeholder*='{key}']").first
            if existing.count() > 0:
                existing.fill(value)
                print(f"[SET] {key} = {value[:20]}...")
                added_count += 1
            else:
                # Try to add new var
                for sel in add_selectors:
                    btn = page.locator(sel).first
                    if btn.count() > 0:
                        btn.click()
                        time.sleep(0.5)
                        # Find the new empty inputs
                        new_inputs = page.locator("input[type=text], input:not([type])").all()
                        for ni in new_inputs:
                            if not ni.get_attribute("value"):
                                ni.fill(key)
                                # Find next sibling input for value
                                parent = ni.locator("..")
                                val_input = parent.locator("input").last
                                val_input.fill(value)
                                print(f"[ADD] {key} = {value[:20]}...")
                                added_count += 1
                                break
                        break

        if added_count > 0:
            time.sleep(1)
            # Try to find and click save/confirm button
            save_selectors = [
                "button:has-text('保存')",
                "button:has-text('确认')",
                "button:has-text('Save')",
                "button:has-text('Submit')",
                "button:has-text('提交')",
            ]
            for sel in save_selectors:
                btn = page.locator(sel).first
                if btn.count() > 0:
                    btn.click()
                    print("[INFO] Clicked save button")
                    time.sleep(2)
                    break

            # Try to find and click restart button
            restart_selectors = [
                "button:has-text('重启')",
                "button:has-text('Restart')",
                "button:has-text('重启服务')",
            ]
            for sel in restart_selectors:
                btn = page.locator(sel).first
                if btn.count() > 0:
                    btn.click()
                    print("[INFO] Clicked restart button")
                    time.sleep(2)
                    break

        page.screenshot(path="/tmp/ms_setting_after.png")
        print("[INFO] After screenshot: /tmp/ms_setting_after.png")

        browser.close()

        if added_count == len(ENV_VARS):
            print(f"[SUCCESS] All {added_count} env vars configured!")
            return True
        elif added_count > 0:
            print(f"[PARTIAL] {added_count}/{len(ENV_VARS)} env vars configured")
            return True
        else:
            print("[WARN] Could not configure env vars automatically")
            print("[INFO] Please configure manually at:")
            print(f"       {STUDIO_URL}")
            return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
