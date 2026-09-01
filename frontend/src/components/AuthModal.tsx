"use client";

import { useState } from "react";
import { COPY } from "@/i18n/copy";
import { forgotPassword, gpsFix, loginAccount, registerAccount, resetPassword } from "@/lib/auth";
import { useApp } from "@/lib/store";

type Mode = "signin" | "register" | "forgot" | "reset";

export function AuthModal() {
  const { locale, authModal, setAuthModal, setAccount } = useApp();
  const t = COPY[locale];
  const [mode, setMode] = useState<Mode>("signin");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [sms, setSms] = useState(true);
  const [otp, setOtp] = useState("");
  const [gps, setGps] = useState<{ lat: number; lon: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (!authModal) return null;

  const close = () => {
    setErr("");
    setAuthModal(false);
  };

  const captureGps = async () => {
    setErr("");
    const fix = await gpsFix();
    if (!fix) {
      setErr(t.authGpsFail);
      return;
    }
    setGps(fix);
  };

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      if (mode === "signin") {
        const { user } = await loginAccount(phone, password);
        setAccount(user);
        close();
      } else if (mode === "register") {
        if (!phone.trim() || !password) {
          setErr(t.authNeedPhonePass);
          return;
        }
        const { user } = await registerAccount({
          phone,
          password,
          display_name: name || undefined,
          sms_opt_in: sms,
          lat: gps?.lat,
          lon: gps?.lon,
          email: email || undefined,
        });
        setAccount(user);
        close();
      } else if (mode === "forgot") {
        await forgotPassword(phone);
        setMode("reset");
      } else {
        const { user } = await resetPassword(phone, otp, password);
        setAccount(user);
        close();
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : t.authError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 p-4" onClick={close}>
      <div className="neo w-full max-w-sm space-y-3 p-4" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-bold">
          {mode === "signin" ? t.authSignIn : mode === "register" ? t.authRegister : t.authForgot}
        </h3>
        <p className="text-xs text-neo-muted">{t.authOptional}</p>
        <label className="block text-sm">
          {t.authPhone}
          <input className="neo-in mt-1 w-full px-3 py-2" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" />
        </label>
        {mode === "register" ? (
          <>
            <label className="block text-sm">
              {t.authName}
              <input className="neo-in mt-1 w-full px-3 py-2" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="block text-sm">
              {t.authEmail}
              <input className="neo-in mt-1 w-full px-3 py-2" value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
          </>
        ) : null}
        {mode === "reset" ? (
          <label className="block text-sm">
            {t.authOtp}
            <input className="neo-in mt-1 w-full px-3 py-2" value={otp} onChange={(e) => setOtp(e.target.value)} />
          </label>
        ) : null}
        {mode !== "forgot" ? (
          <label className="block text-sm">
            {t.authPassword}
            <input
              className="neo-in mt-1 w-full px-3 py-2"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
        ) : null}
        {mode === "register" ? (
          <>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={sms} onChange={(e) => setSms(e.target.checked)} />
              {t.authSmsOptIn}
            </label>
            <p className="text-xs text-neo-muted">{t.authGpsOptional}</p>
            <button type="button" className="neo-btn w-full text-sm" onClick={() => void captureGps()}>
              {gps ? t.authGpsOk : t.authUseGps}
            </button>
            {gps ? (
              <p className="font-mono text-[11px] text-neo-muted">
                {gps.lat.toFixed(4)}, {gps.lon.toFixed(4)}
              </p>
            ) : null}
          </>
        ) : null}
        {err ? <p className="text-xs text-red-500">{err}</p> : null}
        <button className="neo-btn neo-btn-on w-full text-sm" disabled={busy} onClick={() => void submit()}>
          {busy ? "…" : t.authSubmit}
        </button>
        <div className="flex flex-wrap gap-2 text-xs">
          {mode !== "signin" ? (
            <button className="text-neo-accent" onClick={() => setMode("signin")}>
              {t.authSignIn}
            </button>
          ) : null}
          {mode !== "register" ? (
            <button className="text-neo-accent" onClick={() => setMode("register")}>
              {t.authRegister}
            </button>
          ) : null}
          {mode === "signin" ? (
            <button className="text-neo-accent" onClick={() => setMode("forgot")}>
              {t.authForgot}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
