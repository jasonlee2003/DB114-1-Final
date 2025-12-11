# 2_outlook.py – 用 PageDown 捲動信件列表，累積至少 2000 封信件
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import html  # 用來 escape 文字

# ========= 1. 啟動瀏覽器 & 請你登入 =========
options = Options()
options.add_argument(r"--user-data-dir=C:\chromedriver\user1")  # 你原本的 profile

driver = webdriver.Chrome(options=options)
driver.get("https://outlook.office.com/mail/0/inbox")
driver.maximize_window()

print("請在彈出的 Chrome 視窗中【登入 Outlook 並進入收件匣】")
print("登入完後不用做任何事，程式會自動開始抓信件。")

# 等到「郵件清單」出現（代表你已經進入收件匣）
try:
    WebDriverWait(driver, 300).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[aria-label='郵件清單']")
        )
    )
    print("✅ 已偵測到『郵件清單』，準備開始累積信件…")
except TimeoutException:
    print("❌ 5 分鐘內沒有偵測到『郵件清單』，請確認有成功登入收件匣再重跑程式。")
    driver.quit()
    raise SystemExit

# 找到第一封信，點一下，確保焦點在信件列表上
first_mail = WebDriverWait(driver, 60).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='option']"))
)
first_mail.click()
time.sleep(1)

# 之後用 body 發 PageDown，就像你手動按鍵盤一樣
body = driver.find_element(By.TAG_NAME, "body")

# ========= 2. 一邊捲動，一邊累計「看過的不同信件」 =========
target_count = 2000        # 目標：至少 2000 封
seen = set()               # 存所有看過的 aria-label（去重）
html_parts = ['<html><body>']

scroll_pause = 0.8
no_new_rounds = 0          # 連續幾輪都沒有新信
max_no_new_rounds = 150    # 多捲幾輪保險

while True:
    emails = driver.find_elements(By.CSS_SELECTOR, "div[role='option']")
    new_this_round = 0

    for e in emails:
        aria = e.get_attribute("aria-label")
        if not aria:
            continue
        if aria in seen:
            continue

        seen.add(aria)
        new_this_round += 1

        # 寫進我們自製的 HTML
        safe_aria = html.escape(aria, quote=True)
        html_parts.append(
            f'<div role="option" aria-label="{safe_aria}"></div>'
        )

    print(f"目前累積封數: {len(seen)}（本輪新增 {new_this_round}）")

    # 目標達成
    if len(seen) >= target_count:
        print(f"✅ 已累積至少 {target_count} 封信件")
        break

    # 判斷是否到底了：很多輪都沒有新增
    if new_this_round == 0:
        no_new_rounds += 1
        if no_new_rounds >= max_no_new_rounds:
            print("⚠ 已多次 PageDown 都沒有新信件，應該是到底了。")
            break
    else:
        no_new_rounds = 0

    # ⭐ 核心：送 PageDown，讓「信件列表」往下捲
    body.send_keys(Keys.PAGE_DOWN)

    time.sleep(scroll_pause)

# ========= 3. 把累積到的所有信件寫成一個 HTML 檔 =========
html_parts.append("</body></html>")
save_path = r"C:\Users\user\Desktop\final\emails_full.html"

with open(save_path, "w", encoding="utf-8") as f:
    f.write("\n".join(html_parts))

driver.quit()
print(f"✔ 已成功儲存 {len(seen)} 封信件到：{save_path}")
