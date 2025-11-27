import re
import requests
import json
import os

BASE_URL = "https://cloud.zrvvv.com/cart"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# Telegram（可选）
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})

# =====================================================
# 自动扫描所有 fid 并抓 product type 名称
# =====================================================
def scan_all_fid():
    html = requests.get(BASE_URL, headers=HEADERS).text
    matches = re.findall(r'/cart\?fid=(\d+).*?>([^<>]+)<', html, re.S)
    fid_map = {}
    for fid, name in matches:
        fid_map[int(fid)] = name.strip()
    if not fid_map:
        fid_map[1] = "默认产品类型"
    return fid_map

# =====================================================
# 自动扫描 fid 下的所有 gid > 1
# =====================================================
def scan_gid_for_fid(fid):
    html = requests.get(f"{BASE_URL}?fid={fid}", headers=HEADERS).text
    gids = set(map(int, re.findall(r"cart\?fid=" + str(fid) + r"&gid=(\d+)", html)))
    gids = sorted([g for g in gids if g > 1])  # 只返回 gid>1
    return gids

# =====================================================
# 抓取商品名称和库存
# =====================================================
def fetch_items(fid, gid=None):
    url = f"{BASE_URL}?fid={fid}"
    if gid is not None:
        url += f"&gid={gid}"
    html = requests.get(url, headers=HEADERS).text

    # 匹配商品名称
    names = re.findall(r'<h4>(.*?)</h4>', html, re.S)
    if not names:
        names = re.findall(r'<a class="[^"]*yy-bth-text[^"]*">(.*?)</a>', html, re.S)
    # 匹配库存
    invs = list(map(int, re.findall(r"inventory\s*：\s*(\d+)", html)))
    items = [{"name": n.strip(), "inventory": i} for n, i in zip(names, invs)]
    return items

# =====================================================
# JSON 记录
# =====================================================
def load_last():
    if not os.path.exists("inventory.json"):
        return {}
    return json.load(open("inventory.json", "r", encoding="utf-8"))

def save_now(data):
    json.dump(data, open("inventory.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

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
            changes.append(f"🆕 区域 {region} 新增商品：{name} 库存 {new_inv}")
        elif old_inv != new_inv:
            changes.append(f"🔔 区域 {region} 商品《{name}》库存 {old_inv} → {new_inv}")

    for name in old_map:
        if name not in new_map:
            changes.append(f"❌ 区域 {region} 下架商品：{name}")

    return "\n".join(changes) if changes else None

# =====================================================
# 主逻辑
# =====================================================
def main():
    last = load_last()
    now_all = {}
    messages = []

    # 1. 扫描所有 fid
    fid_map = scan_all_fid()

    for fid, product_type in fid_map.items():

        # ① fid 默认区域（等价 gid=1）
        region_key = f"{product_type}"
        items = fetch_items(fid)
        now_all[region_key] = items

        # 首次记录
        if region_key not in last:
            msg = [f"📌 首次记录区域 {region_key}"]
            for i in items:
                msg.append(f"{i['name']} 数量：{i['inventory']}")
            messages.append("\n".join(msg))
        else:
            diff = compare(last[region_key], items, region_key)
            if diff:
                messages.append(diff)

        # ② 自动扫描 fid 下的 gid>1
        gids = scan_gid_for_fid(fid)
        for gid in gids:
            # availability zones 名称
            az_name_match = re.search(rf'cart\?fid={fid}&gid={gid}.*?>([^<>]+)<', requests.get(f"{BASE_URL}?fid={fid}&gid={gid}", headers=HEADERS).text)
            az_name = az_name_match.group(1).strip() if az_name_match else f"gid={gid}"
            region_key = f"{product_type}&{az_name}"
            items = fetch_items(fid, gid)
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

    save_now(now_all)

    if messages:
        final = "\n\n".join(messages)
        print(final)
        send_telegram(final)

if __name__ == "__main__":
    main()
