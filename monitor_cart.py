import requests
from bs4 import BeautifulSoup
import os

LOGIN_URL = "https://cloud.zrvvv.com/login"
CART_URL = "https://cloud.zrvvv.com/cart"

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

session = requests.Session()

# 用于保存上次抓到的库存
LAST_STATUS_FILE = "last_status.txt"


def send_telegram(msg: str):
    """发送 Telegram 通知"""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": msg
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram 推送失败：", e)


def login():
    """自动登录并获取 session"""
    print("正在登录...")

    payload = {
        "email": EMAIL,
        "password": PASSWORD
    }

    headers = {"User-Agent": "Mozilla/5.0"}

    resp = session.post(LOGIN_URL, data=payload, headers=headers)

    if resp.status_code in (200, 302):
        print("登录成功")
    else:
        print("登录失败：", resp.status_code)


def fetch_products():
    """抓取购物车库存"""
    try:
        resp = session.get(CART_URL, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select("div.card.cartitem")
        result = {}

        for item in items:
            name_tag = item.find("h4")
            if not name_tag:
                continue

            name = name_tag.text.strip()

            stock_tag = item.find("p", class_="card-text")
            if stock_tag and "库存" in stock_tag.text:
                stock = stock_tag.text.replace("库存：", "").strip()
            else:
                stock = "未知"

            result[name] = stock

        return result

    except Exception as e:
        print("抓取库存失败：", e)
        return None


def load_last_status():
    if not os.path.exists(LAST_STATUS_FILE):
        return {}

    data = {}
    with open(LAST_STATUS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            name, stock = line.strip().split(":::")
            data[name] = stock
    return data


def save_last_status(status):
    with open(LAST_STATUS_FILE, "w", encoding="utf-8") as f:
        for name, stock in status.items():
            f.write(f"{name}:::{stock}\n")


def main():
    login()

    print("正在抓取库存...")
    products = fetch_products()
    if not products:
        return

    last_status = load_last_status()

    # 第一次运行（无历史记录）
    if not last_status:
        print("首次运行，保存库存状态")
        save_last_status(products)
        return

    # 对比库存变化
    for name, stock in products.items():
        old_stock = last_status.get(name)

        if old_stock != stock:
            msg = f"库存变化：{name}\n{old_stock} → {stock}"
            print(msg)
            send_telegram(msg)

    save_last_status(products)


if __name__ == "__main__":
    main()
