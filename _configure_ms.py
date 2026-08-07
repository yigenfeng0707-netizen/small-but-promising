"""
自动配置魔搭创空间环境变量 - 改进版
更健壮的页面交互逻辑
"""
import os
import sys
import time
from playwright.sync_api import sync_playwright

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

COOKIE = os.getenv("MODELSCOPE_COOKIE", "")
STUDIO_URL = "https://www.modelscope.cn/studios/gsym236998/home-chem-safety-agent/setting"
SCREENSHOT_DIR = "/tmp"

ENV_VARS = {
    "DASHSCOPE_API_KEY": "sk-ws-H.EIRDHML.1AHp.MEQCIGfD_6V_frAVyWiFA-ZWTjM7LRwmEvS731atmPSxgtZtAiAU9no7HB8nrG1DSrOY9BRLASNRShBBKQ1Meel5UAG_yQ",
    "DASHSCOPE_API_BASE": "https://llm-uarugoa0rqgduef5.cn-beijing.maas.aliyuncs.com/api/v1",
    "PORT": "7860",
    "QWEN3_MODEL": "qwen-plus",
    "QWEN_VL_MODEL": "qwen-vl-plus",
}


def parse_cookies(cookie_str: str) -> list:
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


def wait_and_click(page, selectors, timeout=5000):
    """Try multiple selectors and click the first one found."""
    for sel in selectors:
        try:
            elem = page.locator(sel).first
            if elem.count() > 0 and elem.is_visible():
                elem.click()
                return True
        except Exception:
            continue
    return False


def main():
    if not COOKIE:
        print("[ERROR] MODELSCOPE_COOKIE not set")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        context.add_cookies(parse_cookies(COOKIE))
        page = context.new_page()

        print(f"[INFO] Navigating to: {STUDIO_URL}")
        page.goto(STUDIO_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        if "login" in page.url.lower():
            print("[ERROR] Login required - cookie expired")
            return False

        print(f"[INFO] Title: {page.title()}")

        # Take initial screenshot
        page.screenshot(path=f"{SCREENSHOT_DIR}/ms_step1.png", full_page=True)

        # The /setting page shows minimal content - try the main studio page
        main_url = "https://www.modelscope.cn/studios/gsym236998/home-chem-safety-agent"
        print(f"[INFO] Trying main studio page: {main_url}")
        page.goto(main_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        page.screenshot(path=f"{SCREENSHOT_DIR}/ms_main.png", full_page=True)
        print(f"[INFO] Main page title: {page.title()}")

        # Debug: print all buttons
        buttons = page.locator("button").all()
        print(f"[DEBUG] Found {len(buttons)} buttons on main page:")
        for i, btn in enumerate(buttons):
            text = btn.inner_text().strip()
            cls = btn.get_attribute("class") or ""
            if text and len(text) < 50:
                print(f"  [{i}] text='{text}'")

        # Look for Settings link/button
        setting_selectors = [
            "text=Settings",
            "text=设置",
            "text=配置",
            "text=环境变量",
            "text=Env Vars",
            "a:has-text('Settings')",
            "a:has-text('设置')",
            "button:has-text('Settings')",
            "button:has-text('设置')",
        ]
        for sel in setting_selectors:
            elem = page.locator(sel).first
            if elem.count() > 0:
                print(f"[FOUND] Settings element: {sel}")
                elem.click()
                page.wait_for_timeout(2000)
                break

        page.screenshot(path=f"{SCREENSHOT_DIR}/ms_after_click.png", full_page=True)

        # Strategy 1: Look for tabs/sections and click "环境变量" or "配置"
        tab_selectors = [
            "text=环境变量",
            "text=Env Vars",
            "text=环境配置",
            "text=配置",
            "text=Setting",
            "a:has-text('环境变量')",
            "div:has-text('环境变量')",
            "span:has-text('环境变量')",
        ]
        clicked = wait_and_click(page, tab_selectors)
        if clicked:
            print("[INFO] Clicked env vars tab/section")
            page.wait_for_timeout(1000)

        # Strategy 2: Look for "添加" / "+" / "新增变量" button
        add_selectors = [
            "button:has-text('添加变量')",
            "button:has-text('添加')",
            "button:has-text('新增')",
            "button:has-text('+')",
            "a:has-text('添加')",
            "div.add-btn",
            "span.add-btn",
            "[class*='add']",
        ]

        success_count = 0
        for key, value in ENV_VARS.items():
            # Click "Add" button to add a new row
            added = wait_and_click(page, add_selectors)
            if added:
                print(f"[INFO] Clicked add button for {key}")
                page.wait_for_timeout(500)

            # Find all available inputs - look for empty ones
            all_inputs = page.locator("input").all()
            empty_inputs = [inp for inp in all_inputs if not (inp.get_attribute("value") or "").strip()]

            if len(empty_inputs) >= 2:
                # First empty input = key, second = value
                empty_inputs[0].fill(key)
                empty_inputs[1].fill(value)
                print(f"[SET] {key} = {value[:20]}...")
                success_count += 1
            elif len(empty_inputs) == 1:
                # Single input - fill and look for companion
                empty_inputs[0].fill(key)
                # Try to find a sibling input
                parent = empty_inputs[0].locator("..")
                siblings = parent.locator("input").all()
                if len(siblings) >= 2:
                    siblings[-1].fill(value)
                    print(f"[SET] {key} = {value[:20]}...")
                    success_count += 1
                else:
                    print(f"[WARN] Could not find value input for {key}")
            else:
                # No empty inputs - try to find inputs by checking all
                all_inputs = page.locator("input").all()
                # Look for the last pair of inputs
                if len(all_inputs) >= 2:
                    # Fill last two inputs
                    all_inputs[-2].fill(key)
                    all_inputs[-1].fill(value)
                    print(f"[SET] {key} = {value[:20]}...")
                    success_count += 1
                else:
                    print(f"[WARN] Not enough input fields for {key}")

        page.screenshot(path=f"{SCREENSHOT_DIR}/ms_step2.png", full_page=True)
        print(f"[INFO] Configured {success_count}/{len(ENV_VARS)} vars")

        # Save/Confirm
        save_selectors = [
            "button:has-text('保存')",
            "button:has-text('确认')",
            "button:has-text('Save')",
            "button:has-text('Submit')",
            "button:has-text('提交')",
            "button:has-text('确定')",
        ]
        saved = wait_and_click(page, save_selectors)
        if saved:
            print("[INFO] Clicked save/confirm")
            page.wait_for_timeout(2000)

        # Restart
        restart_selectors = [
            "button:has-text('重启')",
            "button:has-text('Restart')",
            "button:has-text('重启服务')",
            "button:has-text('重新启动')",
        ]
        restarted = wait_and_click(page, restart_selectors)
        if restarted:
            print("[INFO] Clicked restart")
            page.wait_for_timeout(2000)

        page.screenshot(path=f"{SCREENSHOT_DIR}/ms_step3.png")
        browser.close()

        if success_count == len(ENV_VARS):
            print(f"[SUCCESS] All env vars configured!")
            return True
        elif success_count > 0:
            print(f"[PARTIAL] {success_count}/{len(ENV_VARS)} configured")
            return True
        else:
            print("[FAILED] Could not configure automatically")
            return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
