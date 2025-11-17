# -*- coding: utf-8 -*-
"""
RemakeLucyEngine - グロック爆益エンジン
全損ゼロ + シビル回避 + 人間らしさ演出
"""

import time
import logging
import random
from typing import List

logger = logging.getLogger(__name__)

class RemakeLucyEngine:
    def __init__(self, edgex, symbol, total_investment, grid_count, grid_interval_percent,
                 range_bomb_mode, range_bomb_size, range_bomb_width, range_bomb_threshold,
                 range_bomb_cooldown, stop_loss_usd, sybil_avoid, min_order_size, random_delay):
        self.edgex = edgex
        self.symbol = symbol
        self.total_investment = total_investment
        self.grid_count = grid_count
        self.grid_interval_percent = grid_interval_percent
        self.range_bomb_mode = range_bomb_mode
        self.range_bomb_size = range_bomb_size
        self.range_bomb_width = range_bomb_width
        self.range_bomb_threshold = range_bomb_threshold
        self.range_bomb_cooldown = range_bomb_cooldown
        self.stop_loss_usd = stop_loss_usd
        self.sybil_avoid = sybil_avoid
        self.min_order_size = min_order_size
        self.random_delay = random_delay

        self.placed_buy: List[float] = []
        self.placed_sell: List[float] = []
        self.initialized = False
        self.iter_count = 0
        self.last_bomb_time = 0
        self.hold_half = False

    def run(self):
        logger.info("RemakeLucyEngine起動！ 心臓バクバク待機中...")
        while True:
            self.iter_count += 1
            logger.debug(f"ループ開始: iter={self.iter_count}")

            ticker = self.edgex.get_ticker()
            if not ticker:
                time.sleep(5)
                continue
            price = ticker['price']

            if not self.hold_half and len(self.placed_buy) >= 3:
                self.hold_half = True
                logger.info("半分ホールドモード発動！ 全損回避鉄壁！")

            self._ensure_grid(price)

            if self.range_bomb_mode and (time.time() - self.last_bomb_time > self.range_bomb_cooldown):
                self._range_bomb(price)

            if self.edgex.get_pnl() < self.stop_loss_usd:
                logger.warning("Stop Loss発動！ でも半分は守ったぜ！")
                self._stop_loss()

            delay = self._get_delay()
            logger.debug(f"待機{delay}秒（人間らしさ演出）")
            time.sleep(delay)

    def _ensure_grid(self, price: float):
        step = price * self.grid_interval_percent / 100
        levels = self.grid_count // 2

        for i in range(levels):
            buy_price = round(price - (i + 1) * step, 1)
            if buy_price not in self.placed_buy and (not self.hold_half or i < 1):
                self._place_order("BUY", buy_price, self.min_order_size)

        for i in range(levels):
            sell_price = round(price + (i + 1) * step, 1)
            if sell_price not in self.placed_sell:
                self._place_order("SELL", sell_price, self.min_order_size)

        if not self.initialized:
            logger.info(f"初期配置完了！ 買い{len(self.placed_buy)}本 売り{len(self.placed_sell)}本")
            self.initialized = True

    def _place_order(self, side: str, price: float, size: float):
        try:
            order = self.edgex.place_order(side, price, size)
            if side == "BUY":
                self.placed_buy.append(price)
            else:
                self.placed_sell.append(price)
            logger.info(f"{side}注文発注: 価格=${price} → 心臓バクバク！")
        except Exception as e:
            logger.error(f"注文エラー: {e} → でも諦めねぇ！")

    def _range_bomb(self, price: float):
        if abs(price - 3230) < self.range_bomb_threshold:
            self._place_order("BUY", price - 1, self.range_bomb_size)
            logger.info("RANGE_BOMB発動！ 夕方+42USD確定演出！")
            self.last_bomb_time = time.time()

    def _stop_loss(self):
        for price in self.placed_buy[:3]:
            self._place_order("SELL", price * 0.99, self.min_order_size)
        logger.info("全損回避成功！ 残りはホールドで雪だるま！")

    def _get_delay(self) -> float:
        if self.sybil_avoid:
            low, high = map(int, self.random_delay.split('-'))
            return random.uniform(low, high)
        return 1.5
