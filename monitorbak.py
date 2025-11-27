import re
import requests
import json
import os

BASE_URL = "https://cloud.zrvvv.com/cart"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Telegram（可选）
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})

# =============================
# 扫描所有 fid
# =============================
def scan_all_fid():
    html = requests.get(BASE_URL + "?fid=1", headers=HEADERS).text
    fids = set(map(int, re.findall(r"/cart\?fid=(\d+)", html)))
    if 1 not in fids:
        fids.add(1)
    return sorted(fids)

# =============================
# 扫描某 fid 下所有 gid
# =============================
def scan_gid_for_fid(fid):
    html = requests.get(f"{BASE_URL}?fid={fid}", headers=HEADERS).text
    gids = set(map(int, re.findall(r"cart\?fid=" + str(fid) + r"&gid=(\d+)", html)))
    return sorted(gids)

# =============================
# 抓取商品
# =============================
def fetch_items(fid, gid=None):
    params = f"?fid={fid}" + (f"&gid={gid}" if gid else "")
    html = requests.get(BASE_URL + params, headers=HEADERS).text
    names = re.findall(r"<h4>(.*?)</h4>", html)
    invs = list(map(int, re.findall(r"inventory\s*：\s*(\d+)", html)))
    return [{"name": n.strip(), "inventory": i} for n, i in zip(names, invs)]

# =============================
# 记录载入与保存
# =============================
def load_last():
    if not os.path.exists("inventory.json"):
        return {}
    return json.load(open("inventory.json", "r", encoding="utf-8"))

def save_now(data):
    json.dump(data, open("inventory.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

# =============================
# 比较变化
# =============================
def compare(old, new, region):
    changes = []
    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    # 新增或变化
    for name, new_inv in new_map.items():
        old_inv = old_map.get(name)
        if old_inv is None:
            changes.append(f"🆕 区域 {region} 新增商品：{name} 库存 {new_inv}")
        elif old_inv != new_inv:
            changes.append(f"🔔 区域 {region} 商品《{name}》库存 {old_inv} → {new_inv}")

    # 下架
    for name in old_map:
        if name not in new_map:
            changes.append(f"❌ 区域 {region} 下架商品：{name}")

    return "\n".join(changes) if changes else None

# =============================
# 主逻辑
# =============================
def main():
    last = load_last()
    now_all = {}
    messages = []

    fids = scan_all_fid()
    for fid in fids:
        # 默认 fid 页面（相当于 gid=1）
        region_key = f"fid={fid}"
        items = fetch_items(fid)
        now_all[region_key] = items

        if region_key not in last:
            msg = [f"📌 首次记录区域 {region_key}"]
            for i in items:
                msg.append(f"{i['name']} 数量：{i['inventory']}")
            messages.append("\n".join(msg))
        else:
            diff = compare(last[region_key], items, region_key)
            if diff:
                messages.append(diff)

        # 扫描 fid 下的 gid
        gids = scan_gid_for_fid(fid)
        for gid in gids:
            region_key = f"fid={fid}&gid={gid}"
            items_gid = fetch_items(fid, gid)
            now_all[region_key] = items_gid

            # 如果 gid 页面和 fid 页面内容完全一样，就不推送
            if items_gid != items:
                if region_key not in last:
                    msg = [f"📌 首次记录区域 {region_key}"]
                    for i in items_gid:
                        msg.append(f"{i['name']} 数量：{i['inventory']}")
                    messages.append("\n".join(msg))
                else:
                    diff = compare(last[region_key], items_gid, region_key)
                    if diff:
                        messages.append(diff)

    save_now(now_all)
    if messages:
        final = "\n\n".join(messages)
        print(final)
        send_telegram(final)

if __name__ == "__main__":
    main()
