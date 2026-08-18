import { NextRequest, NextResponse } from "next/server";

const BACKEND = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(/\/+$/, "");

async function proxy(req: NextRequest) {
  const url = new URL("/api/nowcast/live", BACKEND || "http://127.0.0.1:8000");
  req.nextUrl.searchParams.forEach((v, k) => url.searchParams.set(k, v));
  try {
    const r = await fetch(url.toString(), { cache: "no-store" });
    const body = await r.text();
    return new NextResponse(body, {
      status: r.status,
      headers: { "content-type": r.headers.get("content-type") || "application/json" },
    });
  } catch (e) {
    return NextResponse.json({ error: String(e), hint: "Start uvicorn on :8000" }, { status: 502 });
  }
}

export async function GET(req: NextRequest) {
  return proxy(req);
}
