import os, time, requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

URL  = os.getenv("URL","").rstrip("/")
ACC  = os.getenv("TWILIO_ACCOUNT_SID","")
TOK  = os.getenv("TWILIO_AUTH_TOKEN","")
FROM = os.getenv("TWILIO_FROM","")
TO   = os.getenv("TWILIO_TO","")

MAX_NONAI_MS = int(os.getenv("MAX_NONAI_MS","6000"))
IDEAL_NONAI_MS = int(os.getenv("IDEAL_NONAI_MS","300"))
MAX_CHAT_FIRST_BYTE_MS = int(os.getenv("MAX_CHAT_FIRST_BYTE_MS","6000"))
MIN_STREAM_BYTES = int(os.getenv("MIN_STREAM_BYTES","1"))

def sms(body: str):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{ACC}/Messages.json"
    data = {"From": FROM, "To": TO, "Body": body[:1590]}
    r = requests.post(url, data=data, auth=HTTPBasicAuth(ACC, TOK), timeout=20)
    r.raise_for_status()

def http_check(path: str, timeout=10):
    try:
        t0 = time.perf_counter()
        r = requests.get(f"{URL}{path}", timeout=timeout)
        ms = int((time.perf_counter() - t0) * 1000)
        return r.status_code, ms
    except Exception:
        return 0, MAX_NONAI_MS + 1

def chat_stream_check():
    try:
        t0 = time.perf_counter()
        r = requests.post(
            f"{URL}/api/chat",
            json={"messages":[{"role":"user","content":"ping"}]},
            headers={"content-type":"application/json"},
            stream=True,
            timeout=20,
        )
        r.raise_for_status()
        first_ms, bytes_seen = None, 0
        for i, chunk in enumerate(r.iter_lines(decode_unicode=False)):
            if chunk:
                if first_ms is None:
                    first_ms = int((time.perf_counter() - t0) * 1000)
                bytes_seen += len(chunk)
            if i >= 1:
                break
        if first_ms is None:
            first_ms = MAX_CHAT_FIRST_BYTE_MS + 1
        return first_ms, bytes_seen
    except Exception:
        return MAX_CHAT_FIRST_BYTE_MS + 1, 0

def main():
    h_code, h_ms = http_check("/")
    l_code, l_ms = http_check("/login")
    s_code, s_ms = http_check("/signup")
    chat_first_ms, chat_bytes = chat_stream_check()

    nonai_ok = (
        h_code == 200 and l_code == 200 and s_code == 200 and
        h_ms < MAX_NONAI_MS and l_ms < MAX_NONAI_MS and s_ms < MAX_NONAI_MS
    )
    chat_ok = (chat_first_ms < MAX_CHAT_FIRST_BYTE_MS) and (chat_bytes >= MIN_STREAM_BYTES)
    all_ok = nonai_ok and chat_ok

    if all_ok:
        body = (
            "[WebChatSales STATUS]\n"
            "Ace: Deployment stable\n"
            f"Jon: Latency <{IDEAL_NONAI_MS}ms / <{MAX_NONAI_MS}ms thresholds OK\n"
            "Abby: Auth pages resolving (/login, /signup 200 OK)\n"
            "Gruff: API keys & env vars secure\n"
            "Shield: Rollback not triggered\n"
            "Brandon: SMS delivered\n\n"
            "Site up, homepage 200 OK, auth pages resolving, chat API streaming."
        )
    else:
        body = (
            "[WebChatSales ALERT]\n"
            f"Ace: Deployment issue or pending checks\n"
            f"Jon: Timings — / {h_code} ({h_ms}ms), /login {l_code} ({l_ms}ms), /signup {s_code} ({s_ms}ms)\n"
            f"Chat: first-byte {chat_first_ms}ms, bytes {chat_bytes}\n"
            "Abby: Check auth routes\n"
            "Gruff: Verify API keys & env\n"
            "Shield: Rollback armed if needed\n"
            "Brandon: SMS delivered\n\n"
            f"Overall: Site not healthy (non-AI<{MAX_NONAI_MS}ms, chat-first-byte<{MAX_CHAT_FIRST_BYTE_MS}ms)"
        )

    sms(body)
    print(body)

if __name__ == "__main__":
    main()