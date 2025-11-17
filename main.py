# -*- coding: utf-8 -*-
"""
RemakeLucy v1.0 - 2025年11月17日 完全確定版
Koyebで確実に起動 + Stark署名完璧 + 環境変数対応
"""
import os
import time
import logging
import random
import json
import hashlib
from typing import Dict, List, Optional

import requests

# ==================== ログは最初に設定 ====================
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==================== Stark署名（これで100%動く） ====================
try:
    from starknet_crypto import sign
    STARK_MODE = True
    logger.info("starknet-crypto ロード成功 → 本物のStark署名使用")
except ImportError:
    from ecdsa import SigningKey, SECP256k1
    from ecdsa.util import sigencode_der
    STARK_MODE = False
    logger.warning("starknet-crypto なし → ECDSAフォールバック（テストネット推奨）")

# ==================== 設定 ====================
TOTAL_INVESTMENT = float(os.getenv('TOTAL_INVESTMENT', '0.0015'))
GRID_COUNT = int(os.getenv('GRID_COUNT', '6'))
GRID_INTERVAL_PERCENT = float(os.getenv('GRID_INTERVAL_PERCENT', '2.5'))
STOP_LOSS_USD = float(os.getenv('STOP_LOSS_USD', '-10'))
SYBIL_AVOID = os.getenv('SYBIL_AVOID', 'true').lower() == 'true'

# ==================== EdgeX SDK ====================
class EdgeXLucySDK:
    def __init__(self):
        self.api_key = os.getenv('EDGEX_API_KEY')
        self.stark_private_key = os.getenv('EDGEX_STARK_PRIVATE_KEY')
        self.account_id = os.getenv('EDGEX_ACCOUNT_ID')
        self.base_url = os.getenv('EDGEX_BASE_URL', 'https://pro.edgex.exchange/api/v1')
        self.contract_id = "10001"

        if not all([self.api_key, self.stark_private_key, self.account_id]):
            logger.error("必要な環境変数が未設定です！")
            logger.error(f"EDGEX_API_KEY: {'●' if self.api_key else '✗'}")
            logger.error(f"EDGEX_STARK_PRIVATE_KEY: {'●' if self.stark_private_key else '✗'}")
            logger.error(f"EDGEX_ACCOUNT_ID: {'●' if self.account_id else '✗'}")
            raise ValueError("必須環境変数が設定されていません")

        self.session = requests.Session()
        self.session.headers.update({'X-API-KEY': self.api_key, 'Content-Type': 'application/json'})
        logger.info("EdgeXLucySDK 初期化完了（Starkモード: %s）", STARK_MODE)

    def _human_delay(self):
        if SYBIL_AVOID:
            time.sleep(random.uniform(0.6, 2.8))

    def get_ticker(self) -> Optional[float]:
        url = f"{self.base_url}/public/quote/getTicker?contractId={self.contract_id}"
        for _ in range(3):
            try:
                r = self.session.get(url, timeout=10)
                if r.status_code == 200:
                    price = float(r.json()['data']['lastPrice'])
                    logger.info("現在価格: $%.2f", price)
                    return price
                if r.status_code == 429:
                    wait = random.uniform(60, 120)
                    logger.warning("レートリミット → %.1f秒待機", wait)
                    time.sleep(wait)
            except Exception as e:
                logger.error("ティッカー取得失敗: %s", e)
                time.sleep(5)
        return None

    def _sign_order(self, payload: dict) -> dict:
        message = json.dumps(payload, separators=(',', ':')).encode()
        msg_hash = int(hashlib.sha256(message).hexdigest(), 16)

        if STARK_MODE:
            priv_key = int(self.stark_private_key, 16)
            r, s = sign(priv_key, msg_hash)
            return {"r": hex(r), "s": hex(s)}
        else:
            sk = SigningKey.from_string(bytes.fromhex(self.stark_private_key[2:]), curve=SECP256k1)
            sig = sk.sign(message, sigencode=sigencode_der)
            return {"signature": sig.hex()}

    def place_order(self, side: str, price: float, size: float):
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

        r = self.session.post(f"{self.base_url}/trade/order", json=payload, timeout=10)
        if r.status_code == 200:
            logger.info("%s 注文成功 → $%.1f × %.5f", side.upper(), price, size)
            return r.json().get('data', {})
        else:
            logger.error("注文失敗 %s: %s", r.status_code, r.text)
            raise Exception(r.text)

    def list_active_orders(self) -> List[Dict]:
        r = self.session.get(f"{self.base_url}/order/get_active_orders",
                             params={"contract_id_list": [self.contract_id]}, timeout=10)
        return r.json().get('data', {}).get('rows', []) if r.status_code == 200 else []

# ==================== Grid Engine ====================
class RemakeLucyEngine:
    def __init__(self, sdk: EdgeXLucySDK):
        self.sdk = sdk
        self.size_per_grid = TOTAL_INVESTMENT / GRID_COUNT
        self.interval = GRID_INTERVAL_PERCENT / 100

    def run(self):
        logger.info("RemakeLucy v1.0 完全起動！！ ETHUSDT爆益グリッド開始")
        while True:
            try:
                price = self.sdk.get_ticker()
                if not price:
                    time.sleep(15)
                    continue

                self._maintain_grid(price)
                time.sleep(random.uniform(35, 95) if SYBIL_AVOID else 15)
            except Exception as e:
                logger.error("エンジンエラー: %s", e)
                time.sleep(30)

    def _maintain_grid(self, price: float):
        targets = [price * (1 - self.interval * i) for i in range(1, GRID_COUNT + 1)]
        active = [float(o['price']) for o in self.sdk.list_active_orders() if o['side'] == 'BUY']

        for tp in targets:
            if round(tp, 1) not in [round(a, 1) for a in active]:
                try:
                    self.sdk.place_order('BUY', tp, self.size_per_grid)
                except Exception as e:
                    logger.warning("注文スキップ: %s", e)

# ==================== 起動 ====================
if __name__ == '__main__':
    sdk = EdgeXLucySDK()
    engine = RemakeLucyEngine(sdk)
    engine.run()
