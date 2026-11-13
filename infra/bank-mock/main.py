"""Cổng thanh toán giả lập (docs/api.md mục 6), chỉ để chạy demo KT-04, KT-05; test không gọi.

Nhận yêu cầu thanh toán từ api, trả 202 ngay, rồi gọi lại `BANK_CALLBACK_URL` theo chế độ hiện tại:
SUCCESS, FAILED, SILENT (không gọi lại, để thu ngân tra soát), DUPLICATE (gửi SUCCESS hai lần).
"""

from __future__ import annotations

import os
from typing import Literal

import httpx
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

Mode = Literal["SUCCESS", "FAILED", "SILENT", "DUPLICATE"]

app = FastAPI(title="bank-mock")
state: dict[str, str] = {"mode": os.environ.get("BANK_MOCK_MODE", "SUCCESS")}


class PaymentRequest(BaseModel):
    txn_id: str
    type: str
    method: str
    amount: int


class ModeChange(BaseModel):
    mode: Mode


async def _call_back(txn_id: str, mode: str) -> None:
    result = "FAILED" if mode == "FAILED" else "SUCCESS"
    body = {"txn_id": txn_id, "result": result, "reference_code": f"REF-{txn_id}"}
    headers = {"X-Bank-Key": os.environ["BANK_KEY"]}
    async with httpx.AsyncClient(timeout=5) as http:
        for _ in range(2 if mode == "DUPLICATE" else 1):
            await http.post(os.environ["BANK_CALLBACK_URL"], json=body, headers=headers)


@app.post("/requests", status_code=202)
async def receive(body: PaymentRequest, tasks: BackgroundTasks) -> dict[str, str]:
    if state["mode"] != "SILENT":
        tasks.add_task(_call_back, body.txn_id, state["mode"])
    return {"mode": state["mode"]}


@app.put("/mode")
async def set_mode(body: ModeChange) -> dict[str, str]:
    state["mode"] = body.mode
    return state
