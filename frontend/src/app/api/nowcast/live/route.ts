import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND = (
  process.env.NEXT_PUBLIC_API_BASE ||
  (process.env.VERCEL ? "https://rituchakra-api.onrender.com" : "http://127.0.0.1:8000")
).replace(/\/+$/, "");

async function proxy(req: NextRequest) {
  const url = new URL("/api/nowcast/live", BACKEND || "http://127.0.0.1:8000");
  req.nextUrl.searchParams.forEach((v, k) => url.searchParams.set(k, v));
  try {
    const r = await fetch(url.toString(), { cache: "no-store" });
    const body = await r.text();
    return new NextResponse(body, {
      status: r.status,
      headers: {
        "content-type": r.headers.get("content-type") || "application/json",
        // Let Vercel's edge cache identical (location-keyed) requests for 60 s and serve
        // stale while revalidating, instead of a cold trip to Render on every poll.
        "cache-control": r.ok ? "public, s-maxage=60, stale-while-revalidate=300" : "no-store",
      },
    });
  } catch (e) {
    return NextResponse.json({ error: String(e), hint: "Start uvicorn on :8000" }, { status: 502 });
  }
}

export async function GET(req: NextRequest) {
  return proxy(req);
}
