import re
import requests
import json
import os

BASE_URL = "https://cloud.zrvvv.com/cart"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ===============================
# Telegram
# ===============================
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })


# =====================================================
# 扫描所有 fid
# =====================================================
def scan_all_fid():
    html = requests.get(BASE_URL + "?fid=1", headers=HEADERS).text
    fids = set(map(int, re.findall(r"/cart\?fid=(\d+)", html)))
    fids.add(1)
    return sorted(fids)


# =====================================================
# 扫描 fid 下所有 gid
# =====================================================
def scan_gid_for_fid(fid):
    html = requests.get(f"{BASE_URL}?fid={fid}", headers=HEADERS).text
    gids = set(map(int, re.findall(rf"cart\?fid={fid}&gid=(\d+)", html)))
    gids.add(1)
    return sorted(gids)


# =====================================================
# 修复后的标题获取函数（不会再错！！！）
# =====================================================
def fetch_title(html, fid):
    # 一级标题
    if fid == 1:
        m1 = re.search(r'class="text-white yy-bth-text fs-24[^"]*?">(.*?)</a>', html)
    else:
        m1 = re.search(r'class="yy-bth-text fs-24[^"]*?">(.*?)</a>', html)

    title1 = m1.group(1).strip() if m1 else "Unknown"

    # 二级 active 标题
    m2 = re.search(
        r'<div class="secondgroup_item[^"]*active[^"]*">.*?<a class="text-white[^>]*>(.*?)</a>',
        html,
        re.S
    )
    title2 = m2.group(1).strip() if m2 else ""

    return f"{title1}-{title2}"


# =====================================================
# 抓取商品名称和库存
# =====================================================
def fetch_items(fid, gid):
    url = f"{BASE_URL}?fid={fid}&gid={gid}"
    html = requests.get(url, headers=HEADERS).text

    # 商品名称
    names = [n.strip() for n in re.findall(r"<h4>(.*?)</h4>", html)]

    # 库存
    invs = [int(n) for n in re.findall(r"inventory ：\s*(\d+)", html)]

    # 标题
    title = fetch_title(html, fid)

    return title, [{"name": n, "inventory": i} for n, i in zip(names, invs)]


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
def compare(old, new):
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
        gids = scan_gid_for_fid(fid)

        for gid in gids:
            title, items = fetch_items(fid, gid)
            region_key = title  # 用标题作为唯一键

            now_all[region_key] = items

            if region_key not in last:
                msg = [f"📌 首次记录：{region_key}"]
                for i in items:
                    msg.append(f"{i['name']} : 库存 {i['inventory']}")
                messages.append("\n".join(msg))
            else:
                diff = compare(last[region_key], items)
                if diff:
                    messages.append(
                        f"⚠️ 库存变化：{region_key}\n" + "\n".join(diff)
                    )

    save_now(now_all)

    if messages:
        final_text = "⚠️ **监控提醒：库存变化**\n\n" + "\n\n".join(messages)
        final_text += "\n\n🔗 https://cloud.zrvvv.com/cart"
        print(final_text)
        send_telegram(final_text)


if __name__ == "__main__":
    main()
