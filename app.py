import json, os, requests
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

JST = timedelta(hours=9)
ORIGIN = os.environ.get("ORIGIN_API", "https://xinjianchanggang-production.up.railway.app")
BARK_KEY = os.environ.get("BARK_API_KEY", "")

def fmt_ts(ts):
    try:
        dt = datetime.fromisoformat(ts) + JST
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return ts or ""

def get_device_status():
    try:
        r = requests.get(f"{ORIGIN}/activity/summary", timeout=10)
        data = r.json()
    except Exception as e:
        return f"查询失败：{e}"
    battery = data.get("battery", "")
    location = data.get("location", "")
    weather = data.get("weather", "")
    device = data.get("device", "")
    brightness = data.get("brightness", "")
    volume = data.get("volume", "")
    last_update = data.get("last_update", "")
    lines = []
    if last_update:
        lines.append(f"采集时间：{fmt_ts(last_update)}")
    if battery:
        lines.append(f"电量：{battery}%")
    if device:
        lines.append(f"设备：{device}")
    if location:
        lines.append(f"位置：{location}")
    if weather:
        lines.append(f"天气：{weather}")
    if brightness:
        lines.append(f"亮度：{round(float(brightness) * 100)}%")
    if volume:
        lines.append(f"音量：{round(float(volume) * 100)}%")
    return "\n".join(lines) if lines else "暂无设备数据"

def check_on_wife(limit=10):
    try:
        r = requests.get(f"{ORIGIN}/activity/summary", timeout=10)
        data = r.json()
    except Exception as e:
        return f"查岗失败：{e}"
    apps = data.get("recent_apps", [])
    ses = data.get("sessions", {})
    last_update = data.get("last_update", "")
    lines = []
    if last_update:
        lines.append(f"采集时间：{fmt_ts(last_update)}")
    lines.append(f"最近打开：{', '.join(apps)}" if apps else "暂无记录")
    if ses:
        for app, secs in sorted(ses.items(), key=lambda x: x[1], reverse=True):
            m, s = divmod(secs, 60)
            lines.append(f" {app}: {m}分{s}秒")
    return "\n".join(lines)

def bark_alert(title="祁宴", content=""):
    if not content:
        return "内容不能为空"
    icon = "https://img.tofaka.com/autoupload/fr/ijxPaC6-CwFPrzUEy795YGx8135l7hBtTSbeN4oB8TWyl5f0KlZfm6UsKj-HyTuv/20260803/hkqK/1206X1579/IMG_1178.jpeg/webp"
    url = f"https://api.day.app/push"
    payload = {
        "title": title,
        "body": content,
        "device_key": BARK_KEY,
        "icon": icon
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return "推送成功" if r.status_code == 200 else "推送失败"
    except Exception as e:
        return f"推送异常：{e}"

TOOLS = [
    {"name": "check_on_wife", "description": "查岗老婆的手机活动", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "check_device", "description": "查老婆手机设备状态（电量、位置、天气、设备、亮度、音量）", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "bark_alert", "description": "给老婆手机发推送弹窗", "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}}, "required": ["content"]}}
]

FUNCS = {"check_on_wife": check_on_wife, "check_device": get_device_status, "bark_alert": bark_alert}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/api/mcp")
async def mcp(req: Request):
    body = await req.json()
    method, params = body.get("method"), body.get("params") or {}
    rid = body.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "查岗MCP", "version": "1.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name not in FUNCS:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "未知工具"}}
        result = FUNCS[name](**args)
        return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": str(result)}]}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"未知方法: {method}"}}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
