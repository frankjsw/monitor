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
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"})


# =====================================================
# 自动扫描所有 fid（主分类）
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
    html = requests.get(f"{BASE_URL}?fid={fid}", headers=HEADERS).text
    gids = set(map(int, re.findall(r"cart\?fid=" + str(fid) + r"&gid=(\d+)", html)))
    # 只返回 gid>1 避免重复抓 fid 默认页面
    return sorted([g for g in gids if g > 1])


# =====================================================
# 抓取商品
# =====================================================
def fetch_items(fid, gid=None):
    params = f"?fid={fid}"
    if gid:
        params += f"&gid={gid}"
    html = requests.get(BASE_URL + params, headers=HEADERS).text

    # 获取商品名称
    names = re.findall(r'<a class="yy-bth-text.*?">(.*?)</a>', html, re.S)
    # 获取库存
    invs = list(map(int, re.findall(r'库存\s*[:：]\s*(\d+)', html)))

    return [{"name": n.strip(), "inventory": i} for n, i in zip(names, invs)]


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
# 变化比较
# =====================================================
def compare(old, new, region):
    changes = []
    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    # 新增或库存变化
    for name, new_inv in new_map.items():
        old_inv = old_map.get(name)
        if old_inv is None:
            changes.append(f"🆕 {name} : 库存 {new_inv}")
        elif old_inv != new_inv:
            changes.append(f"🔔 {name} : 库存 {old_inv} → {new_inv}")

    # 下架
    for name in old_map:
        if name not in new_map:
            changes.append(f"❌ 下架商品：{name}")

    if changes:
        return f"📌 首次记录区域 {region}\n" + "\n".join(changes)
    return None


# =====================================================
# 主逻辑
# =====================================================
def main():
    last = load_last()
    now_all = {}
    messages = []

    fids = scan_all_fid()

    for fid in fids:
        # 1️⃣ 默认 fid 页面（等价 gid=1）
        region_key = f"fid={fid}"
        items = fetch_items(fid)
        now_all[region_key] = items

        if region_key not in last:
            msg = f"📌 首次记录区域 {region_key}\n"
            for i in items:
                msg += f"{i['name']} : 库存 {i['inventory']}\n"
            messages.append(msg.strip())
        else:
            diff = compare(last[region_key], items, region_key)
            if diff:
                messages.append(diff)

        # 2️⃣ 扫描 fid 下的 gid>1
        gids = scan_gid_for_fid(fid)
        for gid in gids:
            region_key_gid = f"fid={fid}&gid={gid}"
            items_gid = fetch_items(fid, gid)
            now_all[region_key_gid] = items_gid

            if region_key_gid not in last:
                msg = f"📌 首次记录区域 {region_key_gid}\n"
                for i in items_gid:
                    msg += f"{i['name']} : 库存 {i['inventory']}\n"
                messages.append(msg.strip())
            else:
                diff = compare(last.get(region_key_gid, []), items_gid, region_key_gid)
                if diff:
                    messages.append(diff)

    # 保存最新数据
    save_now(now_all)

    # 推送 Telegram
    if messages:
        final_msg = "⚠️ 监控提醒：发现有库存变化\n\n"
        final_msg += "\n\n".join(messages)
        final_msg += f"\n\n🔗 直达链接: ({BASE_URL})\nShopping Cart | 纯爱发电丨"
        print(final_msg)
        send_telegram(final_msg)


if __name__ == "__main__":
    main()
