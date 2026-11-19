"""
Service for simulating live market tick streaming over the RealtimeGateway WebSocket.
Provides streaming market quotes and order book depth ladders for active dashboard subscriptions.
"""
import asyncio
import logging
import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional

from backend.app.modules.infrastructure_platform.realtime_api.gateway import gateway
from backend.app.modules.infrastructure_platform.realtime_api.schemas.message_schemas import (
    RealtimeChannelType,
)
from backend.app.modules.market_data_ingestion.adapters.yfinance.adapter import YFinanceMarketDataAdapter

logger = logging.getLogger("m15_02.market_streamer")

class MarketStreamerService:
    def __init__(self):
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._base_cache: Dict[str, Dict[str, Any]] = {}

    def start_streaming_for_resource(self, symbol_or_id: str, levels_count: int = 5):
        clean_sym = YFinanceMarketDataAdapter._clean_symbol(symbol_or_id)
        task_key = f"{clean_sym}:{levels_count}"
        if task_key not in self._active_tasks or self._active_tasks[task_key].done():
            self._active_tasks[task_key] = asyncio.create_task(
                self._stream_loop(symbol_or_id, clean_sym, levels_count)
            )

    def stop_streaming_for_resource(self, symbol_or_id: str, levels_count: int = 5):
        clean_sym = YFinanceMarketDataAdapter._clean_symbol(symbol_or_id)
        task_key = f"{clean_sym}:{levels_count}"
        task = self._active_tasks.pop(task_key, None)
        if task and not task.done():
            task.cancel()

    async def _stream_loop(self, raw_id: str, clean_sym: str, levels_count: int):
        stream_id = f"mkt-{clean_sym}"
        try:
            # 1. Fetch real live quote from yfinance adapter
            init_quote = None
            try:
                init_quote = await asyncio.wait_for(YFinanceMarketDataAdapter.get_live_quote(clean_sym), timeout=4.0)
            except Exception:
                pass

            if not init_quote:
                init_quote = {
                    "symbol": clean_sym,
                    "best_bid": Decimal("150.00"),
                    "best_ask": Decimal("150.25"),
                    "mid_price": Decimal("150.125"),
                    "spread_bps": Decimal("8.32"),
                    "currency": "USD" if not (clean_sym.endswith(".NS") or clean_sym.endswith(".BO")) else "INR",
                }

            current_mid = float(init_quote.get("mid_price", 150.0))
            best_bid_base = float(init_quote.get("best_bid", current_mid - 0.05))
            best_ask_base = float(init_quote.get("best_ask", current_mid + 0.05))
            if best_bid_base >= best_ask_base:
                best_ask_base = best_bid_base + 0.05
            stable_spread_abs = round(best_ask_base - best_bid_base, 2)
            currency = init_quote.get("currency", "USD")

            # Check if active Upstox stream has real exchange L2 quotes for this instrument
            from backend.app.modules.upstox_integration.stream import stream as upstox_stream
            from backend.app.modules.upstox_integration.service import normalize_quote

            # Tick size resolution: ₹0.01 for Indian equities (NSE/BSE), $0.01 for US
            is_indian_asset = clean_sym.endswith(".NS") or clean_sym.endswith(".BO") or "NSE" in raw_id
            tick_size = 0.01

            tick_counter = 0

            while True:
                # Check active subscriptions
                subscribers = gateway.subscription_manager.get_matching_connections(
                    channel=RealtimeChannelType.MARKET,
                    resource_id=clean_sym,
                    event_type="market.orderbook.depth",
                )
                raw_subs = gateway.subscription_manager.get_matching_connections(
                    channel=RealtimeChannelType.MARKET,
                    resource_id=raw_id,
                    event_type="market.orderbook.depth",
                )
                if not subscribers and not raw_subs:
                    logger.debug(f"No active subscribers for {clean_sym}. Pausing stream loop.")
                    break

                now_iso = datetime.now(timezone.utc).isoformat()

                # Check if real Upstox stream has fresh L2 depth
                upstox_match = None
                if upstox_stream and upstox_stream.state == 'CONNECTED':
                    for k, q in upstox_stream.quotes.items():
                        if clean_sym in k or raw_id in k or k.endswith(clean_sym):
                            upstox_match = normalize_quote(k, q)
                            break

                if upstox_match and upstox_match.get('bids') and upstox_match.get('asks'):
                    # Use authentic exchange L2 order book directly
                    bids = []
                    cum_b = 0.0
                    for idx, b in enumerate(upstox_match['bids'][:levels_count]):
                        p, q_val = float(b['price']), float(b['quantity'])
                        notional = round(p * q_val, 2)
                        cum_b += notional
                        bids.append({
                            "level_index": idx + 1,
                            "price": p,
                            "quantity": int(q_val),
                            "notional": notional,
                            "distance_bps": round(abs(float(upstox_match['midpoint']) - p) / float(upstox_match['midpoint']) * 10000, 2) if upstox_match.get('midpoint') else 0.0,
                            "order_count": b.get('orders', 1),
                        })

                    asks = []
                    cum_a = 0.0
                    for idx, a in enumerate(upstox_match['asks'][:levels_count]):
                        p, q_val = float(a['price']), float(a['quantity'])
                        notional = round(p * q_val, 2)
                        cum_a += notional
                        asks.append({
                            "level_index": idx + 1,
                            "price": p,
                            "quantity": int(q_val),
                            "notional": notional,
                            "distance_bps": round(abs(p - float(upstox_match['midpoint'])) / float(upstox_match['midpoint']) * 10000, 2) if upstox_match.get('midpoint') else 0.0,
                            "order_count": a.get('orders', 1),
                        })

                    total_bid_qty = sum(b['quantity'] for b in bids)
                    total_ask_qty = sum(a['quantity'] for a in asks)
                    total_bid_notional = sum(b['notional'] for b in bids)
                    total_ask_notional = sum(a['notional'] for a in asks)
                    cum_bid_notional = [round(sum(b['notional'] for b in bids[:i+1]), 2) for i in range(len(bids))]
                    cum_ask_notional = [round(sum(a['notional'] for a in asks[:i+1]), 2) for i in range(len(asks))]
                    imbalance = upstox_match.get('bid_ask_imbalance', 0.0) or 0.0
                    venue_tag = "UPSTOX/NSE_L2"
                    current_mid = float(upstox_match['midpoint'])
                    best_bid = float(upstox_match['best_bid'])
                    best_ask = float(upstox_match['best_ask'])
                    stable_spread_abs = float(upstox_match['spread'])
                    actual_bps = float(upstox_match['spread_bps'])

                else:
                    # Synthetic empirical order book with realistic live tick dynamics
                    tick_counter += 1
                    # Small live price tick shifts (e.g. +$0.01 / -$0.01 or +₹0.05 / -₹0.05) every tick
                    tick_step = 0.05 if is_indian_asset else 0.01
                    tick_dir = random.choice([-tick_step, 0.0, tick_step, tick_step, -tick_step])
                    best_bid_base = round(best_bid_base + tick_dir, 2)
                    best_ask_base = round(best_bid_base + stable_spread_abs, 2)
                    current_mid = round((best_bid_base + best_ask_base) / 2.0, 3)

                    best_bid = best_bid_base
                    best_ask = best_ask_base
                    actual_bps = round((stable_spread_abs / current_mid) * 10000.0, 2)

                    bids = []
                    asks = []
                    total_bid_qty = 0
                    total_ask_qty = 0
                    total_bid_notional = 0.0
                    total_ask_notional = 0.0
                    cum_bid_notional = []
                    cum_ask_notional = []

                    # Realistic distribution per level (non-pyramidal quantities with continuous live tick fluctuations)
                    level_quantities_b = [357, 2130, 2594, 1435, 1454, 1850, 2200, 2900, 3100, 3400]
                    level_quantities_a = [52, 302, 1040, 2138, 1955, 1720, 2050, 2800, 3050, 3350]

                    for i in range(1, levels_count + 1):
                        # Consecutive 1-tick price steps: e.g. 351.52, 351.51, 351.50...
                        bid_p = round(best_bid - ((i - 1) * tick_step), 2)
                        ask_p = round(best_ask + ((i - 1) * tick_step), 2)

                        base_bq = level_quantities_b[(i - 1) % len(level_quantities_b)]
                        base_aq = level_quantities_a[(i - 1) % len(level_quantities_a)]

                        # Visible live queue fluctuation on resting limit orders
                        b_qty = max(10, base_bq + random.randint(-45, 45))
                        a_qty = max(10, base_aq + random.randint(-45, 45))

                        b_notional = round(bid_p * b_qty, 2)
                        a_notional = round(ask_p * a_qty, 2)

                        total_bid_qty += b_qty
                        total_ask_qty += a_qty
                        total_bid_notional += b_notional
                        total_ask_notional += a_notional
                        cum_bid_notional.append(round(total_bid_notional, 2))
                        cum_ask_notional.append(round(total_ask_notional, 2))

                        dist_b_bps = round(abs(current_mid - bid_p) / current_mid * 10000, 2)
                        dist_a_bps = round(abs(ask_p - current_mid) / current_mid * 10000, 2)

                        bids.append({
                            "level_index": i,
                            "price": bid_p,
                            "quantity": b_qty,
                            "notional": b_notional,
                            "distance_bps": dist_b_bps,
                            "order_count": max(1, i * 3 + random.randint(-1, 2)),
                        })
                        asks.append({
                            "level_index": i,
                            "price": ask_p,
                            "quantity": a_qty,
                            "notional": a_notional,
                            "distance_bps": dist_a_bps,
                            "order_count": max(1, i * 3 + random.randint(-1, 2)),
                        })

                    denom = total_bid_qty + total_ask_qty
                    imbalance = round((total_bid_qty - total_ask_qty) / denom, 4) if denom > 0 else 0.0
                    venue_tag = "SIMULATED"
                imb_status = "BALANCED"
                if imbalance > 0.20:
                    imb_status = "BID_HEAVY"
                elif imbalance < -0.20:
                    imb_status = "ASK_HEAVY"

                # 1. Publish depth ladder event
                depth_payload = {
                    "source_kind": "PROVIDER_REPORTED" if venue_tag.startswith("UPSTOX") else "SIMULATED",
                    "quality_status": "PROVIDER_REPORTED" if venue_tag.startswith("UPSTOX") else "SIMULATED",
                    "source_timestamp": upstox_match.get('timestamp') if venue_tag.startswith("UPSTOX") else None,
                    "instrument_id": raw_id,
                    "symbol": clean_sym,
                    "snapshot_timestamp": (upstox_match.get('timestamp') or now_iso) if venue_tag.startswith("UPSTOX") else now_iso,
                    "bids": bids,
                    "asks": asks,
                    "total_bid_quantity": total_bid_qty,
                    "total_ask_quantity": total_ask_qty,
                    "total_bid_notional": total_bid_notional,
                    "total_ask_notional": total_ask_notional,
                    "cumulative_bid_notional": cum_bid_notional,
                    "cumulative_ask_notional": cum_ask_notional,
                    "depth_imbalance": imbalance,
                    "imbalance_status": imb_status,
                    "is_stale": False,
                    "venue": venue_tag,
                    "currency": currency,
                }

                # 2. Publish top-of-book quote event
                quote_payload = {
                    "source_kind": "PROVIDER_REPORTED" if venue_tag.startswith("UPSTOX") else "SIMULATED",
                    "source_timestamp": upstox_match.get('timestamp') if venue_tag.startswith("UPSTOX") else None,
                    "timestamp_basis": "Provider exchange timestamp" if venue_tag.startswith("UPSTOX") else "Generated demo update",
                    "instrument_id": raw_id,
                    "symbol": clean_sym,
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "mid_price": current_mid,
                    "spread_abs": stable_spread_abs,
                    "spread_rel": round(stable_spread_abs / current_mid, 6),
                    "spread_bps": actual_bps,
                    "quote_condition": "NORMAL",
                    "observation_timestamp": now_iso,
                    "venue": venue_tag,
                    "currency": currency,
                }

                # Publish to both canonical and raw resource IDs
                for target_res in set([clean_sym, raw_id]):
                    await gateway.publish_event(
                        channel=RealtimeChannelType.MARKET,
                        event_type="market.orderbook.depth",
                        resource_id=target_res,
                        stream_id=stream_id,
                        payload=depth_payload,
                        producer_module="M15_MARKET_STREAMER",
                    )
                    await gateway.publish_event(
                        channel=RealtimeChannelType.MARKET,
                        event_type="market.quote",
                        resource_id=target_res,
                        stream_id=stream_id,
                        payload=quote_payload,
                        producer_module="M15_MARKET_STREAMER",
                    )

                # Calm institutional tick cadence (every 2.5 seconds)
                await asyncio.sleep(2.5)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in stream loop for {clean_sym}: {e}", exc_info=True)


market_streamer = MarketStreamerService()
