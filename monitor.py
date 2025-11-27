import re
import requests
import json
import os

BASE_URL = "https://cloud.zrvvv.com/cart"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# Telegram 配置（从环境变量读取）
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram 未配置，跳过推送")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("⚠️ Telegram 推送失败:", e)


# ===============================
# 扫描所有 fid
# ===============================
def scan_all_fid():
    html = requests.get(BASE_URL + "?fid=1", headers=HEADERS).text
    fids = set(map(int, re.findall(r"/cart\?fid=(\d+)", html)))
    if 1 not in fids:
        fids.add(1)
    return sorted(fids)


# ===============================
# 扫描 fid 下的 gid
# ===============================
def scan_gid_for_fid(fid):
    html = requests.get(f"{BASE_URL}?fid={fid}", headers=HEADERS).text
    gids = set(map(int, re.findall(r"cart\?fid=" + str(fid) + r"&gid=(\d+)", html)))
    # 返回所有 gid（包括 gid=1）
    return sorted(gids)


# ===============================
# 抓取商品及库存
# ===============================
def fetch_items(fid, gid=None):
    params = f"?fid={fid}"
    if gid is not None:
        params += f"&gid={gid}"
    html = requests.get(BASE_URL + params, headers=HEADERS).text

    # 商品名称
    names = re.findall(r'<a class="text-white yy-bth-text fs-24.*?">(.*?)<', html, re.S)
    # 库存数量
    invs = list(map(int, re.findall(r'inventory\s*：\s*(\d+)', html)))
    
    # 确保数量对应
    items = [{"name": n.strip(), "inventory": i} for n, i in zip(names, invs)]
    return items


# ===============================
# JSON 记录加载/保存
# ===============================
def load_last():
    if not os.path.exists("inventory.json"):
        return {}
    return json.load(open("inventory.json", "r", encoding="utf-8"))


def save_now(data):
    json.dump(data, open("inventory.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


# ===============================
# 比较库存变化
# ===============================
def compare(old, new):
    messages = []
    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    for name, new_inv in new_map.items():
        old_inv = old_map.get(name)
        if old_inv is None:
            messages.append(f"🆕 {name} : 库存 {new_inv}")
        elif old_inv != new_inv:
            messages.append(f"🔔 {name} 库存 {old_inv} → {new_inv}")
    for name in old_map:
        if name not in new_map:
            messages.append(f"❌ {name} 已下架")
    return messages


# ===============================
# 主逻辑
# ===============================
def main():
    last = load_last()
    now_all = {}
    messages_all = []

    fids = scan_all_fid()
    for fid in fids:
        gids = scan_gid_for_fid(fid)
        if not gids:
            gids = [None]  # 如果没有 gid

        for gid in gids:
            key = f"fid={fid}" if gid is None else f"fid={fid}&gid={gid}"
            items = fetch_items(fid, gid)
            now_all[key] = items

            if key not in last:
                msg = [f"📌 首次记录区域 {key}"]
                for i in items:
                    msg.append(f"{i['name']} : 库存 {i['inventory']}")
                messages_all.append("\n".join(msg))
            else:
                diff = compare(last[key], items)
                if diff:
                    msg = [f"⚠️ **监控提醒：发现有库存变化**"]
                    msg.extend(diff)
                    messages_all.append("\n".join(msg))

    save_now(now_all)

    if messages_all:
        final_msg = "\n\n".join(messages_all)
        final_msg += f"\n\n🔗 直达链接: {BASE_URL}\n\nZrvvv ({BASE_URL})\nShopping Cart | 纯爱发电丨"
        print(final_msg)
        send_telegram(final_msg)


if __name__ == "__main__":
    main()
