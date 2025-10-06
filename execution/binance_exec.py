from __future__ import annotations
import hmac, hashlib, time
from typing import Optional
import httpx
from main.models import OrderRequest, OrderType, OrderSide, Fill
from main.utils import now_ms

BINANCE_BASE = "https://api.binance.com"

class BinanceRestExec:
    """Very small subset of Binance Spot REST for live Binance Spot trading."""

    def __init__(self, api_key: str, api_secret: str, base_url: str = BINANCE_BASE):
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.base = base_url
        self._client = httpx.Client(base_url=self.base, timeout=10.0)

    def _sign(self, qs: str) -> str:
        return hmac.new(self.api_secret, qs.encode(), hashlib.sha256).hexdigest()

    def _headers(self):
        return {"X-MBX-APIKEY": self.api_key}

    def place_order(self, order: OrderRequest) -> Optional[Fill]:
        assert order.order_type in (OrderType.MARKET, OrderType.LIMIT)
        side = order.side.value
        typ = order.order_type.value
        ts = int(time.time() * 1000)

        params = {
            "symbol": order.symbol.upper(),
            "side": side,
            "type": typ,
            "quantity": f"{abs(order.qty):.10f}",
            "timestamp": ts,
            "newClientOrderId": order.client_id or ""
        }
        if order.order_type == OrderType.LIMIT:
            params.update({"price": f"{order.price:.8f}", "timeInForce": "GTC"})

        qs = "&".join(f"{k}={v}" for k, v in params.items() if v != "")
        sig = self._sign(qs)
        url = "/api/v3/order" + f"?{qs}&signature={sig}"

        r = self._client.post(url, headers=self._headers())
        if r.status_code != 200:
            # surface error to the caller
            raise RuntimeError(f"Binance order error: {r.status_code} {r.text}")
        data = r.json()
        # Map the response to a Fill-like object where possible
        px = None
        if order.order_type == OrderType.MARKET:
            # For MARKET orders, price is not guaranteed in response; best-effort: cummulativeQuoteQty/qty
            try:
                cqq = float(data.get("cummulativeQuoteQty", 0))
                qty = float(data.get("executedQty", 0))
                if qty > 0:
                    px = cqq / qty
            except Exception:
                px = None
        px = px or order.price or 0.0
        fill_qty = order.qty if order.side == OrderSide.BUY else -abs(order.qty)
        return Fill(symbol=order.symbol, side=order.side, qty=fill_qty, price=px, ts_ms=now_ms(), client_id=order.client_id, order_id=str(data.get("orderId")))
