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

# --- 关键修复：使用脚本所在目录存状态 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAST_STATUS_FILE = os.path.join(BASE_DIR, "last_status.txt")


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
    """加载上次库存状态"""
    if not os.path.exists(LAST_STATUS_FILE):
        print("未发现上次状态文件")
        return {}

    data = {}
    with open(LAST_STATUS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":::")
            if len(parts) != 2:
                continue
            name, stock = parts
            data[name] = stock

    print("读取到上次状态：", data)
    return data


def save_last_status(status):
    """保存当前库存状态"""
    with open(LAST_STATUS_FILE, "w", encoding="utf-8") as f:
        for name, stock in status.items():
            f.write(f"{name}:::{stock}\n")

    print("已写入状态文件 →", LAST_STATUS_FILE)


def format_current_status(products):
    """格式化当前库存状态为字符串"""
    status = "当前库存状态:\n"
    for name, stock in products.items():
        status += f"{name}: {stock}\n"
    return status


def main():
    login()

    print("正在抓取库存...")
    products = fetch_products()
    if not products:
        return

    # 格式化当前库存状态
    current_status = format_current_status(products)

    # 发送当前库存状态到 Telegram
    send_telegram(current_status)

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
