import re
import requests
import json
import os

BASE_URL = "https://cloud.zrvvv.com/cart"

# ===============================
# 配置要监控的区域
# ===============================
TARGETS = [
    {"fid": 1, "gid": None},   # 监控 fid=1 默认
    {"fid": 1, "gid": 1},      # 监控 fid=1 & gid=1
    {"fid": 2, "gid": None},   # 监控 fid=2 默认
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ========== Telegram 通知（可选） ==========
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})


# ========== 抓取页面 HTML ==========
def fetch_html(fid, gid=None):
    params = f"?fid={fid}"
    if gid:
        params += f"&gid={gid}"
    url = BASE_URL + params
    print(f"Fetching: {url}")
    return requests.get(url, headers=HEADERS, timeout=20).text


# ========== 从页面解析商品名称和库存 ==========
def parse_inventory(html):
    """
    返回:
    [
      {"name": "HK-①号", "inventory": 0},
      {"name": "FR-②号", "inventory": 3},
      ...
    ]
    """

    # 商品名称：位于 <h4>xxx</h4>
    names = re.findall(r"<h4>(.*?)</h4>", html)

    # 库存： inventory ： 0
    invs = re.findall(r"inventory\s*：\s*(\d+)", html)
    invs = list(map(int, invs))

    items = []
    for name, inv in zip(names, invs):
        items.append({"name": name, "inventory": inv})

    return items


# ========== JSON 存储 ==========
def load_last():
    if not os.path.exists("inventory.json"):
        return {}
    with open("inventory.json", "r", encoding="utf-8") as f:
        return json.load(f)


def save_inventory(data):
    with open("inventory.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========== 主逻辑 ==========
def main():
    last = load_last()
    now_all = {}

    messages = []

    for t in TARGETS:
        fid, gid = t["fid"], t["gid"]

        key = f"fid={fid}&gid={gid}" if gid else f"fid={fid}"
        html = fetch_html(fid, gid)
        now = parse_inventory(html)

        now_all[key] = now  # 保存当前数据

        # last 中没有，说明首次监控
        if key not in last:
            messages.append(f"📌 首次记录区域 {key} 商品数量，共 {len(now)} 个商品")
            continue

        # 检查变化
        old_list = last[key]
        diff_msg = compare_changes(key, old_list, now)
        if diff_msg:
            messages.append(diff_msg)

    # 保存最新记录
    save_inventory(now_all)

    # 合并所有变化消息
    if messages:
        final = "\n\n".join(messages)
        print(final)
        send_telegram("库存变化提醒：\n" + final)


def compare_changes(region, old, new):
    changes = []
    # 商品数量可能变化，用 dict 处理
    old_map = {i["name"]: i["inventory"] for i in old}
    new_map = {i["name"]: i["inventory"] for i in new}

    # 检查所有商品
    for name, new_inv in new_map.items():
        old_inv = old_map.get(name)
        if old_inv is None:
            changes.append(f"🆕 区域 {region} 新增商品：{name}，库存 {new_inv}")
        elif old_inv != new_inv:
            changes.append(
                f"🔔 区域 {region} 商品《{name}》库存变化：{old_inv} → {new_inv}"
            )

    # 检查是否有商品被删除
    for name in old_map:
        if name not in new_map:
            changes.append(f"❌ 区域 {region} 商品已下架：{name}")

    return "\n".join(changes) if changes else None


if __name__ == "__main__":
    main()
