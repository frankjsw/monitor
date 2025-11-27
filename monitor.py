import requests
from bs4 import BeautifulSoup
import time

# ----------------- 配置 -----------------
BASE_URL = "https://cloud.zrvvv.com"  # 替换为你的目标域名
CHECK_INTERVAL = 60  # 秒

# 映射 fid -> product type
product_type_map = {
    "1": "cloud.zrvvv.com",
    "2": "anotherProductType"
}

# 映射 gid -> availability zones
availability_zone_map = {
    "1": "活跃福利",
    "2": "其他zone"
}

# ----------------- 抓取函数 -----------------
def fetch_html(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.text

def parse_products(html):
    """
    返回数据结构：
    {
        fid: {
            gid: [
                {"name": "HK-①号", "qty": 0},
                ...
            ]
        }
    }
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    
    # 遍历每个商品的 div
    items = soup.select("div.secondgroup_item")
    for item in items:
        onclick = item.get("onclick", "")
        # 从 onclick 中解析 fid 和 gid
        fid, gid = "1", "1"
        if "fid=" in onclick and "gid=" in onclick:
            try:
                parts = onclick.split("?")[1].split("&")
                for part in parts:
                    if part.startswith("fid="):
                        fid = part.split("=")[1]
                    elif part.startswith("gid="):
                        gid = part.split("=")[1]
            except Exception:
                pass
        
        # 商品名称
        name_tag = item.select_one("a.yy-bth-text-a")
        name = name_tag.get_text(strip=True) if name_tag else "未知商品"

        # 商品数量
        qty_tag = item.select_one("g-b")
        qty = int(qty_tag.get_text(strip=True)) if qty_tag and qty_tag.get_text(strip=True).isdigit() else 0

        result.setdefault(fid, {}).setdefault(gid, []).append({"name": name, "qty": qty})

    return result

# ----------------- 打印函数 -----------------
def print_stock(data):
    for fid, gid_dict in data.items():
        for gid, items in gid_dict.items():
            # 只有 gid>1 才显示 availability zone
            gid_display = availability_zone_map.get(gid) if gid != "1" else None
            if gid_display:
                print(f"📌 首次记录区域 {product_type_map.get(fid, fid)} & {gid_display}")
            else:
                print(f"📌 首次记录区域 {product_type_map.get(fid, fid)}")
            for item in items:
                print(f"{item['name']}  数量：{item['qty']}")
            print()

# ----------------- 主循环 -----------------
def main():
    print("开始监控...")
    while True:
        try:
            html = fetch_html(BASE_URL)
            data = parse_products(html)
            print_stock(data)
        except Exception as e:
            print("抓取失败:", e)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
