import re
import requests
import json
import os

BASE_URL = "https://cloud.zrvvv.com/cart"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# Telegram 配置
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
    return sorted(gids)


# =====================================================
# 抓取商品
# =====================================================
def fetch_items(fid, gid=None):
    url = f"{BASE_URL}?fid={fid}"
    if gid is not None:
        url += f"&gid={gid}"
    html = requests.get(url, headers=HEADERS).text

    # 获取商品名称和库存
    names = re.findall(r"<h4>(.*?)</h4>", html)
    invs = list(map(int, re.findall(r"inventory\s*：\s*(\d+)", html)))
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
# 比较库存变化，返回格式化消息
# =====================================================
def compare(old, new):
    messages = []
    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    # 新增或变化
    for name, new_inv in new_map.items():
        old_inv = old_map.get(name)
        if old_inv is None:
            messages.append(f"🆕 {name} : 库存 {new_inv}")
        elif old_inv != new_inv:
            messages.append(f"🔔 {name} : 库存 {old_inv} → {new_inv}")

    # 下架
    for name in old_map:
        if name not in new_map:
            messages.append(f"❌ {name} 已下架")

    return messages


# =====================================================
# 主逻辑
# =====================================================
def main():
    last = load_last()
    now_all = {}
    messages_all = []

    fids = scan_all_fid()

    for fid in fids:
        # 默认 fid 区域
        region_key = f"fid={fid}"
        items = fetch_items(fid)
        now_all[region_key] = items

        if region_key not in last:
            msg = [f"📌 首次记录区域 fid={fid}"]
            for i in items:
                msg.append(f"{i['name']} : 库存 {i['inventory']}")
            messages_all.append("\n".join(msg))
        else:
            diff = compare(last[region_key], items)
            if diff:
                messages_all.append(f"📌 区域 fid={fid}\n" + "\n".join(diff))

        # 扫描 fid 下的 gid
        gids = scan_gid_for_fid(fid)
        for gid in gids:
            region_key_gid = f"fid={fid}&gid={gid}"
            items_gid = fetch_items(fid, gid)
            now_all[region_key_gid] = items_gid

            if region_key_gid not in last:
                msg = [f"📌 首次记录区域 fid={fid}&gid={gid}"]
                for i in items_gid:
                    msg.append(f"{i['name']} : 库存 {i['inventory']}")
                messages_all.append("\n".join(msg))
            else:
                diff = compare(last.get(region_key_gid, []), items_gid)
                if diff:
                    messages_all.append(f"📌 区域 fid={fid}&gid={gid}\n" + "\n".join(diff))

    # 保存最新库存
    save_now(now_all)

    # 发送 Telegram
    if messages_all:
        final_msg = "⚠️ **监控提醒：发现有库存变化**\n\n"
        final_msg += "\n\n".join(messages_all)
        final_msg += f"\n\n🔗 直达链接: {BASE_URL}\nZrvvv ({BASE_URL})\nShopping Cart | 纯爱发电丨"
        send_telegram(final_msg)
        print(final_msg)


if __name__ == "__main__":
    main()
