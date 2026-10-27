import httpx
async def http_fetch(url: str):
    if not url.startswith("http"):
        raise ValueError("Invalid URL")
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        r = await c.get(url, headers={"User-Agent":"AgentPlatform/1.0"})
        r.raise_for_status()
        text = r.text[:15000] # truncate - prevent token explosion
        return {"url": url, "status": r.status_code, "content": text, "truncated": len(r.text) > 15000}