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
# 自动扫描所有 fid（主分类）
# =====================================================
def scan_all_fid():
    html = requests.get(BASE_URL + "?fid=1", headers=HEADERS).text

    # 寻找所有 /cart?fid=数字 的链接
    fids = set(map(int, re.findall(r"/cart\?fid=(\d+)", html)))

    # 确保至少有 fid=1
    if 1 not in fids:
        fids.add(1)

    return sorted(fids)


# =====================================================
# 自动扫描某个 fid 下的所有 gid
# =====================================================
def scan_gid_for_fid(fid):
    url = f"{BASE_URL}?fid={fid}"
    html = requests.get(url, headers=HEADERS).text

    # 寻找 /cart?fid=1&gid=数字
    gids = set(map(int, re.findall(r"cart\?fid=" + str(fid) + r"&gid=(\d+)", html)))

    # 默认 gid=1 等于无 gid（fid=1 页面）
    # 我们只返回 gid>1，因为 gid=1 与 fid=1 重复
    gids = sorted([g for g in gids if g > 1])

    return gids


# =====================================================
# 抓取商品
# =====================================================
def fetch_items(fid, gid=None):
    params = f"?fid={fid}"
    if gid is not None:
        params += f"&gid={gid}"

    html = requests.get(BASE_URL + params, headers=HEADERS).text

    names = re.findall(r"<h4>(.*?)</h4>", html)
    invs = list(map(int, re.findall(r"inventory\s*：\s*(\d+)", html)))

    return [{"name": n, "inventory": i} for n, i in zip(names, invs)]


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
# 变化比较
# =====================================================
def compare(old, new, region):
    changes = []

    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    # 变化 & 新增
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


# =====================================================
# 主逻辑
# =====================================================
def main():
    last = load_last()
    now_all = {}
    messages = []

    # 1. 自动扫描所有 fid
    fids = scan_all_fid()

    for fid in fids:

        # ① fid 默认区域（等价 gid=1）
        region_key = f"fid={fid}"
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

        # 2. 自动扫描 fid 下的 gid > 1
        gids = scan_gid_for_fid(fid)

        for gid in gids:
            region_key = f"fid={fid}&gid={gid}"
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

    # 保存记录
    save_now(now_all)

    # 发送通知
    if messages:
        final = "\n\n".join(messages)
        print(final)
        send_telegram(final)


if __name__ == "__main__":
    main()
