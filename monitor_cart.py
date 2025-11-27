import re
import requests
import json
import os

URL = "https://cloud.zrvvv.com/cart?fid=1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# === Telegram 通知（可选） ===
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(api, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})


def fetch_inventory():
    html = requests.get(URL, headers=HEADERS, timeout=20).text
    # 匹配所有 inventory 数字
    nums = re.findall(r"inventory\s*：\s*(\d+)", html)
    return list(map(int, nums))


def load_last():
    if not os.path.exists("inventory.json"):
        return None
    with open("inventory.json", "r", encoding="utf-8") as f:
        return json.load(f)


def save_inventory(data):
    with open("inventory.json", "w", encoding="utf-8") as f:
        json.dump(data, f)


def main():
    now = fetch_inventory()
    print("当前库存：", now)

    last = load_last()

    if last is None:
        print("首次运行，创建库存记录")
        save_inventory(now)
        return

    # 比较差异
    changed = []
    for i, (l, n) in enumerate(zip(last, now)):
        if l != n:
            changed.append(f"商品 #{i+1} 库存变化：{l} → {n}")

    if changed:
        msg = "库存变化提醒：\n" + "\n".join(changed)
        print(msg)
        send_telegram(msg)

    save_inventory(now)


if __name__ == "__main__":
    main()
