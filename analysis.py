# analysis.py - 校園 E-mail 分析（產生 5 張圖）
#
# 1. 從 Firebase 抓 /email 全部資料
# 2. 主要用 raw / content / subject 這三個欄位做文字解析
# 3. 產出：
#    (1) 主要寄件單位 Top 20          -> 01_units.png
#    (2) 郵件常見主題類型             -> 02_topic_types.png
#    (3) 各月份件數統整               -> 03_months.png
#    (4) 適用對象分析                 -> 04_audience.png
#    (5) 一天中不同時間的寄件分布     -> 05_hour_distribution.png

import os
import re
from collections import Counter
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams
from firebase import firebase

# ---------- 字型設定（讓圖表可以正常顯示中文） ----------
rcParams["font.family"] = "Microsoft JhengHei"  # Windows 推薦用微軟正黑體
rcParams["axes.unicode_minus"] = False          # 讓負號正常顯示

# ---------- Firebase & 輸出路徑 ----------
FIREBASE_URL = "https://db114-1-final-9c6eb-default-rtdb.asia-southeast1.firebasedatabase.app/"  # 若你原本不是這個，請改回自己的
OUTPUT_DIR = "./analysis_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------- 日期 / 時間 / 分類用的小工具 ----------

def parse_date(text: str):
    """
    從文字中抓出「日期」，回傳 datetime(date) 或 None
    支援：
      - 2025/12/18
      - 2025-12-18
      - 2025年12月18日
    """
    if not text:
        return None

    # 2025/12/18 或 2025-12-18
    m = re.search(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})", text)
    if m:
        s = m.group(1)
        try:
            if "/" in s:
                return datetime.strptime(s, "%Y/%m/%d")
            else:
                return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            pass

    # 2025年12月18日
    m = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", text)
    if m:
        nums = re.findall(r"\d+", m.group(1))
        if len(nums) == 3:
            y, mn, d = map(int, nums)
            try:
                return datetime(y, mn, d)
            except ValueError:
                return None

    return None


def parse_hour(text: str):
    """
    從文字中抓出一個 HH:MM，回傳「小時」(0~23) 或 None
    （不管是 '週三 下午 06:33' 或單純 '06:33' 都會抓第一個 HH:MM）
    """
    if not text:
        return None
    m = re.search(r"(\d{1,2}):(\d{2})", text)
    if not m:
        return None
    h = int(m.group(1))
    # 簡單保護一下範圍
    if h < 0 or h > 23:
        return None
    return h


def extract_unit(text: str) -> str:
    """
    抽出寄件單位：
      1. 優先：長庚大學公告系統【XXX公告】 -> 回傳 XXX公告
      2. 再來：長庚大學【XXX】          -> XXX
      3. 其他：
         - 有 @cgu.edu.tw -> 校內個人/老師
         - 其餘 -> 外部單位/廠商
    """
    if not text:
        return "未知"

    if "長庚大學公告系統" in text:
        m = re.search(r"長庚大學公告系統\s*【([^】]+)】", text)
        if m:
            return m.group(1)
        return "公告系統(未明單位)"

    m = re.search(r"長庚大學【([^】]+)】", text)
    if m:
        return m.group(1)

    if "@cgu.edu.tw" in text:
        return "校內個人/老師"

    return "外部單位/廠商"


TOPIC_PATTERNS = {
    "演講/講座": r"演講|講座|speech|talk|seminar|workshop|work shop",
    "徵才/招募": r"徵才|招募|recruit|招考|誠徵|聘任",
    "活動/競賽": r"活動|比賽|競賽|比賽|展覽|嘉年華|festival|camp",
    "課程/教學": r"課程|修課|選課|加退選|教學意見|EMI|教學資源",
    "系所/學院公告": r"學系公告|系公告|學系|學程|學院",
    "行政/校務公告": r"停電|維護|防火牆|網路|校務|調整|管制|安全性|防疫|交通|班次|機房|資訊中心公告|總務處",
    "獎助學金/補助": r"獎學金|補助|經費|補貼|助學金",
}

def classify_topic(text: str) -> str:
    if not text:
        return "其他"
    for topic, pat in TOPIC_PATTERNS.items():
        if re.search(pat, text, flags=re.IGNORECASE):
            return topic
    return "其他"


AUDIENCE_PATTERNS = {
    "大一新生": r"大一|一年級|新生",
    "全校師生": r"全校教職員生|全校教職員工生|全校師生|全校學生|全體教職員生|全體學生",
    "研究生": r"碩士班|博士班|研究生|研究所",
    "特定系所/學院": r"學系公告|系公告|學系|學程|學院|醫學系|護理系|資訊工程學系|資工系",
    "國際學生/外籍生": r"國際學生|外國學生|外籍生|International Students|EMI",
}

def classify_audience(text: str) -> str:
    if not text:
        return "其他/未明"

    for label, pat in AUDIENCE_PATTERNS.items():
        if re.search(pat, text):
            return label

    if "長庚大學公告系統" in text:
        return "全校或特定對象(未明)"

    return "其他/未明"


