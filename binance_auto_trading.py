import ccxt 
import time
import pandas as pd
import math
import qortjf_slacker

api_key = "yours"
secret  = "yours"
myToken = "yours"

binance = ccxt.binance(config={
 'apiKey': api_key, 
 'secret': secret,
 'enableRateLimit': True,
 
 'options': {
     'defaultType': 'future',
        }
})

position = {
 "amount" : 0
}

turn = {
    "type" : None,
    "message" : None
}

error = 0 

symbol="BTC/USDT"


## 레버리지 설정
markets = binance.load_markets()

market = binance.market(symbol)
leverage = 13

resp = binance.fapiPrivate_post_leverage({
    'symbol': market['id'],
    'leverage': leverage
})


## 비트코인 진입 가격 평균 구하기
balance = binance.fetch_balance()
positions = balance['info']['positions']

for ps in positions:
		if ps['symbol'] == 'BTCUSDT':
		  entry_price = ps['entryPrice']

entry_price = float(entry_price)


## RSI 
def rsi_calc(ohlc: pd.DataFrame, period: int = 14):
  ohlc = ohlc[4].astype(float)
  delta = ohlc.diff()
  gains, declines = delta.copy(), delta.copy()
  gains[gains < 0] = 0
  declines[declines > 0] = 0

  _gain = gains.ewm(com=(period-1), min_periods=period).mean()
  _loss = declines.abs().ewm(com=(period-1), min_periods=period).mean()

  RS = _gain / _loss
  return pd.Series(100-(100/(1+RS)), name="RSI")

def rsi_binance(itv='1h', simbol='BTC/USDT'):
  ohlcv = binance.fetch_ohlcv(symbol="BTC/USDT", timeframe=itv, limit=200)
  df = pd.DataFrame(ohlcv)
  rsi = rsi_calc(df,14).iloc[-1]
  return rsi
 

## 33%로 포지션 매수/매도 수량 설정
def cal_amount(usdt_balance, current_price):
    portion = 0.33 ## (자산의 몇 % 투자 비율, 현재 33%)
    usdt_trade = usdt_balance * portion
    amount = math.floor((usdt_trade * 1000000)/current_price) / 1000000 *13
    return amount 


## 트레일링 스탑 마켓 롱/ 숏 진입 함수
def enter_position(symbol, RSI, amount, position):

  if RSI <= 30:
      position['amount'] = amount
      binance.create_market_buy_order(symbol=symbol, amount=amount)
      balance = binance.fetch_balance()
      positions = balance['info']['positions']
      for ps in positions:
                  if ps['symbol'] == 'BTCUSDT':
                      entry_price = ps['entryPrice']
                      entry_price = float(entry_price)
      side = 'sell'
      order_type = 'TRAILING_STOP_MARKET'
      rate = '0.7' ## (callbackRate 비율, 현재 0.7%)
      price = None
      params = {'stopPrice': entry_price, 'callbackRate': rate, 'reduceOnly': True}
      binance.create_order(symbol, order_type, side, amount, price, params)
      
  elif RSI >= 69:
      position['amount'] = amount
      binance.create_market_sell_order(symbol=symbol, amount=amount)
      balance = binance.fetch_balance()
      positions = balance['info']['positions']
      for ps in positions:
                  if ps['symbol'] == 'BTCUSDT':
                      entry_price = ps['entryPrice']
                      entry_price = float(entry_price)
      side = 'buy'
      order_type = 'TRAILING_STOP_MARKET'
      rate = '0.9'
      price = None
      params = {'stopPrice': entry_price, 'callbackRate': rate, 'reduceOnly': True}
      binance.create_order(symbol, order_type, side, amount, price, params)


while True:
  try:
 ## 잔고조회
     balance=binance.fetch_balance()
     usdt=balance['total']['USDT']

     resp = binance.fetch_open_orders(symbol)

 ## 현재가 조회
     ticker=binance.fetch_ticker(symbol)
     current_price = ticker['last']

 ## 매수/매도 수량 조회
     amount = cal_amount(usdt, current_price)

 ## RSI 1분봉 기준
     RSI= rsi_binance(itv='1m')

 ## 중복 구매 방지
     if len(resp) == 0:
         turn['type'] = 'None'
         turn['message'] = 'on'
     elif len(resp) != 0:
         turn['type'] = 'on'
         if turn['message'] is 'on':
             qortjf_slacker.post_message(myToken, "#qortjf", "현재가:" + str(current_price) + ", RSI:" + str(round(RSI, 2)) + ", 잔고:" + str(round(usdt, 2)) + ", 수익률:" + str(round(float(balance['info']['totalUnrealizedProfit']), 2)) + "USDT , 구매여부:" + str(turn['type']) + ", error_count:" + str(error))
             turn['message'] = 'None'
     
  ## 트레일링 스탑 시작
     if turn['type'] is 'None':
         enter_position(symbol, RSI, amount, position)
    
  
     print("현재가:", current_price, ", RSI:", round(RSI, 2), ", 잔고:", round(usdt, 2), ", 수익률:", round(float(balance['info']['totalUnrealizedProfit']), 2), "USDT , 구매여부:", turn['type'], " error_count:", error)
  
     time.sleep(1)

  except:      
  ## 예외 처리  
     error+=1
     qortjf_slacker.post_message(myToken, "#qortjf", "error:" + str(error))
     pass

     qortjf_slacker.post_message(myToken, "#qortjf", "restart")

     time.sleep(1)
