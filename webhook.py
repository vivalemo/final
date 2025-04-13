from fastapi import FastAPI, Request, Header, HTTPException
import hmac
import hashlib
import json

app = FastAPI()

API_SECRET = "your_oxapay_api_key"  # Замените на ваш OxaPay API ключ

@app.post("/oxapay/webhook")
async def handle_webhook(request: Request, hmac_header: str = Header(None)):
    body = await request.body()
    computed_hmac = hmac.new(
        API_SECRET.encode(), body, hashlib.sha512
    ).hexdigest()

    if hmac_header != computed_hmac:
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    data = json.loads(body)
    print("Получен вебхук:", data)

    # Здесь добавьте вашу логику обработки данных

    return {"status": "ok"}
