from fastapi import FastAPI, Query
import httpx

app = FastAPI()
BASE = "https://public-api.nazk.gov.ua/v2"
HEADERS = {"User-Agent": "Shanovni/1.0"}


@app.get("/documents/list")
async def search(query: str = Query(...)):
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(f"{BASE}/documents/list", params={"query": query}, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return {"error": r.status_code, "body": r.text[:500]}
        return r.json()


@app.get("/documents/{doc_id}")
async def document(doc_id: str):
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(f"{BASE}/documents/{doc_id}", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return {"error": r.status_code, "body": r.text[:500]}
        return r.json()
