# monitor.py
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests
import time

# 配置
URL = "https://cloud.zrvvv.com"
SCAN_INTERVAL = 300  # 扫描间隔，秒

# 保存上次库存状态
last_stock = {}

def parse_select_mappings():
    """自动抓取 product types 和 availability zones"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    product_type_select = soup.find("select", id="productType")
    if not product_type_select:
        raise ValueError("页面中没有找到 productType 下拉菜单")
    fid_map = {opt['value']: opt.text.strip() for opt in product_type_select.find_all('option') if opt.get('value')}

    availability_select = soup.find("select", id="availabilityZone")
    if not availability_select:
        gid_map = {}
    else:
        gid_map = {opt['value']: opt.text.strip() for opt in availability_select.find_all('option') if opt.get('value')}

    return fid_map, gid_map

def fetch_stock(fid, gid=None):
    """请求库存接口，返回 {商品名称: 数量}"""
    # 假设库存接口示例：https://cloud.zrvvv.com/api/stock?fid=1&gid=2
    params = {'fid': fid}
    if gid:
        params['gid'] = gid
    resp = requests.get(f"{URL}/api/stock", params=params)
    data = resp.json()
    stock = {item['name']: item['quantity'] for item in data.get('products', [])}
    return stock

def monitor():
    global last_stock
    fid_map, gid_map = parse_select_mappings()

    for fid, product_name in fid_map.items():
        # 先抓 fid 对应库存
        stock_fid = fetch_stock(fid)
        print(f"\n📌 首次记录区域 {product_name}")
        for name, qty in stock_fid.items():
            print(f"{name} 数量：{qty}")

        last_stock[(fid, None)] = stock_fid

        # 再抓 fid&gid 对应库存（只抓 gid>1 的情况）
        for gid, zone_name in gid_map.items():
            stock_fid_gid = fetch_stock(fid, gid)
            # 如果 fid 只有默认 gid=1，不用推送
            if len(gid_map) <= 1:
                continue
            print(f"\n📌 首次记录区域 {product_name} & {zone_name}")
            for name, qty in stock_fid_gid.items():
                print(f"{name} 数量：{qty}")
            last_stock[(fid, gid)] = stock_fid_gid

def main():
    while True:
        try:
            monitor()
        except Exception as e:
            print("监控出错:", e)
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
