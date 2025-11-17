# -*- coding: utf-8 -*-
"""
EdgeXLucySDK - グロック強化版
ETHUSDT専用 + シビル回避 + エラー耐性
"""

import requests
import time
import logging
import random
from typing import Dict, Any, Optional

# ロガー設定
logger = logging.getLogger(__name__)


class EdgeXLucySDK:
    """
    EdgeX API ラッパー
    - レートリミット（429）対策
    - 再試行ロジック
    - 人間らしい遅延
    """

    def __init__(
        self,
        api_key: str,
        secret: str,
        stark_private_key: str,
        account_id: str,
        symbol: str = "ETHUSDT",
        contract_id: str = "10001",
        base_url: str = "https://pro.edgex.exchange/api/v1",
    ):
        self.api_key = api_key
        self.secret = secret
        self.stark_private_key = stark_private_key
        self.account_id = account_id
        self.symbol = symbol
        self.contract_id = contract_id
        self.base_url = base_url

        logger.info(f"EdgeXLucySDK 初期化完了: SYMBOL={self.symbol}, contract_id={self.contract_id}")

    # --------------------------------------------------------------------- #
    # ティッカー取得（再試行 + レートリミット対策）
    # --------------------------------------------------------------------- #
    def get_ticker(self) -> Optional[Dict[str, float]]:
        url = f"{self.base_url}/public/quote/getTicker?contractId={self.contract_id}"
        for attempt in range(1, 4):
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    price = float(data.get("lastPrice", 0))
                    logger.debug(f"ティッカー取得成功: ${price}")
                    return {"price": price}

                if resp.status_code == 429:
                    wait = random.uniform(60, 120)
                    logger.warning(f"429 Rate Limit → {wait:.1f}s 待機中...")
                    time.sleep(wait)
                    continue  # 再試行

                logger.error(f"ティッカー取得失敗: HTTP {resp.status_code} - {resp.text}")

            except Exception as e:
                logger.error(f"ティッカー取得例外 (試行 {attempt}/3): {e}")
                time.sleep(5)

        logger.error("ティッカー取得失敗: 最大試行回数超過")
        return None

    # --------------------------------------------------------------------- #
    # 注文発注（人間らしい遅延 + エラーハンドリング）
    # --------------------------------------------------------------------- #
    def place_order(self, side: str, price: float, size: float) -> Dict[str, Any]:
        time.sleep(random.uniform(0.5, 2.0))  # 人間らしさ演出

        payload = {
            "contract_id": self.contract_id,
            "size": str(size),
            "price": str(round(price, 1)),
            "side": side,
        }
        url = f"{self.base_url}/trade/order"

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                result = resp.json().get("data", {})
                logger.info(f"{side} 注文成功: 価格=${price}, サイズ={size}")
                return result

            raise Exception(f"order failed: HTTP {resp.status_code} - {resp.text}")

        except Exception as e:
            logger.error(f"注文エラー: {e}")
            raise

    # --------------------------------------------------------------------- #
    # アクティブ注文一覧
    # --------------------------------------------------------------------- #
    def list_active_orders(self) -> list:
        params = {"contract_id_list": [self.contract_id]}
        url = f"{self.base_url}/order/get_active_orders"
        try:
            resp = requests.get(url, params=params, timeout=10)
            return resp.json().get("data", {}).get("rows", []) if resp.status_code == 200 else []
        except Exception as e:
            logger.error(f"アクティブ注文取得失敗: {e}")
            return []

    # --------------------------------------------------------------------- #
    # ポジション（モック）
    # --------------------------------------------------------------------- #
    def get_position(self) -> Dict[str, float]:
        return {"net_size": 0.0}

    # --------------------------------------------------------------------- #
    # 損益（モック）
    # --------------------------------------------------------------------- #
    def get_pnl(self) -> float:
        return 0.0
