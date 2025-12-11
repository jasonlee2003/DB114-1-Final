from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

options = Options()
options.add_argument(r"--user-data-dir=C:\chromedriver\user1")
driver = webdriver.Chrome(options=options)

driver.get("https://outlook.office.com/mail/0/inbox")
time.sleep(8)

selectors = [
    "div[role='list']",
    "div[aria-label='郵件清單']",
    "div[aria-label='Message list']",
    "div.ZjFb7",
    "div.U9XYu",
    "div._3qM3P",
    "div._1SmzW",
    "div[role='region']",
]

print("開始偵測可捲動的容器...\n")

for sel in selectors:
    try:
        element = driver.find_element(By.CSS_SELECTOR, sel)
        print(f"找到元素：{sel}")
        size = element.size
        print("大小:", size)
        print("-" * 40)
    except:
        pass

print("\n偵測結束，請截圖發給我哪些找到了！")

time.sleep(20)
driver.quit()
