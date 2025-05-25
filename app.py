import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json


with open('config.json', 'r') as file:
    config = json.load(file)

etherscan_key = config.get("ETHERSCAN_API_KEY")
eth_address = config.get("ETH_ADDRESS")
bybit_key = config.get("BYBIT_API_KEY")
bybit_secret = config.get("BYBIT_API_SECRET")
cryptopanic_token = config.get("CRYPTOPANIC_API_TOKEN")

st.set_page_config(page_title="Crypto Analytics & Trading", layout="wide")

menu = st.sidebar.radio("Меню", [
    "Dashboard",
    "Market Overview",
    "Trading Analysis",
    "Backtest",
    "Trade Monitor"
])

if menu == "Dashboard":
    import streamlit as st
    import requests
    import pandas as pd
    from datetime import datetime

    st.title("📊 Dashboard — Обзор кошелька Ethereum")


    @st.cache_data
    def get_transactions(address, api_key):
        url = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=txlist&address={address}"
            f"&startblock=0&endblock=99999999&sort=asc&apikey={api_key}"
        )
        r = requests.get(url).json()
        if r["status"] != "1":
            return pd.DataFrame()
        df = pd.DataFrame(r["result"])
        df["timeStamp"] = pd.to_datetime(df["timeStamp"], unit='s')
        df["value_eth"] = df["value"].astype(float) / 1e18
        df["direction"] = df["from"].apply(lambda x: "OUT" if x.lower() == address.lower() else "IN")
        return df


    txs = get_transactions(eth_address, etherscan_key)

    if txs.empty:
        st.error("Не удалось загрузить данные по кошельку.")
    else:
        latest_balance = txs["value_eth"].where(txs["direction"] == "IN", -txs["value_eth"]).cumsum().iloc[-1]
        weekly_change = txs[txs["timeStamp"] > (pd.Timestamp.now() - pd.Timedelta(days=7))]
        delta_weekly = weekly_change["value_eth"].where(weekly_change["direction"] == "IN",
                                                        -weekly_change["value_eth"]).sum()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Доходность за всё время", f"{latest_balance:.4f} ETH", delta=f"{delta_weekly:+.4f} ETH за 7д")
        with col2:
            st.metric("Капитал", f"${latest_balance * 3100:.2f}", delta=f"${delta_weekly * 3100:+.2f}")
        with col3:
            st.metric("Транзакций всего", f"{len(txs)}")

        st.subheader("📈 Equity Curve (баланс по времени)")
        txs["equity"] = txs["value_eth"].where(txs["direction"] == "IN", -txs["value_eth"]).cumsum()
        st.line_chart(txs.set_index("timeStamp")["equity"])

        st.subheader("📋 Последние транзакции")
        st.dataframe(
            txs[["timeStamp", "from", "to", "value_eth", "direction"]].sort_values("timeStamp", ascending=False).head(
                10),
            use_container_width=True
        )


elif menu == "Market Overview":
    st.title("🌐 Обзор рынка криптовалют")

    st.subheader("Котировки популярных криптовалют")

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,binancecoin,solana,ripple",
        "vs_currencies": "usd"
    }
    response = requests.get(url, params=params).json()

    coins_map = {
        "bitcoin": "BTC/USDT",
        "ethereum": "ETH/USDT",
        "binancecoin": "BNB/USDT",
        "solana": "SOL/USDT",
        "ripple": "XRP/USDT"
    }

    for key, label in coins_map.items():
        price = response.get(key, {}).get("usd", "N/A")
        st.write(f"**{label}**: ${price}")

    st.subheader("Индикаторы настроения")
    fear_greed = requests.get("https://api.alternative.me/fng/").json()
    value = int(fear_greed["data"][0]["value"])
    st.progress(value / 100)
    st.caption(f"Индекс настроения: {fear_greed['data'][0]['value_classification']} ({value}%)")

    st.subheader("Объёмы торгов (24ч)")

    volume_url = "https://api.coingecko.com/api/v3/coins/markets"
    volume_params = {
        "vs_currency": "usd",
        "ids": "bitcoin,ethereum,solana"
    }
    volumes_data = requests.get(volume_url, params=volume_params).json()

    volume_dict = {
        coin["symbol"].upper(): [coin["total_volume"]] for coin in volumes_data
    }
    st.bar_chart(volume_dict)

    st.subheader("Новости / события")

    CRYPTO_PANIC_API_KEY = cryptopanic_token

    news_url = "https://cryptopanic.com/api/v1/posts/"
    news_params = {
        "auth_token": CRYPTO_PANIC_API_KEY,
        "currencies": "BTC,ETH,SOL,XRP,BNB",
        "public": "true"
    }

    try:
        news_response = requests.get(news_url, params=news_params)
        news_response.raise_for_status()
        news_data = news_response.json()

        for post in news_data.get("results", [])[:5]:
            title = post.get("title", "Без заголовка")
            link = post.get("url", "#")
            published = post.get("published_at", "N/A")
            st.markdown(f"📰 [{title}]({link})\n\n<sub>{published}</sub>", unsafe_allow_html=True)

    except requests.RequestException as e:
        st.error("❌ Не удалось загрузить новости с CryptoPanic.")

