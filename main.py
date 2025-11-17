# -*- coding: utf-8 -*-
"""
RemakeLucy v1.0 - ByBitミス完全除去版（2025/11/17最終確定）
ETHUSD Perpetual専用 + レバx2対応 + ティッカー安定
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

# ログ設定
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 設定（150 USDT安全モード）
TOTAL_INVESTMENT = float(os.getenv('TOTAL_INVESTMENT', '0.04'))  # 2本分
GRID_COUNT = int(os.getenv('GRID_COUNT', '2'))
GRID_INTERVAL_PERCENT = float(os.getenv('GRID_INTERVAL_PERCENT', '2.5'))
MIN_ORDER_SIZE = float(os.getenv('MIN_ORDER_SIZE', '0.02'))  # レバx2最低
STOP_LOSS_USD = float(os.getenv('STOP_LOSS_USD', '-12'))
SYBIL_AVOID = os.getenv('SYBIL_AVOID', 'true').lower() == 'true'
TICKER_INTERVAL = int(os.getenv('TICKER_INTERVAL', '120'))  # 2分間隔

# EdgeX SDK（ByBitミス完全除去 + ETHUSD統一）
class EdgeXLucySDK:
    def __init__(self):
        self.api_key = os.getenv('EDGEX_API_KEY')  # ByBitキーじゃないよ！
        self.stark_private_key = os.getenv('EDGEX_STARK_PRIVATE_KEY')
        self.account_id = os.getenv('EDGEX_ACCOUNT_ID')
        self.base_url = os.getenv('EDGEX_BASE_URL', 'https://pro.edgex.exchange/api/v1')
        self.contract_id = os.getenv('CONTRACT_ID', '10001')  # ETHUSD Perpetual

        logger.info("=== 環境変数チェック（ByBitミス除去版） ===")
        logger.info(f"EDGEX_API_KEY: {'OK' if self.api_key else 'NG (ByBitキーじゃない！)'}")
        logger.info(f"EDGEX_STARK_PRIVATE_KEY: {'OK' if self.stark_private_key else 'NG'}")
        logger.info(f"EDGEX_ACCOUNT_ID: {'OK' if self.account_id else 'NG'}")
        logger.info(f"CONTRACT_ID: {self.contract_id} (ETHUSD用)")

        if not all([self.api_key, self.stark_private_key, self.account_id]):
            raise ValueError("EDGEX_ envが未設定！ ByBitキーじゃないよ！")

        self.session = requests.Session()
        self.session.headers.update({'X-API-KEY': self.api_key, 'Content-Type': 'application/json'})
        logger.info("EdgeX接続OK！ ETHUSDグリッド開始（ByBitミス除去）")

    def _human_delay(self):
        if SYBIL_AVOID:
            min_delay = float(os.getenv('HUMAN_DELAY_MIN', '3'))
            max_delay = float(os.getenv('HUMAN_DELAY_MAX', '8'))
            time.sleep(random.uniform(min_delay, max_delay))

    def get_ticker(self) -> Optional[float]:
        # 間隔待機（ティッカー安定）
        time.sleep(random.uniform(TICKER_INTERVAL * 0.8, TICKER_INTERVAL * 1.2))

        url = f"{self.base_url}/public/quote/getTicker?contractId={self.contract_id}"
        for attempt in range(3):
            try:
                r = self.session.get(url, timeout=15)
                logger.info(f"ティッカー試行 {attempt+1}: HTTP {r.status_code}")
                if r.status_code == 200:
                    data = r.json().get('data', {})
                    price = float(data.get('lastPrice', 0))
                    if price > 0:
                        logger.info("ティッカー取得成功！ ETHUSD = $%.2f", price)
                        return price
                    else:
                        logger.warning("ティッカー空データ（EdgeXメンテ？）")
                elif r.status_code == 429:
                    wait = random.uniform(90, 150)
                    logger.warning("レートリミット → %.1f秒待機", wait)
                    time.sleep(wait)
                else:
                    logger.warning("ティッカーHTTPエラー: %s - %s", r.status_code, r.text[:100])
            except Exception as e:
                logger.error("ティッカー例外 (試行 %d): %s", attempt + 1, e)
                time.sleep(10)
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
                logger.info("注文成功！ %s $%.1f × %.3f (ETHUSD)", side.upper(), price, size)
                return True
            else:
                logger.warning("注文HTTP %s: %s (サイズ%.3f OK？)", r.status_code, r.text[:100], size)
                return False
        except Exception as e:
            logger.error("注文例外: %s", e)
            return False

    def list_active_orders(self) -> List[Dict]:
        params = {"contract_id_list": [self.contract_id]}
        url = f"{self.base_url}/order/get_active_orders"
        try:
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json().get('data', {}).get('rows', [])
        except:
            pass
        return []

# グリッドエンジン
class RemakeLucyEngine:
    def __init__(self, sdk):
        self.sdk = sdk
        self.size_per_grid = TOTAL_INVESTMENT / GRID_COUNT
        self.interval = GRID_INTERVAL_PERCENT / 100.0

    def run(self):
        logger.info("RemakeLucy v1.0 起動！ ETHUSDグリッド開始（ByBitミス除去）")
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
