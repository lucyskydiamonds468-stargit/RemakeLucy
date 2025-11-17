# -*- coding: utf-8 -*-
"""
RemakeLucy v1.0 - グロック完全リメイク版
ETHUSDT Grid + 全損ゼロ + シビル回避 + 爆益増進
"""

import os
import logging
from bot.grid_engine import RemakeLucyEngine
from bot.adapters.edgex_sdk import EdgeXLucySDK

# ログ設定
logging.basicConfig(level=logging.INFO)
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

# SDK初期化
edgex = EdgeXLucySDK(
    api_key=os.getenv('BYBIT_API_KEY'),
    secret=os.getenv('BYBIT_SECRET'),
    stark_private_key=os.getenv('EDGEX_STARK_PRIVATE_KEY'),
    account_id=os.getenv('EDGEX_ACCOUNT_ID'),
    symbol=SYMBOL
)

# Engine起動
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
