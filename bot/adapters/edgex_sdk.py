# -*- coding: utf-8 -*-
"""
EdgeXLucySDK - グロック強化版
ETHUSDT専用 + シビル回避 + エラー耐性
"""

import requests
import time
import logging
import random

logger = logging.getLogger(__name__)

class EdgeXLucySDK:
    def __init__(self, api_key: str, secret: str, stark_private_key: str, account_id: str, symbol: str = "ETHUSDT"):
        self.api_key = api_key
        self.secret = secret
        self.stark_private_key = stark_private_key
        self.account_id = account_id
        self.base_url = "https://pro.edgex.exchange/api/v1"
        self.contract_id = "10001"
        self.symbol = symbol
        logger.info(f"EdgeXLucySDK初期化: SYMBOL={self.symbol}")

    def get_ticker(self):
        url = f"{self.base_url}/public/quote/getTicker?contractId={self.contract_id}"
        for _ in range(3):
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json().get('data', {})
                    return {'price': float(data.get('lastPrice', 0))}
                elif resp.status_code == 429:
                    logger.warning("429 → 人間らしく待機...")
                    time.sleep(random.uniform(60, 120))
            except Exception as e:
                logger.error(f"ティッカー失敗: {e}")
                time.sleep(5)
        return None

    def place_order(self, side: str, price: float, size: float):
        time.sleep(random.uniform(0.5, 2.0))
        payload = {
            'contract_id': self.contract_id,
            'size': str(size),
            'price': str(round(price, 1)),
            'side': side
        }
        url = f"{self.base_url}/trade/order"
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('data', {})
        raise Exception(f"order failed: {resp.text}")

    def list_active_orders(self):
        params = {'contract_id_list': [self.contract_id]}
        url = f"{self.base_url}/order/get_active_orders"
        resp = requests.get(url, params=params, timeout=10)
        return resp.json().get('data', {}).get('rows', []) if resp.status_code == 200 else []

    def get_position(self):
        return {'net_size': 0.0}

    def get_pnl(self):
        return 0.0
