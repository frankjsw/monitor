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
        print("⚠ 未配置 Telegram 环境变量，取消推送")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
    )


# ===============================
# 自动抓取页面标题(区域名 + 子区域名)
# ===============================
def fetch_title(html):
    # 一级区域名，例如 Cloud.Zrvvv.com / 贵宾请上二楼包间
    m1 = re.search(r'class="yy-bth-text fs-24.*?">(.*?)<', html)
    title1 = m1.group(1).strip() if m1 else "Unknown"

    # 二级区域名，例如 活跃福利 / 二楼VIP
    m2 = re.search(
        r'<div class="secondgroup_item.*?<a class="text-white[^>]*>(.*?)<', html, re.S
    )
    title2 = m2.group(1).strip() if m2 else ""

    return f"{title1}-{title2}"


# ===============================
# 抓取商品列表(h4 + 库存)
# ===============================
def fetch_items(fid, gid=None):
    params = f"?fid={fid}"
    if gid:
        params += f"&gid={gid}"

    url = BASE_URL + params
    html = requests.get(url, headers=HEADERS).text

    # 页面标题
    title = fetch_title(html)

    # 商品名称
    names = [n.strip() for n in re.findall(r"<h4>(.*?)</h4>", html)]

    # 库存
    invs = [int(x) for x in re.findall(r"inventory\s*[:：]\s*(\d+)", html)]

    # 防止数量不一致
    items = []
    for i, name in enumerate(names):
        inv = invs[i] if i < len(invs) else None
        items.append({"name": name, "inventory": inv})

    return title, items


# ===============================
# 自动扫描所有 fid
# ===============================
def scan_all_fid():
    html = requests.get(BASE_URL + "?fid=1", headers=HEADERS).text
    fids = set(map(int, re.findall(r"/cart\?fid=(\d+)", html)))
    if 1 not in fids:
        fids.add(1)
    return sorted(fids)


# ===============================
# 自动扫描某个 fid 下所有 gid
# ===============================
def scan_gid_for_fid(fid):
    url = f"{BASE_URL}?fid={fid}"
    html = requests.get(url, headers=HEADERS).text
    gids = set(map(int, re.findall(rf"fid={fid}&gid=(\d+)", html)))
    return sorted(gids)


# ===============================
# JSON 数据
# ===============================
def load_last():
    if not os.path.exists("inventory.json"):
        return {}
    return json.load(open("inventory.json", "r", encoding="utf-8"))


def save_now(data):
    json.dump(data, open("inventory.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)


# ===============================
# 库存变化对比
# ===============================
def compare(old, new):
    changes = []
    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    # 新增或库存变化
    for name, new_inv in new_map.items():
        if name not in old_map:
            changes.append(f"🆕 **{name}** : 库存 {new_inv}")
        elif old_map[name] != new_inv:
            changes.append(f"🔔 **{name}** : {old_map[name]} → {new_inv}")

    # 下架
    for name in old_map:
        if name not in new_map:
            changes.append(f"❌ **下架**：{name}")

    return changes


# ===============================
# 主程序
# ===============================
def main():
    last = load_last()
    now_all = {}
    messages = []

    fids = scan_all_fid()

    for fid in fids:
        # 扫描当前 fid 自身页面
        title, items = fetch_items(fid)
        region_key = f"fid={fid}"
        now_all[region_key] = items

        if region_key not in last:
            msg = f"📌 **首次记录：{title}**\n" + "\n".join([f"{x['name']} : 库存 {x['inventory']}" for x in items])
            messages.append(msg)
        else:
            diff = compare(last[region_key], items)
            if diff:
                messages.append(f"⚠️ **库存变化：{title}**\n" + "\n".join(diff))

        # 扫描 gid
        gids = scan_gid_for_fid(fid)
        for gid in gids:
            title, items = fetch_items(fid, gid)
            region_key = f"fid={fid}&gid={gid}"
            now_all[region_key] = items

            if region_key not in last:
                msg = f"📌 **首次记录：{title}**\n" + "\n".join([f"{x['name']} : 库存 {x['inventory']}" for x in items])
                messages.append(msg)
            else:
                diff = compare(last[region_key], items)
                if diff:
                    messages.append(f"⚠️ **库存变化：{title}**\n" + "\n".join(diff))

    # 保存最新数据
    save_now(now_all)

    # 推送通知
    if messages:
        final_text = "⚠️ *监控提醒：库存变化*\n\n" + "\n\n".join(messages)
        final_text += "\n\n🔗 https://cloud.zrvvv.com/cart"
        print(final_text)
        send_telegram(final_text)
    else:
        print("无变化")


if __name__ == "__main__":
    main()
