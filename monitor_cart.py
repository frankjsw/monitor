import requests
from bs4 import BeautifulSoup
import os
import time

LOGIN_URL = "https://cloud.zrvvv.com/login"
CART_URL = "https://cloud.zrvvv.com/cart"

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

session = requests.Session()


def login():
    """自动登录并获取 session"""
    print("正在登录...")

    payload = {
        "email": EMAIL,
        "password": PASSWORD
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    resp = session.post(LOGIN_URL, data=payload, headers=headers)

    # 登录成功通常会重定向
    if resp.status_code in (200, 302):
        print("登录成功")
    else:
        print("登录失败，状态码：", resp.status_code)


def fetch_products():
    """抓取购物车中的产品与库存"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = session.get(CART_URL, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select("div.card.cartitem")
        result = {}

        for item in items:
            name_tag = item.find("h4")
            if not name_tag:
                continue

            name = name_tag.text.strip()

            stock_tag = item.find("p", class_="card-text")
            if stock_tag and "库存" in stock_tag.text:
                stock = stock_tag.text.replace("库存：", "").strip()
            else:
                stock = "未知"

            result[name] = stock

        return result

    except Exception as e:
        print("请求失败：", e)
        return None


def main():
    login()

    print("开始抓取库存...")

    products = fetch_products()
    if not products:
        print("抓取失败")
        return

    print("当前库存：")
    for name, stock in products.items():
        print(f" - {name}: {stock}")


if __name__ == "__main__":
    main()