elif menu == "Trading Analysis":
    st.title("📊 Trading Assistant (Streamlit)")


    def map_interval(interval):
        mapping = {
            "1m": "1",
            "2m": "3",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "60m": "60",
            "90m": "60",
            "1d": "D",
            "1wk": "W",
            "1mo": "M"
        }
        return mapping.get(interval, "D")


    @st.cache_data
    def load_tickers():
        try:
            res = requests.get("http://localhost:8000/tickers")
            return res.json() if res.status_code == 200 else ["AAPL", "BTC-USD"]
        except:
            return [
                "BTCUSDT",
                "ETHUSDT",
                "SOLUSDT",
                "DOGEUSDT",
                "BNBUSDT",
                "XRPUSDT",
                "ADAUSDT",
                "DOTUSDT",
                "LTCUSDT",
                "LINKUSDT"
            ]


    tickers = load_tickers()
    ticker = st.selectbox("Торговая пара", tickers)

    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox("Период данных", ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"],
                              index=2)
    with col2:
        interval = st.selectbox("Интервал",
                                ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1d", "5d", "1wk", "1mo", "3mo"],
                                index=7)

    st.markdown("### Индикаторы:")
    col1, col2, col3 = st.columns(3)
    with col1:
        show_sma = st.checkbox("SMA", value=True)
    with col2:
        show_ema = st.checkbox("EMA")
    with col3:
        show_rsi = st.checkbox("RSI")

    if st.button("📈 Показать график"):
        with st.spinner("Загружаем данные..."):
            interval_mapped = map_interval(interval)
            params = {
                "ticker": ticker,
                "period": period,
                "interval": interval_mapped,
                "show_sma": show_sma,
                "show_ema": show_ema,
                "show_rsi": show_rsi,
            }
            res = requests.get("http://localhost:8000/history", params=params)
            data = res.json()

            if data["dates"]:

                if data["prices"]:
                    current_price = data["prices"][-1]
                    previous_price = data["prices"][-2] if len(data["prices"]) >= 2 else current_price
                    price_delta = current_price - previous_price

                    col1, col2 = st.columns([1, 3])

                    with col1:
                        st.metric(
                            label=f"💵 Текущая цена {ticker}",
                            value=f"${current_price:.2f}",
                            delta=f"{price_delta:.2f}"
                        )

                    with col2:
                        st.line_chart(data["prices"][-30:])

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=data["dates"], y=data["prices"], name="Price", line=dict(color="white")))

                if show_sma and data["sma"]:
                    fig.add_trace(go.Scatter(x=data["dates"], y=data["sma"], name="SMA", line=dict(color="orange")))
                if show_ema and data["ema"]:
                    fig.add_trace(go.Scatter(x=data["dates"], y=data["ema"], name="EMA", line=dict(color="purple")))

                fig.update_layout(title=f"{ticker} Price", template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

                if show_rsi and data["rsi"]:
                    rsi_fig = go.Figure()
                    rsi_fig.add_trace(go.Scatter(x=data["dates"], y=data["rsi"], name="RSI", line=dict(color="green")))
                    rsi_fig.update_layout(title="RSI", template="plotly_dark", height=300)
                    st.plotly_chart(rsi_fig, use_container_width=True)

                st.success(f"📌 Рекомендация: **{data['recommendation'].upper()}**")
            else:
                st.error(f"⚠️ Ошибка: {data.get('recommendation', 'no data')}")
elif menu == "Backtest":
    st.title("🚀 Backtest Trading Bot")

    ticker = st.selectbox("Выбери актив", [
                "BTCUSDT",
                "ETHUSDT",
                "SOLUSDT",
                "DOGEUSDT",
                "BNBUSDT",
                "XRPUSDT",
                "ADAUSDT",
                "DOTUSDT",
                "LTCUSDT",
                "LINKUSDT"
            ])
    timeframe = st.selectbox("Таймфрейм", ["1m", "5m", "15m", "30m", "1h", "1d"])

    today = datetime.today()
    default_start = today - timedelta(days=90)

    start_date = st.date_input("Начальная дата", value=default_start)
    end_date = st.date_input("Конечная дата", value=today)

    if st.button("Запустить бэктест"):
        params = {
            "ticker": ticker,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "timeframe": timeframe
        }

        try:
            res = requests.get("http://localhost:8000/backtest", params=params)

            if res.status_code != 200:
                st.error(f"Ошибка: {res.json()['detail']}")
            else:
                result = res.json()

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=result["timestamps"], y=result["equity_curve"], name="Equity",
                                         line=dict(color="cyan")))
                fig.update_layout(title="📈 Кривая капитала", template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("📜 История сделок")
                st.dataframe(result["trade_history"])

                st.metric("💰 Финальный баланс", f"${result['final_balance']:.2f}")

        except Exception as e:
            st.error(f"Ошибка подключения к серверу: {e}")

elif menu == "Trade Monitor":
    import streamlit as st
    import requests
    import time
    import hmac
    import hashlib
    import pandas as pd

    API_KEY = bybit_key
    API_SECRET = bybit_secret


    def get_order_history(category="linear", limit=20):
        endpoint = "/v5/order/history"
        url = "https://api.bybit.com" + endpoint

        params = {
            "category": category,
            "limit": limit
        }

        timestamp = str(int(time.time() * 1000))
        recv_window = "10000"

        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        string_to_sign = f"{timestamp}{API_KEY}{recv_window}{query_string}"

        signature = hmac.new(
            API_SECRET.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-BAPI-API-KEY": API_KEY,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            return None, f"Ошибка запроса: {response.status_code}"

        data = response.json()
        if data["retCode"] != 0:
            return None, f"Ошибка API: {data['retMsg']}"

        return data["result"]["list"], None


    def get_transfer_history():
        endpoint = "/v5/account/wallet/transfer-list"
        url = "https://api.bybit.com" + endpoint

        params = {
            "accountType": "UNIFIED",
            "limit": 20
        }

        timestamp = str(int(time.time() * 1000))
        recv_window = "10000"

        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        string_to_sign = f"{timestamp}{API_KEY}{recv_window}{query_string}"

        signature = hmac.new(
            API_SECRET.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-BAPI-API-KEY": API_KEY,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            return None, f"Ошибка запроса: {response.status_code}"

        data = response.json()
        if data["retCode"] != 0:
            return None, f"Ошибка API: {data['retMsg']}"

        return data["result"]["list"], None


    def get_wallet_balance():
        endpoint = "/v5/account/wallet-balance"
        url = "https://api.bybit.com" + endpoint

        params = {
            "accountType": "UNIFIED"
        }

        timestamp = str(int(time.time() * 1000))
        recv_window = "10000"

        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        string_to_sign = f"{timestamp}{API_KEY}{recv_window}{query_string}"

        signature = hmac.new(
            API_SECRET.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-BAPI-API-KEY": API_KEY,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            return None, f"Ошибка запроса: {response.status_code}"

        data = response.json()
        if data["retCode"] != 0:
            return None, f"Ошибка API: {data['retMsg']}"

        return data["result"]["list"][0], None


    def get_wallet_balance_all_accounts():
        account_types = ["UNIFIED", "CONTRACT", "SPOT", "FUNDING"]
        results = {}

        for acc_type in account_types:
            endpoint = "/v5/account/wallet-balance"
            url = "https://api.bybit.com" + endpoint

            params = {
                "accountType": acc_type
            }

            timestamp = str(int(time.time() * 1000))
            recv_window = "10000"

            query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            string_to_sign = f"{timestamp}{API_KEY}{recv_window}{query_string}"

            signature = hmac.new(
                API_SECRET.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()

            headers = {
                "X-BAPI-API-KEY": API_KEY,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window,
                "X-BAPI-SIGN": signature,
                "Content-Type": "application/json"
            }

            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                if data["retCode"] == 0 and data["result"]["list"]:
                    results[acc_type] = data["result"]["list"][0]["coin"]
                else:
                    results[acc_type] = []
            else:
                results[acc_type] = f"Ошибка {response.status_code}"

        return results


    st.header("💼 Trade Monitor — Баланс, Транзакции и Ордеры")

    tabs = st.tabs(["📊 Баланс", "📑 История ордеров"])

    with tabs[0]:
        st.subheader("💰 Балансы по всем типам аккаунтов")
        balances = get_wallet_balance_all_accounts()

        for acc_type, coins in balances.items():
            st.markdown(f"### 🧾 {acc_type} Account")
            if isinstance(coins, str):
                st.error(coins)
            elif not coins:
                st.info("Нет средств.")
            else:
                df = pd.DataFrame(coins)
                df = df[df["walletBalance"].astype(float) > 0]
                df["walletBalance"] = df["walletBalance"].astype(float)
                df["unrealisedPnl"] = df["unrealisedPnl"].astype(float)
                df["usdValue"] = df["usdValue"].astype(float)
                st.dataframe(df[["coin", "walletBalance", "usdValue", "unrealisedPnl"]])

    with tabs[1]:
        st.subheader("📑 История ордеров (последние 20)")
        with st.spinner("Загружаем историю ордеров..."):
            orders, error = get_order_history()

        if error:
            st.error(error)
        elif not orders:
            st.info("История ордеров пуста.")
        else:
            import pandas as pd

            df = pd.DataFrame(orders)
            df["createdTime"] = pd.to_datetime(df["createdTime"].astype(int), unit="ms")
            df["updatedTime"] = pd.to_datetime(df["updatedTime"].astype(int), unit="ms")
            columns_to_show = ["symbol", "side", "orderType", "price", "qty", "orderStatus", "createdTime"]
            st.dataframe(df[columns_to_show].sort_values("createdTime", ascending=False))
