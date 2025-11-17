# -*- coding: utf-8 -*-
"""
RemakeLucy v1.0 - 429完全回避版（WebSocketティッカー + バックオフ強化）
2025/11/17 最終確定
"""
import os
import time
import logging
import random
import json
import hashlib
from typing import Dict, List, Optional

import requests
from ecdsa import SigningKey, SECP256k1
from ecdsa.util import sigencode_der

import websocket  # 追加: pip install websocket-client (requirements.txtに追加)

# ログ設定
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 設定
TOTAL_INVESTMENT = float(os.getenv('TOTAL_INVESTMENT', '0.04'))
GRID_COUNT = int(os.getenv('GRID_COUNT', '2'))
GRID_INTERVAL_PERCENT = float(os.getenv('GRID_INTERVAL_PERCENT', '2.5'))
MIN_ORDER_SIZE = float(os.getenv('MIN_ORDER_SIZE', '0.02'))
STOP_LOSS_USD = float(os.getenv('STOP_LOSS_USD', '-12'))
SYBIL_AVOID = os.getenv('SYBIL_AVOID', 'true').lower() == 'true'
TICKER_INTERVAL = int(os.getenv('TICKER_INTERVAL', '300'))

# EdgeX SDK
class EdgeXLucySDK:
    def __init__(self):
        self.api_key = os.getenv('EDGEX_API_KEY')
        self.stark_private_key = os.getenv('EDGEX_STARK_PRIVATE_KEY')
        self.account_id = os.getenv('EDGEX_ACCOUNT_ID')
        self.base_url = os.getenv('EDGEX_BASE_URL', 'https://pro.edgex.exchange/api/v1')
        self.contract_id = os.getenv('CONTRACT_ID', '10001')  # ETHUSD

        logger.info("環境変数チェック...")
        logger.info(f"EDGEX_API_KEY: {'OK' if self.api_key else 'NG'}")
        logger.info(f"EDGEX_STARK_PRIVATE_KEY: {'OK' if self.stark_private_key else 'NG'}")
        logger.info(f"EDGEX_ACCOUNT_ID: {'OK' if self.account_id else 'NG'}")

        if not all([self.api_key, self.stark_private_key, self.account_id]):
            raise ValueError("必須環境変数が未設定！")

        self.session = requests.Session()
        self.session.headers.update({'X-API-KEY': self.api_key, 'Content-Type': 'application/json'})
        logger.info("EdgeX接続完了！ 150USDT爆益モード起動！！")

        self.ws = None  # WebSocket初期化

    def _human_delay(self):
        if SYBIL_AVOID:
            min_delay = float(os.getenv('HUMAN_DELAY_MIN', '3'))
            max_delay = float(os.getenv('HUMAN_DELAY_MAX', '8'))
            time.sleep(random.uniform(min_delay, max_delay))

    def get_ticker(self) -> Optional[float]:
        # WebSocketでリアルタイムティッカー（429回避）
        if not self.ws or not self.ws.connected:
            self.ws = websocket.create_connection("wss://pro.edgex.exchange/ws/quote")
            self.ws.send(json.dumps({"action": "subscribe", "contractId": self.contract_id}))

        try:
            data = json.loads(self.ws.recv())
            if 'lastPrice' in data:
                price = float(data['lastPrice'])
                logger.info("WebSocketティッカー取得成功: $%.2f", price)
                return price
        except:
            logger.warning("WebSocketエラー、RESTにフォールバック")

        # RESTフォールバック (バックオフ強化)
        backoff = 60  # 初回待機秒
        for attempt in range(3):
            time.sleep(random.uniform(backoff * 0.8, backoff * 1.2))
            url = f"{self.base_url}/public/quote/getTicker?contractId={self.contract_id}"
            try:
                r = self.session.get(url, timeout=15)
                logger.debug("ティッカー応答: HTTP %s, データ: %s", r.status_code, r.text[:100])
                if r.status_code == 200:
                    data = r.json().get('data', {})
                    price = float(data.get('lastPrice', 0))
                    if price > 0:
                        logger.info("RESTティッカー取得成功: $%.2f", price)
                        return price
                    logger.warning("ティッカー空データ (EdgeXメンテ？)")
                elif r.status_code == 429:
                    logger.warning("429検出 → 待機秒を2倍に: %s秒", backoff * 2)
                    backoff *= 2  # 指数関数バックオフ
            except Exception as e:
                logger.error("ティッカー例外: %s", e)
        logger.warning("ティッカー3回失敗 → 5分後にリトライ")
        return None

    def _sign_order(self, payload: dict) -> dict:
        message = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        sk = SigningKey.from_string(bytes.fromhex(self.stark_private_key[2:]), curve=SECP256k1)
        sig = sk.sign(message, sigencode=sigencode_der)
        return {"signature": sig.hex()}

    def place_order(self, side: str, price: float, size: float) -> bool:
        self._human_delay()
        payload = {
            "contract_id": self.contract_id,
            "size": str(size),
            "price": str(round(price, 1)),
            "side": side.upper(),
            "account_id": self.account_id,
            "nonce": int(time.time() * 1000)
        }
        payload["signature"] = self._sign_order(payload)

        url = f"{self.base_url}/trade/order"
        try:
            r = self.session.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                logger.info("注文成功！ %s $%.1f × %.3f", side.upper(), price, size)
                return True
            else:
                logger.warning("注文失敗: HTTP %s - %s", r.status_code, r.text[:100])
                return False
        except Exception as e:
            logger.error("注文例外: %s", e)
            return False

    def list_active_orders(self) -> List[Dict]:
        params = {"contract_id_list": [self.contract_id]}
        url = f"{self.base_url}/order/get_active_orders"
        try:
            r = self.session.get(url, params=params, timeout=15)
            if r.status_code == 200:
                return r.json().get('data', {}).get('rows', [])
            logger.warning("注文一覧失敗: HTTP %s - %s", r.status_code, r.text[:100])
        except Exception as e:
            logger.error("注文一覧例外: %s", e)
        return []

# グリッドエンジン
class RemakeLucyEngine:
    def __init__(self, sdk):
        self.sdk = sdk
        self.size_per_grid = TOTAL_INVESTMENT / GRID_COUNT
        self.interval = GRID_INTERVAL_PERCENT / 100.0

    def run(self):
        logger.info("RemakeLucy v1.0 起動！ ETHUSDグリッド開始")
        while True:
            try:
                price = self.sdk.get_ticker()
                if not price:
                    time.sleep(300)  # 5分リトライ
                    continue

                targets = [price * (1 - self.interval * i) for i in range(1, GRID_COUNT + 1)]
                active_prices = [float(o.get('price', 0)) for o in self.sdk.list_active_orders() if o.get('side') == 'BUY']

                for tp in targets:
                    rounded_tp = round(tp, 1)
                    if rounded_tp not in [round(p, 1) for p in active_prices]:
                        success = self.sdk.place_order('BUY', rounded_tp, self.size_per_grid)
                        if success:
                            logger.info("グリッド追加成功！ BUY $%.1f", rounded_tp)

                logger.info("グリッドチェック完了！ 次は2分後")
                time.sleep(random.uniform(120, 180))  # 2-3分間隔

            except Exception as e:
                logger.error("エンジンエラー: %s", e)
                time.sleep(300)

# 起動
if __name__ == '__main__':
    sdk = EdgeXLucySDK()
    engine = RemakeLucyEngine(sdk)
    engine.run()
