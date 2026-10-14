import asyncio
import os
from pathlib import Path

def load_dotenv():
    env_file = Path(__file__).resolve().parents[1] / ".env"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "")
PG_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

SQL_TABLES = "SELECT tablename FROM pg_tables WHERE schemaname='public'"

async def main():
    import asyncpg
    print("Connecting to Neon.tech...")
    host = PG_URL.split("@")[-1].split("/")[0]
    print("Host:", host)
    conn = await asyncpg.connect(PG_URL)
    ver = await conn.fetchval("SELECT version()")
    rows = await conn.fetch(SQL_TABLES)
    await conn.close()
    print("CONNECTED OK")
    print("Version:", ver[:80])
    names = [r["tablename"] for r in rows]
    print("Tables:", names if names else "(empty — run migrations next)")

asyncio.run(main())