# ---------- 主程式 ----------

def main():
    # 1. 從 Firebase 抓資料
    fb = firebase.FirebaseApplication(FIREBASE_URL, None)
    data = fb.get("/email", None)

    if not data:
        print("❌ Firebase /email 沒有資料，請先跑 3_beautifulsoup.py 上傳。")
        return

    df = pd.DataFrame(data.values())
    print(f"✅ 成功從 Firebase 下載 {len(df)} 筆資料")

    # 2. 準備一個「分析用文字欄位」：優先 raw，其次 content，再來 subject
    def pick_text(row):
        if "raw" in row and pd.notna(row["raw"]):
            return str(row["raw"])
        if "content" in row and pd.notna(row["content"]):
            return str(row["content"])
        if "subject" in row and pd.notna(row["subject"]):
            return str(row["subject"])
        return ""

    df["text"] = df.apply(pick_text, axis=1)

    # 3. 解析寄件單位 / 主題類型 / 適用對象 / 日期 / 小時
    df["unit"] = df["text"].apply(extract_unit)
    df["topic_type"] = df["text"].apply(classify_topic)
    df["audience"] = df["text"].apply(classify_audience)
    # 先用我們的 parse_date 抓出 Python datetime / None
    df["dt"] = df["text"].apply(parse_date)

    # 再轉成 pandas 的 datetime，錯的自動變成 NaT
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce")

    # 用 .dt.strftime 來產生月份字串，NaT 會自動變成 NaN
    df["month"] = df["dt"].dt.strftime("%Y-%m")

    df["hour"] = df["text"].apply(parse_hour)

    # ========== 1. 主要寄件單位有哪些？ ==========
    unit_counts = df["unit"].value_counts()
    print("\n[1] 主要寄件單位（前 20 名）")
    for name, cnt in unit_counts.head(20).items():
        print(f"{name:20s} : {cnt:4d} 封")

    plt.figure(figsize=(10, 5))
    unit_counts.head(20).plot(kind="bar")
    plt.title("主要寄件單位 Top 20")
    plt.ylabel("信件數")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "01_units.png"))
    plt.close()

    # ========== 2. 郵件常見主題類型？ ==========
    topic_counts = df["topic_type"].value_counts()
    print("\n[2] 郵件常見主題類型")
    for t, cnt in topic_counts.items():
        print(f"{t:12s} : {cnt:4d} 封 ({cnt/len(df)*100:5.1f}%)")

    plt.figure(figsize=(8, 5))
    topic_counts.plot(kind="bar")
    plt.title("郵件常見主題類型")
    plt.ylabel("信件數")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "02_topic_types.png"))
    plt.close()

    # ========== 3. 各月份件數統整 ==========
    month_counts = df["month"].dropna().value_counts().sort_index()
    print("\n[3] 各月份件數統整")
    for m, cnt in month_counts.items():
        print(f"{m} : {cnt:4d} 封")

    if not month_counts.empty:
        plt.figure(figsize=(10, 4))
        month_counts.plot(kind="bar")
        plt.title("各月份公告信件量")
        plt.ylabel("信件數")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, "03_months.png"))
        plt.close()
    else:
        print("（目前資料中抓不到明確的年月資訊，因此無法畫月份統計圖）")

    # ========== 4. 適用對象分析 ==========
    aud_counts = df["audience"].value_counts()
    print("\n[4] 適用對象分析")
    for a, cnt in aud_counts.items():
        print(f"{a:16s} : {cnt:4d} 封 ({cnt/len(df)*100:5.1f}%)")

    plt.figure(figsize=(8, 5))
    aud_counts.plot(kind="bar")
    plt.title("公告信適用對象分布")
    plt.ylabel("信件數")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "04_audience.png"))
    plt.close()

    # ========== 5. 時間分布分析（一日中各小時） ==========
    hour_series = df["hour"].dropna().astype(int)
    hour_counts = hour_series.value_counts().sort_index()

    print("\n[5] 一天中不同時間的郵件量分布")
    total_with_hour = len(hour_series)
    for h, cnt in hour_counts.items():
        print(f"{h:02d}:00 - {h:02d}:59 : {cnt:4d} 封 ({cnt/total_with_hour*100:5.1f}%)")

    if not hour_counts.empty:
        plt.figure(figsize=(10, 4))
        plt.bar(hour_counts.index, hour_counts.values)
        plt.title("一天中不同時間的公告信件量")
        plt.xlabel("小時 (0–23)")
        plt.ylabel("信件數")
        plt.xticks(range(0, 24))
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, "05_hour_distribution.png"))
        plt.close()
    else:
        print("（目前資料中抓不到時間資訊，因此無法畫時間分布圖）")

    print(f"\n📁 圖片已輸出到資料夾：{OUTPUT_DIR}")


if __name__ == "__main__":
    main()
