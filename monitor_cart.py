import requests
from bs4 import BeautifulSoup
import time

URL = "https://cloud.zrvvv.com/cart"

# 换成你自己的 Cookie！！
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Cookie": os.getenv("COOKIE")
}

last_status = {}   # 保存上次库存状态


def fetch_products():
    """抓取产品名称与库存"""
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select("div.card.cartitem")
        result = {}

        for item in items:
            # 产品名
            name_tag = item.find("h4")
            if not name_tag:
                continue
            name = name_tag.text.strip()

            # 库存
            stock_tag = item.find("p", class_="card-text")
            if stock_tag and "库存" in stock_tag.text:
                stock = stock_tag.text.replace("库存：", "").strip()
            else:
                stock = "未知"

            result[name] = stock

        return result

    except Exception as e:
        print("请求失败：", e)
        return None


def monitor(interval=60):
    """监控库存变化"""
    global last_status

    while True:
        print("\n正在检查库存……")
        products = fetch_products()

        if not products:
            time.sleep(interval)
            continue

        # 第一次初始化
        if not last_status:
            last_status = products
            print("初始化库存：")
            for n, s in products.items():
                print(f" - {n}: {s}")
        else:
            # 对比库存变化
            for name, stock in products.items():
                old_stock = last_status.get(name)

                if old_stock != stock:
                    print(f"⚠️【库存变化】{name}: {old_stock} → {stock}")

            last_status = products

        time.sleep(interval)


if __name__ == "__main__":
    monitor(interval=60)   # 每 60 秒检查一次
