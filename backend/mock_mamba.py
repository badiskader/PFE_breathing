"""
Throwaway local stand-in for the Mamba forecast API.

Only for development/testing of the forecast scheduler when the real
Mamba container isn't running. NOT a real model — it just echoes the
last input record with a small per-hour offset so the pipeline has
something well-formed to parse.

Run:
    python mock_mamba.py
"""

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="Mock Mamba (development only)")


@app.get("/")
def health():
    return {"status": "ok", "note": "mock mamba — do not use for science"}


@app.post("/predict_raw")
async def predict_raw(body: dict):
    sensors = body.get("sensor_data", [])
    predictions = []

    for history in sensors:
        if not history:
            predictions.append([])
            continue
        last = history[-1]

        hours = []
        for h in range(1, 13):
            hours.append({
                "hour_offset": h,
                "pm10":             float(last.get("pm10", 0.0))             + h * 0.5,
                "pm2_5":            float(last.get("pm2_5", 0.0))            + h * 0.3,
                "nitrogen_dioxide": float(last.get("nitrogen_dioxide", 0.0)) + h * 0.2,
                "ozone":            float(last.get("ozone", 0.0))            + h * 0.1,
                "carbon_monoxide":  float(last.get("carbon_monoxide", 0.0)) + h * 1.0,
                "sulphur_dioxide":  float(last.get("sulphur_dioxide", 0.0))  + h * 0.05,
            })
        predictions.append(hours)

    return {"predictions": predictions}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")
