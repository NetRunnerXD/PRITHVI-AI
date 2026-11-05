"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl } from "@/lib/config";
import { searchPlaces } from "@/lib/api";
import type { Location } from "@/types/dashboard";

type Ap = { ssid: string; rssi: number };
type BtDev = { name: string; bda: string; rssi?: number };
type BoxStatus = {
  code?: string;
  ssid?: string;
  sta?: boolean;
  live_ip?: string;
  place?: string;
  audio_mode?: string;
  volume?: number;
  bt_paired?: boolean;
  bt_linked?: boolean;
  bt_name?: string;
  host?: string;
  port?: number;
};
type Voice = { stt?: boolean; tts?: boolean; detail?: string };
type PlacePick = { name: string; lat: number; lon: number };
type FaceCard = { place?: string; temp_c?: number; sky?: string; aqi?: number };

async function call(path: string, body?: object) {
  const res = await fetch(apiUrl(path), {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.error || "error");
  return data;
}

function speakerName(mode: string) {
  if (mode === "bt") return "Bluetooth speaker";
  if (mode === "both") return "Wired and Bluetooth";
  return "Wired speaker";
}

export function DevicePanel() {
  const [code, setCode] = useState("");
  const [linked, setLinked] = useState("");
  const [status, setStatus] = useState<BoxStatus | null>(null);
  const [voice, setVoice] = useState<Voice | null>(null);
  const [aps, setAps] = useState<Ap[]>([]);
  const [ssid, setSsid] = useState("");
  const [pass, setPass] = useState("");
  const [place, setPlace] = useState("");
  const [hits, setHits] = useState<Location[]>([]);
  const [placeOpen, setPlaceOpen] = useState(false);
  const [picked, setPicked] = useState<PlacePick | null>(null);
  const [card, setCard] = useState<FaceCard | null>(null);
  const placeDirty = useRef(false);
  const [audio, setAudio] = useState("i2s");
  const [volume, setVolume] = useState(80);
  const [speakers, setSpeakers] = useState<BtDev[]>([]);
  const [btName, setBtName] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [wifiOpen, setWifiOpen] = useState(false);

  const refresh = useCallback(async () => {
    const [nearby, voiceBody] = await Promise.all([
      call("/device/nearby"),
      call("/device/voice").catch(() => null),
    ]);
    if (voiceBody) setVoice(voiceBody as Voice);
    if (!linked && nearby.linked) setLinked(nearby.linked);
    if (!linked && !nearby.linked) return;
    const box = await call("/device/box");
    const s = (box.status || {}) as BoxStatus;
    setStatus(s);
    setLinked(box.code || linked);
    setSsid(s.ssid || "");
    if (!placeDirty.current) setPlace(s.place || "");
    setAudio(s.audio_mode || "i2s");
    setVolume(s.volume ?? 80);
  }, [linked]);

  useEffect(() => {
    const timer = setInterval(() => {
      void refresh().catch(() => undefined);
    }, 8000);
    void refresh().catch(() => undefined);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    const needle = place.trim();
    if (!placeOpen || needle.length < 2) {
      setHits([]);
      return;
    }
    const ac = new AbortController();
    const id = window.setTimeout(() => {
      void searchPlaces(needle, ac.signal)
        .then((rows) => {
          if (!ac.signal.aborted) setHits(rows.slice(0, 6));
        })
        .catch(() => {
          if (!ac.signal.aborted) setHits([]);
        });
    }, 150);
    return () => {
      window.clearTimeout(id);
      ac.abort();
    };
  }, [place, placeOpen]);

  function choosePlace(hit: Location) {
    const name = hit.place_name || hit.label;
    placeDirty.current = true;
    setPlace(name);
    setPicked({ name, lat: hit.lat, lon: hit.lon });
    setHits([]);
    setPlaceOpen(false);
  }

  async function link() {
    setBusy(true);
    setMsg("Looking for that code on the home network…");
    try {
      const data = await call("/device/link", { code });
      setLinked(data.code);
      setStatus(data.status || null);
      setMsg("Linked. Hold the button on the box and ask in English.");
    } catch (err) {
      setMsg(err instanceof Error && err.message === "not_found"
        ? "No box with that code is on this network yet."
        : "Could not link the box.");
    } finally {
      setBusy(false);
    }
  }

  async function scan() {
    setBusy(true);
    try {
      const wifi = await call("/device/box/wifi");
      setAps(wifi.aps || []);
      setMsg(wifi.aps?.length ? "Tap a network, then save." : "No saved network list. Use the phone setup page.");
    } catch {
      setMsg("The box could not list networks.");
    } finally {
      setBusy(false);
    }
  }

  function btProblem(err: unknown, fallback: string) {
    const code = err instanceof Error ? err.message : "";
    if (code === "name") return "No speaker with that name is nearby. Turn on pairing and try again.";
    if (code === "connect") return "The speaker did not open the audio link. Put it in pairing mode, disconnect it from your phone, and try again.";
    if (code === "scan") return "The box could not scan for speakers.";
    if (code === "busy") return "The box is speaking. Try again in a moment.";
    if (code === "unpaired") return "Save a Bluetooth speaker first, then test it.";
    if (code === "no audio") return "The speaker stayed silent. Put it in pairing mode, disconnect it from your phone, and try again.";
    if (code === "ram") return "The box does not have enough memory for Bluetooth audio. Wait a moment and try the test again.";
    if (code === "offline") return "The box is offline.";
    return fallback;
  }

  async function scanBt() {
    setBusy(true);
    setMsg("Scanning for speakers. This takes a few seconds.");
    try {
      const data = await call("/device/box/bt", { action: "scan" });
      const rows = (data.devices || []) as BtDev[];
      setSpeakers(rows);
      setMsg(rows.length ? "Tap a speaker, or type its name below." : "No speakers found. Put one in pairing mode and scan again.");
    } catch (err) {
      setMsg(btProblem(err, "The box could not scan for speakers."));
    } finally {
      setBusy(false);
    }
  }

  async function connectBt(body: { bda?: string; name?: string }) {
    setBusy(true);
    setMsg(body.name ? `Looking for ${body.name}…` : "Connecting…");
    try {
      const data = await call("/device/box/bt", { action: "pair", ...body });
      if (audio === "i2s") setAudio("both");
      setMsg(data.linked
        ? `Connected to ${data.name || "the speaker"}. The next answer plays there.`
        : `Saved ${data.name || "the speaker"}, but it did not link. Put it in pairing mode and try again.`);
      await refresh();
    } catch (err) {
      setMsg(btProblem(err, "The box could not connect to that speaker."));
    } finally {
      setBusy(false);
    }
  }

  async function testBt() {
    setBusy(true);
    setMsg("Playing a test tone on the Bluetooth speaker…");
    try {
      const data = await call("/device/box/bt", { action: "tone" });
      setMsg(
        data.linked
          ? `Test tone sent to ${data.name || "the speaker"}. You should hear two beeps.`
          : "The tone was sent, but the speaker is not linked.",
      );
      await refresh();
    } catch (err) {
      setMsg(btProblem(err, "The speaker test did not play."));
    } finally {
      setBusy(false);
    }
  }

  async function forgetBt() {
    setBusy(true);
    setMsg("Forgetting the saved speaker…");
    try {
      await call("/device/box/bt", { action: "forget" });
      setMsg("Bluetooth speaker forgotten.");
      await refresh();
    } catch (err) {
      setMsg(btProblem(err, "The box could not forget that speaker."));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setMsg("Saving…");
    try {
      const body: {
        place: string;
        audio_mode: string;
        volume: number;
        show_aqi: boolean;
        show_rain: boolean;
        has_geo?: boolean;
        lat?: number;
        lon?: number;
        ssid?: string;
        pass?: string;
      } = {
        place,
        audio_mode: audio,
        volume,
        show_aqi: true,
        show_rain: true,
      };
      if (picked && picked.name === place.trim()) {
        body.has_geo = true;
        body.lat = picked.lat;
        body.lon = picked.lon;
      }
      if (wifiOpen && ssid) {
        body.ssid = ssid;
        if (pass) body.pass = pass;
      }
      const saved = await call("/device/box", body);
      setPass("");
      placeDirty.current = false;
      const next = (saved.card || null) as FaceCard | null;
      setCard(next);
      const shown = next?.temp_c == null ? "Saved on the box." : `${next.place || place} is ${Math.round(next.temp_c)}°C on the screen.`;
      setMsg(wifiOpen && ssid && ssid !== status?.ssid
        ? "Saved. The box will leave this network. Link it again when the code is back on the screen."
        : shown);
      await refresh();
    } catch {
      setMsg("The box did not accept those settings.");
    } finally {
      setBusy(false);
    }
  }

  const online = Boolean(status?.sta);
  const voiceOk = Boolean(voice?.stt && voice?.tts);
  const voiceLine = voiceOk
    ? "English listening and the speaker are ready on this computer."
    : voice?.detail || "Checking the speaker…";

  return (
    <div className="space-y-4">
      <section className="neo space-y-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold">Weather box</h2>
            <p className="mt-1 text-sm text-neo-muted">Hold the button and ask in English. The answer plays on the speaker.</p>
          </div>
          <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold ${online ? "bg-emerald-700 text-white" : "bg-stone-300 text-stone-800"}`}>
            {online ? "Online" : linked ? "Offline" : "Not linked"}
          </span>
        </div>

        {linked && status ? (
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-neo-muted">Code</dt>
              <dd className="font-bold tracking-widest">{linked}</dd>
            </div>
            <div>
              <dt className="text-neo-muted">Address</dt>
              <dd className="font-bold">{status.live_ip || "—"}</dd>
            </div>
            <div>
              <dt className="text-neo-muted">Network</dt>
              <dd className="font-bold">{status.ssid || "—"}</dd>
            </div>
            <div>
              <dt className="text-neo-muted">Computer</dt>
              <dd className="font-bold">{status.host ? `${status.host}:${status.port || 8000}` : "Not saved"}</dd>
            </div>
          </dl>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-neo-muted">On a phone, join PRITHVI-SETUP and connect the box to home Wi-Fi. Then enter the code from the screen.</p>
            <label className="block text-sm">
              Code on the screen
              <input
                className="neo-in mt-1 w-full px-3 py-2 uppercase tracking-widest"
                value={code}
                maxLength={8}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="P9V9ZN"
              />
            </label>
            <button className="neo-btn text-sm" disabled={busy || code.trim().length < 4} onClick={() => void link()}>
              Link this computer
            </button>
          </div>
        )}
        <p className={`text-sm ${voiceOk ? "text-neo-muted" : "text-amber-800"}`}>{voiceLine}</p>
        {msg ? <p className="text-sm">{msg}</p> : null}
      </section>

      {linked ? (
        <section className="neo space-y-3 p-4">
          <h3 className="text-sm font-bold">On the box</h3>
          <div className="relative block text-sm">
            Place
            <input
              className="neo-in mt-1 w-full px-3 py-2"
              value={place}
              placeholder="Search a town or district"
              onFocus={() => setPlaceOpen(true)}
              onBlur={() => window.setTimeout(() => setPlaceOpen(false), 200)}
              onChange={(e) => {
                placeDirty.current = true;
                setPicked(null);
                setCard(null);
                setPlace(e.target.value);
                setPlaceOpen(true);
              }}
            />
            {placeOpen && hits.length > 0 ? (
              <ul className="absolute left-0 right-0 z-20 mt-1 max-h-52 overflow-auto rounded-xl border border-[var(--line)] bg-[var(--card)] p-1 shadow-lg">
                {hits.map((hit) => (
                  <li key={hit.id}>
                    <button
                      type="button"
                      className="w-full rounded-lg px-3 py-2 text-left hover:bg-[color-mix(in_srgb,var(--accent)_8%,transparent)]"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        choosePlace(hit);
                      }}
                    >
                      <span className="font-medium">{hit.label}</span>
                      <span className="ml-2 text-xs uppercase text-neo-muted">{hit.place_kind || "place"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            <p className="mt-1 text-xs text-neo-muted">
              {card && card.temp_c != null
                ? `${card.place || place}: ${Math.round(card.temp_c)}°C${card.sky ? `, ${card.sky}` : ""}${card.aqi != null ? `, AQI ${card.aqi}` : ""}`
                : "Pick a place from the list, then save. The screen shows that forecast."}
            </p>
          </div>
          <label className="block text-sm">
            Speaker
            <select className="neo-in mt-1 w-full px-3 py-2" value={audio} onChange={(e) => setAudio(e.target.value)}>
              <option value="i2s">Wired speaker</option>
              <option value="bt">Bluetooth speaker</option>
              <option value="both">Both</option>
            </select>
          </label>
          <p className="text-xs text-neo-muted">Now: {speakerName(status?.audio_mode || audio)}</p>
          <div className="space-y-2 rounded-xl border border-[var(--line)] p-3">
            <p className="text-sm font-medium">Bluetooth speaker</p>
            <p className="text-xs text-neo-muted">
              {status?.bt_paired && status.bt_name
                ? status.bt_linked
                  ? `Connected: ${status.bt_name}`
                  : `Saved: ${status.bt_name}. The speaker is not linked yet.`
                : "No speaker saved. Put the speaker in pairing mode first."}
            </p>
            <button className="neo-btn text-sm" type="button" disabled={busy} onClick={() => void scanBt()}>
              Scan speakers
            </button>
            <ul className="max-h-40 space-y-1 overflow-auto text-sm">
              {speakers.map((dev) => (
                <li key={dev.bda}>
                  <button
                    className="w-full text-left"
                    type="button"
                    disabled={busy}
                    onClick={() => void connectBt({ bda: dev.bda, name: dev.name === "Unknown" ? "" : dev.name })}
                  >
                    {dev.name || "Unknown"} <span className="text-neo-muted">{dev.rssi}</span>
                  </button>
                </li>
              ))}
            </ul>
            <label className="block text-sm">
              Or type the speaker name
              <input
                className="neo-in mt-1 w-full px-3 py-2"
                value={btName}
                placeholder="JBL Flip"
                onChange={(e) => setBtName(e.target.value)}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                className="neo-btn text-sm"
                type="button"
                disabled={busy || btName.trim().length < 2}
                onClick={() => void connectBt({ name: btName.trim() })}
              >
                Connect this name
              </button>
              {status?.bt_paired ? (
                <button className="neo-btn text-sm" type="button" disabled={busy} onClick={() => void testBt()}>
                  Test speaker
                </button>
              ) : null}
              {status?.bt_paired ? (
                <button className="neo-btn text-sm" type="button" disabled={busy} onClick={() => void forgetBt()}>
                  Forget speaker
                </button>
              ) : null}
            </div>
          </div>
          <label className="block text-sm">
            Volume {volume}
            <input className="mt-1 w-full" type="range" min={0} max={100} value={volume} onChange={(e) => setVolume(Number(e.target.value))} />
          </label>
          <button className="neo-btn text-sm" disabled={busy} onClick={() => void save()}>
            Save
          </button>
        </section>
      ) : null}

      {linked ? (
        <details className="neo p-4" open={wifiOpen} onToggle={(e) => setWifiOpen((e.target as HTMLDetailsElement).open)}>
          <summary className="cursor-pointer text-sm font-bold">Change home Wi-Fi</summary>
          <div className="mt-3 space-y-3">
            <p className="text-sm text-neo-muted">The phone setup page is the usual way. Saving a different network here makes the box drop offline until you link it again.</p>
            <button className="neo-btn text-sm" disabled={busy} onClick={() => void scan()}>
              Show saved networks
            </button>
            <ul className="max-h-40 space-y-1 overflow-auto text-sm">
              {aps.map((ap) => (
                <li key={ap.ssid}>
                  <button className="w-full text-left" onClick={() => setSsid(ap.ssid)}>
                    {ap.ssid} <span className="text-neo-muted">{ap.rssi}</span>
                  </button>
                </li>
              ))}
            </ul>
            <label className="block text-sm">
              Network
              <input className="neo-in mt-1 w-full px-3 py-2" value={ssid} onChange={(e) => setSsid(e.target.value)} />
            </label>
            <label className="block text-sm">
              Password
              <input className="neo-in mt-1 w-full px-3 py-2" type="password" value={pass} onChange={(e) => setPass(e.target.value)} />
            </label>
          </div>
        </details>
      ) : null}
    </div>
  );
}
