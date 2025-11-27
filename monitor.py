import re
import requests
import json
import os

BASE_URL = "https://cloud.zrvvv.com/cart"

# ===============================
# 配置要监控的区域
# ===============================
TARGETS = [
    {"fid": 1, "gid": None},
    {"fid": 1, "gid": 1},
    {"fid": 2, "gid": None},   # <<< 已加入 fid=2
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ========== Telegram 通知（可选） ==========
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})


# ======================================
# 抓取 HTML
# ======================================
def fetch_html(fid, gid=None):
    params = f"?fid={fid}"
    if gid is not None:
        params += f"&gid={gid}"
    url = BASE_URL + params
    print("Fetching:", url)
    return requests.get(url, headers=HEADERS, timeout=20).text


# ======================================
# 解析商品名称 + 库存
# ======================================
def parse_inventory(html):
    names = re.findall(r"<h4>(.*?)</h4>", html)
    invs = list(map(int, re.findall(r"inventory\s*：\s*(\d+)", html)))

    items = []
    for name, inv in zip(names, invs):
        items.append({"name": name, "inventory": inv})
    return items


# ======================================
# JSON 操作
# ======================================
def load_last():
    if not os.path.exists("inventory.json"):
        return {}
    with open("inventory.json", "r", encoding="utf-8") as f:
        return json.load(f)


def save_inventory(data):
    with open("inventory.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ======================================
# 区域比较
# ======================================
def compare_changes(region, old, new):
    changes = []

    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    for name, new_inv in new_map.items():
        old_inv = old_map.get(name)
        if old_inv is None:
            changes.append(f"🆕 区域 {region} 新增商品：{name}，库存 {new_inv}")
        elif old_inv != new_inv:
            changes.append(f"🔔 区域 {region} 商品《{name}》库存变化： {old_inv} → {new_inv}")

    for name in old_map:
        if name not in new_map:
            changes.append(f"❌ 区域 {region} 商品下架：{name}")

    return "\n".join(changes) if changes else None


# ======================================
# 主流程
# ======================================
def main():
    last = load_last()
    now_all = {}

    messages = []

    for t in TARGETS:
        fid, gid = t["fid"], t["gid"]
        region_key = f"fid={fid}&gid={gid}" if gid is not None else f"fid={fid}"

        html = fetch_html(fid, gid)
        now = parse_inventory(html)
        now_all[region_key] = now

        # === 首次记录：推送详细商品数据 ===
        if region_key not in last:
            msg = [f"📌 首次记录区域 {region_key}"]
            for item in now:
                msg.append(f"{item['name']}  数量：{item['inventory']}")
            messages.append("\n".join(msg))
            continue

        # === 检查变化 ===
        old_list = last[region_key]
        diff_msg = compare_changes(region_key, old_list, now)
        if diff_msg:
            messages.append(diff_msg)

    save_inventory(now_all)

    if messages:
        final_msg = "\n\n".join(messages)
        print(final_msg)
        send_telegram(final_msg)


if __name__ == "__main__":
    main()
