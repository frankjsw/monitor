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
# 解析 productType & availability zones 映射表
# =====================================================
def parse_select_mappings():
    """自动抓取产品类型（fid）和可用区（gid）文字名称"""
    html = requests.get(BASE_URL + "?fid=1", headers=HEADERS).text

    # 解析 productType 字典
    fid_map = dict(re.findall(
        r'<option value="(\d+)">(.*?)</option>',
        re.search(r'id="productType".*?</select>', html, re.S).group()
    ))

    # 解析 availabilityZones 字典
    gid_map = dict(re.findall(
        r'<option value="(\d+)">(.*?)</option>',
        re.search(r'id="availabilityZones".*?</select>', html, re.S).group()
    ))

    return fid_map, gid_map


# =====================================================
# 自动扫描所有 fid（产品类型）
# =====================================================
def scan_all_fid(fid_map):
    return sorted(map(int, fid_map.keys()))


# =====================================================
# 自动扫描某个 fid 下的所有 gid（可用区）
# =====================================================
def scan_gid_for_fid(fid):
    url = f"{BASE_URL}?fid={fid}"
    html = requests.get(url, headers=HEADERS).text

    # 可能的 gid（但有误扫风险）
    gids = set(map(int, re.findall(fr"cart\?fid={fid}&gid=(\d+)", html)))
    gids = [g for g in gids if g > 1]  # gid=1 是默认区，跳过

    valid_gids = []

    # 二次验证：gid 页面是否真实存在商品
    for gid in gids:
        items = fetch_items(fid, gid)
        if len(items) > 0:
            valid_gids.append(gid)

    return sorted(valid_gids)


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
# 比较变化
# =====================================================
def compare(old, new, region_name):
    changes = []

    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    for name, new_inv in new_map.items():
        old_inv = old_map.get(name)
        if old_inv is None:
            changes.append(f"🆕 {region_name} 新增商品：{name} 库存 {new_inv}")
        elif old_inv != new_inv:
            changes.append(f"🔔 {region_name} 商品《{name}》库存 {old_inv} → {new_inv}")

    for name in old_map:
        if name not in new_map:
            changes.append(f"❌ {region_name} 下架商品：{name}")

    return "\n".join(changes) if changes else None


# =====================================================
# 主逻辑
# =====================================================
def main():
    fid_map, gid_map = parse_select_mappings()

    last = load_last()
    now_all = {}
    messages = []

    fids = scan_all_fid(fid_map)

    for fid in fids:

        # 默认区（gid=1）
        region_name = f"{fid_map[str(fid)]}（默认区域）"
        region_key = f"{fid}-1"

        items = fetch_items(fid)
        now_all[region_key] = items

        if region_key not in last:
            msg = [f"📌 首次记录区域 {region_name}"]
            for i in items:
                msg.append(f"{i['name']} 数量：{i['inventory']}")
            messages.append("\n".join(msg))
        else:
            diff = compare(last[region_key], items, region_name)
            if diff:
                messages.append(diff)

        # 其它 gid（自动扫描）
        gids = scan_gid_for_fid(fid)

        for gid in gids:
            region_name = f"{fid_map[str(fid)]}（{gid_map[str(gid)]}）"
            region_key = f"{fid}-{gid}"

            items = fetch_items(fid, gid)
            now_all[region_key] = items

            if region_key not in last:
                msg = [f"📌 首次记录区域 {region_name}"]
                for i in items:
                    msg.append(f"{i['name']} 数量：{i['inventory']}")
                messages.append("\n".join(msg))
            else:
                diff = compare(last[region_key], items, region_name)
                if diff:
                    messages.append(diff)

    save_now(now_all)

    if messages:
        final = "\n\n".join(messages)
        print(final)
        send_telegram(final)


if __name__ == "__main__":
    main()
