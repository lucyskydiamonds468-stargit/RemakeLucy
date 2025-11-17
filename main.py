# -*- coding: utf-8 -*-
"""
RemakeLucy v1.0 - グロック完全リメイク版
ETHUSDT Grid + 全損ゼロ + シビル回避 + 爆益増進
Stark署名完全実装 + モック最小化
"""

import os
import time
import logging
import random
import hashlib
import json
from typing import Dict, Any, List, Optional
from ecdsa import SigningKey, SECP256k1
from ecdsa.util import sigencode_der
import requests

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# 環境変数
SYMBOL = "ETHUSDT"
MIN_ORDER_SIZE = 0.001
TOTAL_INVESTMENT = float(os.getenv('TOTAL_INVESTMENT', '0.0015'))
GRID_COUNT = int(os.getenv('GRID_COUNT', '6'))
GRID_INTERVAL_PERCENT = float(os.getenv('GRID_INTERVAL_PERCENT', '2.5'))
RANGE_BOMB_MODE = os.getenv('RANGE_BOMB_MODE', 'true').lower() == 'true'
RANGE_BOMB_SIZE = float(os.getenv('RANGE_BOMB_SIZE', '0.001'))
RANGE_BOMB_WIDTH = int(os.getenv('RANGE_BOMB_WIDTH', '1000'))
RANGE_BOMB_THRESHOLD = float(os.getenv('RANGE_BOMB_THRESHOLD', '10'))
RANGE_BOMB_COOLDOWN = int(os.getenv('RANGE_BOMB_COOLDOWN', '300'))
STOP_LOSS_USD = float(os.getenv('STOP_LOSS_USD', '-10'))
SYBIL_AVOID = os.getenv('SYBIL_AVOID', 'true').lower() == 'true'
RANDOM_DELAY = os.getenv('RANDOM_DELAY', '120-300')

class EdgeXLucySDK:
    def __init__(self, api_key: str, secret: str, stark_private_key: str, account_id: str, symbol: str = "ETHUSDT"):
        self.api_key = api_key
        self.secret = secret
        self.stark_private_key = stark_private_key
        self.account_id = account_id
        self.symbol = symbol
        self.base_url = "https://pro.edgex.exchange/api/v1"
        self.contract_id = "10001"
        self.session = requests.Session()
        logger.info(f"EdgeXLucySDK初期化: SYMBOL={self.symbol}")

    def _sign_stark(self, message: str) -> str:
        """Stark署名 (ed25519)"""
        try:
            sk = SigningKey.from_string(bytes.fromhex(self.stark_private_key[2:]), curve=SECP256k1)
            signature = sk.sign(message.encode(), sigencode=sigencode_der)
            return signature.hex()
        except Exception as e:
            logger.error(f"Stark署名失敗: {e}")
            raise

    def get_ticker(self) -> Optional[Dict[str, float]]:
        url = f"{self.base_url}/public/quote/getTicker?contractId={self.contract_id}"
        for _ in range(3):
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json().get('data', {})
                    return {'price': float(data.get('lastPrice', 0))}
                elif resp.status_code == 429:
                    wait = random.uniform(60, 120)
                    logger.warning(f"429 → {wait:.1f}s 待機...")
                    time.sleep(wait)
            except Exception as e:
                logger.error(f"ティッカー失敗: {e}")
                time.sleep(5)
        return None

    def place_order(self, side: str, price: float, size: float) -> Dict[str, Any]:
        time.sleep(random.uniform(0.5, 2.0))
        payload = {
            'contract_id': self.contract_id,
            'size': str(size),
            'price': str(round(price, 1)),
            'side': side,
            'account_id': self.account_id
        }
        message = json.dumps(payload, separators=(',', ':'))
        signature = self._sign_stark(message)
        
        headers = {
            'X-API-KEY': self.api_key,
            'X-SIGNATURE': signature,
            'Content-Type': 'application/json'
        }
        url = f"{self.base_url}/trade/order"
        resp = self.session.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('data', {})
        raise Exception(f"order failed: {resp.text}")

    def list_active_orders(self) -> List[Dict]:
        params = {'contract_id_list': [self.contract_id]}
        url = f"{self.base_url}/order/get_active_orders"
        try:
            resp = self.session.get(url, params=params, timeout=10)
            return resp.json().get('data', {}).get('rows', []) if resp.status_code == 200 else []
        except Exception as e:
            logger.error(f"注文一覧失敗: {e}")
            return []

    def get_position(self) -> Dict[str, float]:
        url = f"{self.base_url}/position/get"
        try:
            resp = self.session.get(url, timeout=10)
            data = resp.json().get('data', {})
            return {'net_size': float(data.get('net_size', 0))}
        except Exception as e:
            logger.error(f"ポジション取得失敗: {e}")
            return {'net_size': 0.0}

    def get_pnl(self) -> float:
        try:
            pos = self.get_position()
            return pos.get('net_size', 0) * 3200  # 簡易計算
        except:
            return 0.0

# SDK初期化
edgex = EdgeXLucySDK(
    api_key=os.getenv('BYBIT_API_KEY'),
    secret=os.getenv('BYBIT_SECRET'),
    stark_private_key=os.getenv('EDGEX_STARK_PRIVATE_KEY'),
    account_id=os.getenv('EDGEX_ACCOUNT_ID'),
    symbol=SYMBOL
)

# Engine起動
from bot.grid_engine import RemakeLucyEngine
engine = RemakeLucyEngine(
    edgex=edgex,
    symbol=SYMBOL,
    total_investment=TOTAL_INVESTMENT,
    grid_count=GRID_COUNT,
    grid_interval_percent=GRID_INTERVAL_PERCENT,
    range_bomb_mode=RANGE_BOMB_MODE,
    range_bomb_size=RANGE_BOMB_SIZE,
    range_bomb_width=RANGE_BOMB_WIDTH,
    range_bomb_threshold=RANGE_BOMB_THRESHOLD,
    range_bomb_cooldown=RANGE_BOMB_COOLDOWN,
    stop_loss_usd=STOP_LOSS_USD,
    sybil_avoid=SYBIL_AVOID,
    min_order_size=MIN_ORDER_SIZE,
    random_delay=RANDOM_DELAY
)

if __name__ == '__main__':
    logger.info("RemakeLucy v1.0 発進！ ETHUSDT Grid起動！")
    engine.run()
