import schedule
import time
from src.database import init_db, get_strategies
from src.broker import Broker
import yfinance as yf


def heart_beat():
    # Healthcheck for Docker monitoring
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    broker = Broker()
    if not broker.api.get_clock().is_open:
        return

    strategies = get_strategies()
    for sym, p in strategies.items():
        if not broker.is_holding(sym):
            df = yf.download(sym, period="5d", interval="1h", progress=False)
            if df.empty:
                continue

            # ta is available via the pandas_ta extension
            adx = df.ta.adx().iloc[-1]['ADX_14']
            rsi = df.ta.rsi().iloc[-1]

            # The "Traffic Light" Logic
            if adx > p.get('adx_trend', 25) and rsi > p.get('rsi_trend', 50):
                broker.buy_bracket(sym, 1, p['target'], p['stop'])


if __name__ == "__main__":
    init_db()
    print("🚀 Heart Beat Started...")
    schedule.every(1).minutes.do(heart_beat)
    while True:
        schedule.run_pending()
        time.sleep(1)