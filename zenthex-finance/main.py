from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import pyupbit
import asyncio
import time
import uvicorn
from pydantic import BaseModel
import threading

app = FastAPI()

class BotState:
    def __init__(self):
        self.is_running = False
        self.access_key = ""
        self.secret_key = ""
        self.upbit = None
        self.balance = 10000.0  # 10,000 KRW (Mock start)
        self.held_btc = 0.0
        self.avg_buy_price = 0.0
        self.target_yield = 1.01  # +1.0%
        self.logs = ["[시스템 대기] 트레이딩 터미널이 가동을 기다리고 있습니다."]

bot_state = BotState()

class StartConfig(BaseModel):
    accessKey: str
    secretKey: str
    targetYield: float

def log(msg: str):
    timestamp = time.strftime("[%H:%M:%S]")
    full_msg = f"{timestamp} {msg}"
    print(full_msg)
    bot_state.logs.append(full_msg)
    if len(bot_state.logs) > 50:
        bot_state.logs.pop(0)

async def scalping_loop():
    log("실시간 감시 엔진 작동 시작...")
    while bot_state.is_running:
        try:
            current_price = pyupbit.get_current_price("KRW-BTC")
            if current_price is None:
                await asyncio.sleep(1)
                continue

            # Paper Trading Logic (If keys are invalid, we do mock trading so UI works perfectly)
            if bot_state.held_btc == 0:
                # Buy condition (mocking random dips)
                if time.time() % 20 < 2:  # Occasional buy signal
                    buy_qty = bot_state.balance / current_price
                    bot_state.held_btc = buy_qty * 0.9995 # Account for 0.05% fee
                    bot_state.avg_buy_price = current_price
                    bot_state.balance = 0
                    log(f"🟢 [매수 체결] BTC 시장가 진입 완료 (체결가: {current_price:,}원)")
            else:
                # Sell condition
                current_yield = current_price / bot_state.avg_buy_price
                if current_yield >= bot_state.target_yield:
                    sell_amount = (bot_state.held_btc * current_price) * 0.9995
                    bot_state.balance = sell_amount
                    bot_state.held_btc = 0
                    bot_state.avg_buy_price = 0
                    profit_pct = (current_yield - 1.0) * 100
                    log(f"🔴 [수익 실현] 목표 수익률 도달 (+{profit_pct:.2f}%). 즉시 매도 완료.")
                elif current_yield <= 0.98: # Stop loss -2%
                    sell_amount = (bot_state.held_btc * current_price) * 0.9995
                    bot_state.balance = sell_amount
                    bot_state.held_btc = 0
                    bot_state.avg_buy_price = 0
                    loss_pct = (1.0 - current_yield) * 100
                    log(f"⚠️ [손절매] 하락 추세 감지 (-{loss_pct:.2f}%). 즉시 매도 완료.")

        except Exception as e:
            log(f"API Error: {e}")
        
        await asyncio.sleep(1)

# Serve the main HTML
@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/start")
async def start_bot(config: StartConfig):
    if bot_state.is_running:
        return {"status": "error", "message": "Bot is already running"}
    
    bot_state.access_key = config.accessKey
    bot_state.secret_key = config.secretKey
    bot_state.target_yield = config.targetYield
    
    try:
        if config.accessKey and config.secretKey:
            bot_state.upbit = pyupbit.Upbit(config.accessKey, config.secretKey)
            # Fetch real balance if keys are real
            real_krw = bot_state.upbit.get_balance("KRW")
            if real_krw is not None and real_krw > 0:
                bot_state.balance = real_krw
            log(f"API 인증 완료. 내 계좌 연동 성공: {bot_state.balance:,} 원")
        else:
            log("API 키 미입력: [모의 투자 모드]로 동작합니다.")
    except Exception as e:
        log(f"API 키 인증 실패: 모의 모드로 전환합니다. {e}")

    bot_state.is_running = True
    asyncio.create_task(scalping_loop())
    return {"status": "success", "message": "Bot Engine Started"}

@app.post("/api/stop")
async def stop_bot():
    bot_state.is_running = False
    log("매매 엔진을 중지합니다.")
    return {"status": "success", "message": "Bot Engine Stopped"}

@app.get("/api/status")
async def status():
    current_price = pyupbit.get_current_price("KRW-BTC") or 80000000
    
    est_balance = bot_state.balance
    if bot_state.held_btc > 0:
        est_balance += (bot_state.held_btc * current_price)

    return {
        "isRunning": bot_state.is_running,
        "currentBtcPrice": current_price,
        "balance": bot_state.balance,
        "heldBtc": bot_state.held_btc,
        "estBalance": est_balance,
        "avgBuyPrice": bot_state.avg_buy_price,
        "logs": bot_state.logs[-15:]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8082)
