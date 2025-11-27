import re
import requests
import json
import os

BASE_URL = "https://cloud.zrvvv.com/cart"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# Telegram
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"})

# =====================================================
# 自动扫描所有 fid
# =====================================================
def scan_all_fid():
    html = requests.get(BASE_URL + "?fid=1", headers=HEADERS).text
    fids = set(map(int, re.findall(r"/cart\?fid=(\d+)", html)))
    if 1 not in fids:
        fids.add(1)
    return sorted(fids)

# =====================================================
# 自动扫描某个 fid 下的所有 gid
# =====================================================
def scan_gid_for_fid(fid):
    url = f"{BASE_URL}?fid={fid}"
    html = requests.get(url, headers=HEADERS).text
    gids = set(map(int, re.findall(r"cart\?fid=" + str(fid) + r"&gid=(\d+)", html)))
    # 返回所有 gid，不过滤 1
    return sorted(gids)

# =====================================================
# 抓取商品名称和库存
# =====================================================
def fetch_items(fid, gid=None):
    params = f"?fid={fid}"
    if gid:
        params += f"&gid={gid}"
    html = requests.get(BASE_URL + params, headers=HEADERS).text

    # 商品名称，抓 a 标签或 h4 标签，过滤空格
    names = [n.strip() for n in re.findall(r'<a[^>]*class="[^"]*yy-bth-text[^"]*"[^>]*>(.*?)</a>', html, re.S)]
    if not names:
        names = [n.strip() for n in re.findall(r'<h4>(.*?)</h4>', html, re.S)]

    # 库存
    invs = [int(x) for x in re.findall(r'库存\s*[:：]\s*(\d+)', html)]

    return [{"name": n, "inventory": i} for n, i in zip(names, invs)]

# =====================================================
# JSON 记录
# =====================================================
def load_last():
    if not os.path.exists("inventory.json"):
        return {}
    return json.load(open("inventory.json", "r", encoding="utf-8"))

def save_now(data):
    json.dump(data, open("inventory.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# =====================================================
# 比较库存变化
# =====================================================
def compare(old, new, region):
    changes = []
    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    for name, new_inv in new_map.items():
        old_inv = old_map.get(name)
        if old_inv is None:
            changes.append(f"🆕 {name} : 库存 {new_inv}")
        elif old_inv != new_inv:
            changes.append(f"🔔 {name} : 库存 {old_inv} → {new_inv}")

    for name in old_map:
        if name not in new_map:
            changes.append(f"❌ 下架商品：{name}")

    return changes if changes else None

# =====================================================
# 主逻辑
# =====================================================
def main():
    last = load_last()
    now_all = {}
    messages = []

    fids = scan_all_fid()
    for fid in fids:
        # 默认 fid 页面（gid=None）
        region_key = f"fid={fid}"
        items = fetch_items(fid)
        now_all[region_key] = items

        if region_key not in last:
            msg = [f"📌 首次记录区域 fid={fid}"]
            for i in items:
                msg.append(f"{i['name']} : 库存 {i['inventory']}")
            messages.append("\n".join(msg))
        else:
            diff = compare(last[region_key], items, region_key)
            if diff:
                messages.append(f"⚠️ 监控提醒：区域 fid={fid} 库存变化\n" + "\n".join(diff))

        # 扫描所有 gid
        gids = scan_gid_for_fid(fid)
        for gid in gids:
            # 如果 gid=1 已经等于默认 fid 页面，就不重复
            if gid == 1:
                continue
            region_key = f"fid={fid}&gid={gid}"
            items = fetch_items(fid, gid)
            now_all[region_key] = items

            if region_key not in last:
                msg = [f"📌 首次记录区域 fid={fid}&gid={gid}"]
                for i in items:
                    msg.append(f"{i['name']} : 库存 {i['inventory']}")
                messages.append("\n".join(msg))
            else:
                diff = compare(last[region_key], items, region_key)
                if diff:
                    messages.append(f"⚠️ 监控提醒：区域 fid={fid}&gid={gid} 库存变化\n" + "\n".join(diff))

    save_now(now_all)

    if messages:
        final_text = "⚠️ **监控提醒：发现有库存变化**\n\n" + "\n\n".join(messages)
        final_text += "\n\n🔗 直达链接: (https://cloud.zrvvv.com/cart)\nShopping Cart | 纯爱发电丨"
        print(final_text)
        send_telegram(final_text)

if __name__ == "__main__":
    main()
