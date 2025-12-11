# 3_beautifulsoup.py – 解析寄件人/主旨/日期/內容摘要，存進 Firebase
from bs4 import BeautifulSoup
from firebase import firebase
import re

# 1. 讀 2_outlook.py 產生的 emails_full.html
html_path = r"C:\Users\user\Desktop\final\emails_full.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# 2. Firebase 初始化（用你現在這個專案）
url = "https://db114-1-final-9c6eb-default-rtdb.asia-southeast1.firebasedatabase.app/"
fb = firebase.FirebaseApplication(url, None)

# 3. 抓出每一封信（我們自己做的 <div role="option" aria-label="...">）
emails = soup.find_all("div", {"role": "option"})

count = 0

for mail in emails:
    aria = mail.get("aria-label")
    if not aria:
        continue

    text = aria.strip()

    # ---- 解析 sender / subject / date ----
    # 寄件人
    sender_match = re.search(r"寄件者:\s*(.*)", text)
    sender = sender_match.group(1) if sender_match else "unknown"

    # 日期（2025-10-19 / 週三 06:34 / 06:34 三種都盡量抓）
    date_match = re.search(
        r"(\d{4}-\d{2}-\d{2}|週[一二三四五六日]\s*\d{1,2}:\d{2}|\d{1,2}:\d{2})",
        text,
    )
    date = date_match.group(1) if date_match else "unknown"

    # 主旨：嘗試抓「未讀取 XXX 寄件者」，抓不到就用前 40 字
    subject_match = re.search(r"未讀取 (.*) 寄件者", text)
    subject = subject_match.group(1) if subject_match else text[:40]

    # 內容（簡單用前 120 字當內容摘要）
    content = text[:120]

    # 4. 組成要存進資料庫的資料
    data = {
        "sender": sender,
        "subject": subject,
        "date": date,
        "content": content,  # 作業裡的「內容」欄位
        "raw": text,         # 原始 aria-label，之後分析方便（可有可無）
    }

    fb.post("/email", data)
    count += 1
    print("✔ 已上傳:", data)

print(f"=== 完成，共上傳 {count} 封 email ===")
