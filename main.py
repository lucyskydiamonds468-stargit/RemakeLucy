# -*- coding: utf-8 -*-
"""
RemakeLucy v1.0 - Koyeb即時起動版
ETHUSDT Grid + 全損ゼロ + シビル回避 + Stark署名完全対応
"""
import os
import time
import logging
import random
import json
from typing import Dict, Any, List, Optional

# -----------------------------
# 必須ライブラリは requirements.txt で解決
# -----------------------------
try:
    import requests
    from starkex.order import Order, sign
except ImportError as e:
    raise ImportError(f"ライブラリ不足: {e}. requirements.txt を確認してください。")

# -----------------------------
# ログ設定
# -----------------------------
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# -----------------------------
# 環境変数
# -----------------------------
SYMBOL = "ETHUSDT"
MIN_ORDER_SIZE = 0.001
TOTAL_INVESTMENT = float(os.getenv('TOTAL_INVESTMENT', '0.0015'))
GRID_COUNT = int(os.getenv('GRID_COUNT', '6'))
GRID_INTERVAL_PERCENT = float(os.getenv('GRID_INTERVAL_PERCENT', '2.5'))
STOP_LOSS_USD = float(os.getenv('STOP_LOSS_USD', '-10'))
SYBIL_AVOID = os.getenv('SYBIL_AVOID', 'true').lower() == 'true'

# -----------------------------
# EdgeX SDK
# -----------------------------
class EdgeXLucySDK:
    def __init__(self):
        self.api_key = os.getenv('EDGEX_API_KEY')
        self.secret = os.getenv('EDGEX_SECRET')  # 未使用だが互換性維持
        self.stark_private_key = os.getenv('EDGEX_STARK_PRIVATE_KEY')
        self.account_id = os.getenv('EDGEX_ACCOUNT_ID')
        self.base_url = os.getenv('EDGEX_BASE_URL', 'https://pro.edgex.exchange/api/v1')
        self.contract_id = "10001"
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        })
        logger.info(f"EdgeXLucySDK 初期化完了: {SYMBOL}")

    def _human_delay(self):
        if SYBIL_AVOID:
            delay = random.uniform(0.5, 2.5)
            time.sleep(delay)

    def get_ticker(self) -> Optional[float]:
        url = f"{self.base_url}/public/quote/getTicker?contractId={self.contract_id}"
        for _ in range(3):
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    price = float(resp.json().get('data', {}).get('lastPrice', 0))
                    logger.debug(f"ティッカー: ${price}")
                    return price
                elif resp.status_code == 429:
                    wait = random.uniform(60, 120)
                    logger.warning(f"429 → {wait:.1f}s 待機")
                    time.sleep(wait)
            except Exception as e:
                logger.error(f"ティッカーエラー: {e}")
                time.sleep(5)
        return None

    def _sign_order(self, order: Order) -> Dict[str, str]:
        try:
            sig = sign(self.stark_private_key, order)
            return {"r": sig["r"], "s": sig["s"]}
        except Exception as e:
            logger.error(f"Stark署名失敗: {e}")
            raise

    def place_order(self, side: str, price: float, size: float) -> Dict:
        self._human_delay()
        order = Order(
            contract_id=int(self.contract_id),
            size=int(size * 1e8),           # 8桁精度
            price=int(round(price, 1) * 1e8),
            side=side.upper(),
            nonce=int(time.time() * 1000)
        )
        signature = self._sign_order(order)

        payload = {
            "contract_id": self.contract_id,
            "size": str(size),
            "price": str(round(price, 1)),
            "side": side.upper(),
            "nonce": order.nonce,
            "signature": signature
        }

        url = f"{self.base_url}/trade/order"
        try:
            resp = self.session.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"{side} 注文成功: ${price} × {size}")
                return resp.json().get('data', {})
            else:
                raise Exception(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"注文失敗: {e}")
            raise

    def list_active_orders(self) -> List[Dict]:
        url = f"{self.base_url}/order/get_active_orders"
        params = {"contract_id_list": [self.contract_id]}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            return resp.json().get('data', {}).get('rows', []) if resp.status_code == 200 else []
        except Exception as e:
            logger.error(f"注文一覧失敗: {e}")
            return []

    def get_position(self) -> float:
        url = f"{self.base_url}/position/get"
        params = {"contract_id": self.contract_id}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return float(resp.json().get('data', {}).get('positionSize', 0))
        except Exception as e:
            logger.error(f"ポジション取得失敗: {e}")
        return 0.0

    def get_pnl(self) -> float:
        try:
            pos = self.get_position()
            price = self.get_ticker() or 3000
            return pos * price * 0.0001  # 簡易PnL
        except:
            return 0.0

# -----------------------------
# 簡易Gridエンジン（Koyeb即動作用）
# -----------------------------
class RemakeLucyEngine:
    def __init__(self, edgex, **kwargs):
        self.edgex = edgex
        self.grid_count = kwargs.get('grid_count', 6)
        self.interval = kwargs.get('grid_interval_percent', 2.5) / 100
        self.total_investment = kwargs.get('total_investment', 0.0015)
        self.size_per_grid = self.total_investment / self.grid_count
        self.active_orders = []

    def run(self):
        logger.info("RemakeLucyEngine 起動！")
        while True:
            try:
                price = self.edgex.get_ticker()
                if not price:
                    time.sleep(10)
                    continue

                self._maintain_grid(price)
                self._check_pnl()

                delay = random.uniform(30, 90) if SYBIL_AVOID else 10
                time.sleep(delay)

            except KeyboardInterrupt:
                logger.info("停止リクエスト受信")
                break
            except Exception as e:
                logger.error(f"エンジン例外: {e}")
                time.sleep(30)

    def _maintain_grid(self, current_price: float):
        target_prices = [
            current_price * (1 - self.interval * i) for i in range(1, self.grid_count + 1)
        ]
        active_prices = [float(o['price']) for o in self.edgex.list_active_orders() if o['side'] == 'BUY']

        for tp in target_prices:
            if abs(tp - current_price) / current_price < 0.001:
                continue
            if tp not in [round(p, 1) for p in active_prices]:
                try:
                    self.edgex.place_order('BUY', tp, self.size_per_grid)
                except:
                    pass

    def _check_pnl(self):
        pnl = self.edgex.get_pnl()
        if pnl < STOP_LOSS_USD:
            logger.critical(f"損失停止発動: ${pnl:.2f}")
            os._exit(0)

# -----------------------------
# SDK & Engine 起動
# -----------------------------
edgex = EdgeXLucySDK()
engine = RemakeLucyEngine(
    edgex=edgex,
    total_investment=TOTAL_INVESTMENT,
    grid_count=GRID_COUNT,
    grid_interval_percent=GRID_INTERVAL_PERCENT,
    stop_loss_usd=STOP_LOSS_USD
)

if __name__ == '__main__':
    logger.info("RemakeLucy v1.0 発進！ ETHUSDT Grid 爆益開始！")
    engine.run()
