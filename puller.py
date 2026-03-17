from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from playwright.sync_api import sync_playwright
from urllib.parse import quote
import time
from browser_utils import resolve_browser_executable

ANTIBOT_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
"""

CNBLOGS_RESULT_SELECTORS = (
    ".searchItem",
    ".search-item",
    ".searchList .searchItem",
    ".search-list .search-item",
)

def _notify(on_status, message):
    if on_status:
        on_status(message)


def _launch_browser(playwright, browser_path, headless):
    launch_kwargs = {
        "headless": headless,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    resolved_path = resolve_browser_executable(browser_path or "")
    if browser_path and not resolved_path:
        raise FileNotFoundError(f"浏览器路径不存在: {browser_path}")
    if resolved_path:
        launch_kwargs["executable_path"] = resolved_path
    return playwright.chromium.launch(**launch_kwargs)


def fetch_csdn_results(keyword, page):
    results = []
    api_url = "https://so.csdn.net/api/v3/search"
    params = {"q": keyword, "t": "blog", "p": str(page)}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        articles = resp.json().get('result_vos', []) or []
        for a in articles:
            title = a.get('title', '').replace('<em>','').replace('</em>','')
            article_url = a.get('url')
            if article_url:
                results.append({"site": "CSDN", "title": title, "url": article_url})
    except Exception as e:
        print(f"CSDN 搜索失败(page={page}): {e}")
    return results


def fetch_csdn_results_all(keyword, max_pages):
    results = []
    for page in range(1, max_pages + 1):
        results.extend(fetch_csdn_results(keyword, page))
    return results


def _cnblogs_has_results(page):
    for selector in CNBLOGS_RESULT_SELECTORS:
        if page.locator(selector).count() > 0:
            return True
    return False


def _cnblogs_is_verification_page(page):
    try:
        title = page.title()
    except Exception:
        title = ""

    if "搜索结果提示" in title:
        return True

    body_text = page.locator("body").inner_text(timeout=3000)
    keywords = ("验证码", "验证", "滑块", "请完成验证", "recaptcha")
    return any(keyword in body_text for keyword in keywords)


def _wait_for_cnblogs_results(page, on_status=None, timeout_seconds=90):
    deadline = time.time() + timeout_seconds
    verification_notified = False

    while time.time() < deadline:
        if _cnblogs_has_results(page):
            return True

        if _cnblogs_is_verification_page(page):
            if not verification_notified:
                _notify(on_status, "博客园需要验证码，请在弹出的浏览器窗口中手动完成")
                verification_notified = True
        page.wait_for_timeout(1500)

    return _cnblogs_has_results(page)


def fetch_cnblogs_results_all(keyword, max_pages, browser_path, on_status=None):
    results = []
    try:
        with sync_playwright() as p:
            browser = _launch_browser(p, browser_path, headless=False)
            pg = browser.new_page()
            pg.add_init_script(ANTIBOT_JS)
            
            for p_num in range(1, max_pages + 1):
                url = f"https://zzkx.cnblogs.com/s?w={quote(keyword)}&p={p_num}"
                pg.goto(url, wait_until="domcontentloaded", timeout=60000)
                if p_num == 1:
                    if not _wait_for_cnblogs_results(pg, on_status=on_status):
                        _notify(on_status, "博客园搜索超时，可能仍需手动完成验证码")
                        break
                else:
                    time.sleep(1)

                items = []
                for selector in CNBLOGS_RESULT_SELECTORS:
                    items = pg.query_selector_all(selector)
                    if items:
                        break
                for item in items:
                    title_el = item.query_selector("h3 a")
                    if title_el:
                        results.append({"site": "博客园", "title": title_el.inner_text(), "url": title_el.get_attribute("href")})
            browser.close()
    except Exception as e:
        print(f"博客园搜索失败: {e}")
    return results

def fetch_xz_results_all(keyword, max_pages, browser_path):
    results = []
    try:
        with sync_playwright() as p:
            browser = _launch_browser(p, browser_path, headless=False)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            pg = context.new_page()
            pg.add_init_script(ANTIBOT_JS)
            
            for p_num in range(1, max_pages + 1):
                url = f"https://xz.aliyun.com/search/3?keywords={quote(keyword)}&page={p_num}"
                pg.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)
                
                extracted = pg.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('a'))
                            .filter(a => /xz\\.aliyun\\.com\\/news\\/\\d+/.test(a.href))
                            .map(a => ({ title: a.innerText.trim(), url: a.href.split('#')[0] }))
                            .filter(i => i.title.length > 5);
                    }
                """)
                for item in extracted:
                    results.append({"site": "先知社区", "title": item["title"], "url": item["url"]})
            browser.close()
    except Exception as e:
        print(f"先知社区搜索失败: {e}")
    return results

def concurrent_search(keyword, max_pages, browser_path="", on_status=None):
    all_results = []

    jobs = {
        "CSDN": lambda: fetch_csdn_results_all(keyword, max_pages),
        "博客园": lambda: fetch_cnblogs_results_all(keyword, max_pages, browser_path, on_status=on_status),
        "先知社区": lambda: fetch_xz_results_all(keyword, max_pages, browser_path),
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_map = {}
        for site_name, job in jobs.items():
            _notify(on_status, f"正在搜索 {site_name} ...")
            future_map[executor.submit(job)] = site_name

        for future in as_completed(future_map):
            site_name = future_map[future]
            try:
                site_results = future.result()
                all_results.extend(site_results)
                _notify(on_status, f"{site_name} 搜索完成，新增 {len(site_results)} 条结果")
            except Exception as e:
                print(f"{site_name} 搜索异常: {e}")
                _notify(on_status, f"{site_name} 搜索失败")

    seen = set()
    unique = []
    for r in all_results:
        if r["url"] not in seen:
            unique.append(r)
            seen.add(r["url"])

    unique.sort(key=lambda item: (item["site"], item["title"].lower()))
    return unique
