"use client";

import { useState } from "react";
import { COPY } from "@/i18n/copy";
import { forgotPassword, gpsFix, loginAccount, registerAccount, resetPassword } from "@/lib/auth";
import { useApp } from "@/lib/store";
import { IconCross, IconPin, IconSparkle, IconUser } from "./Icons";

type Mode = "signin" | "register" | "forgot" | "reset";

export function AuthModal() {
  const { locale, authModal, setAuthModal, setAccount } = useApp();
  const t = COPY[locale];
  const [mode, setMode] = useState<Mode>("signin");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [sms, setSms] = useState(true);
  const [otp, setOtp] = useState("");
  const [gps, setGps] = useState<{ lat: number; lon: number } | null>(null);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (!authModal) return null;

  const close = () => {
    setErr("");
    setAuthModal(false);
  };

  const captureGps = async () => {
    setErr("");
    setGpsLoading(true);
    try {
      const fix = await gpsFix();
      if (!fix) {
        setErr(t.authGpsFail);
        return;
      }
      setGps(fix);
    } finally {
      setGpsLoading(false);
    }
  };

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      if (mode === "signin") {
        if (!phone.trim() || !password) {
          setErr(t.authNeedPhonePass);
          return;
        }
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
        if (!phone.trim()) {
          setErr("Please enter your registered mobile number");
          return;
        }
        await forgotPassword(phone);
        setMode("reset");
      } else {
        if (!otp.trim() || !password) {
          setErr("Please enter the verification code and your new password");
          return;
        }
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
    <div
      className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60 backdrop-blur-md p-4 animate-in fade-in duration-200 select-none"
      onClick={close}
    >
      <div
        className="relative w-full max-w-md overflow-hidden rounded-3xl border border-[color-mix(in_srgb,var(--line)_80%,var(--accent))] bg-[var(--card)] p-6 shadow-2xl shadow-black/40 transition-all duration-300 animate-in zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Ambient Top Glow / Radial Gradient */}
        <div className="pointer-events-none absolute -top-24 -left-24 h-48 w-48 rounded-full bg-cyan-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -right-24 h-48 w-48 rounded-full bg-blue-600/20 blur-3xl" />

        {/* Close Button */}
        <button
          type="button"
          onClick={close}
          className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full text-neo-muted transition-all duration-150 hover:bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] hover:text-neo-text active:scale-95"
          title="Close modal"
        >
          <IconCross className="h-4 w-4" />
        </button>

        {/* Header Branding */}
        <div className="flex items-center gap-3">
          <div className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl overflow-hidden bg-gradient-to-tr from-blue-600/30 via-sky-500/30 to-indigo-600/30 shadow-lg shadow-blue-500/20 border border-white/20">
            <img src="/logo.png" alt="PRITHVI-AI Logo" width={48} height={48} className="h-full w-full object-cover" />
            <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-300 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-400 border border-[var(--card)]" />
            </span>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="text-base font-black tracking-tight text-neo-text">
                PRITHVI<span className="text-neo-accent">-AI</span>
              </h2>
              <span className="chip flex items-center gap-1 rounded-md bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] px-1.5 py-0.5 text-[9px] font-mono font-bold text-neo-accent border border-[color-mix(in_srgb,var(--accent)_25%,transparent)]">
                <IconSparkle className="h-2.5 w-2.5" />
                <span>WeatherGPT</span>
              </span>
            </div>
            <p className="text-xs text-neo-muted">
              {mode === "signin"
                ? "Sign in to access SMS weather alerts and saved farm plots"
                : mode === "register"
                ? "Create your profile for hyper-local environmental intelligence"
                : "Reset your account password via SMS"}
            </p>
          </div>
        </div>

        {/* Segmented Mode Switcher */}
        {mode !== "reset" && (
          <div className="mt-5 flex rounded-xl bg-[color-mix(in_srgb,var(--line)_50%,transparent)] p-1 border border-[var(--line)]">
            <button
              type="button"
              onClick={() => {
                setErr("");
                setMode("signin");
              }}
              className={`flex-1 rounded-lg py-1.5 text-xs font-bold transition-all duration-200 ${
                mode === "signin"
                  ? "bg-neo-card text-neo-accent shadow-sm border border-[color-mix(in_srgb,var(--accent)_30%,transparent)]"
                  : "text-neo-muted hover:text-neo-text"
              }`}
            >
              {t.authSignIn}
            </button>
            <button
              type="button"
              onClick={() => {
                setErr("");
                setMode("register");
              }}
              className={`flex-1 rounded-lg py-1.5 text-xs font-bold transition-all duration-200 ${
                mode === "register"
                  ? "bg-neo-card text-neo-accent shadow-sm border border-[color-mix(in_srgb,var(--accent)_30%,transparent)]"
                  : "text-neo-muted hover:text-neo-text"
              }`}
            >
              {t.authRegister}
            </button>
          </div>
        )}

        {/* Form Fields */}
        <form
          className="mt-4 space-y-3.5"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          {/* Mobile Phone Number */}
          <div className="space-y-1">
            <label className="text-[11px] font-bold uppercase tracking-wider text-neo-muted">
              {t.authPhone}
            </label>
            <div className="relative flex items-center">
              <span className="absolute left-3 font-mono text-xs font-bold text-neo-muted select-none">
                +91
              </span>
              <input
                className="neo-in w-full rounded-xl py-2.5 pl-12 pr-3 text-xs font-medium text-neo-text placeholder:text-neo-muted/60 focus:border-neo-accent focus:outline-none transition-all"
                placeholder="10-digit mobile number"
                value={phone}
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))}
                inputMode="tel"
                autoFocus
              />
            </div>
          </div>

          {/* Register Mode Extra Fields */}
          {mode === "register" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="space-y-1">
                <label className="text-[11px] font-bold uppercase tracking-wider text-neo-muted">
                  {t.authName}
                </label>
                <input
                  className="neo-in w-full rounded-xl px-3 py-2 text-xs font-medium text-neo-text placeholder:text-neo-muted/60 focus:border-neo-accent focus:outline-none transition-all"
                  placeholder="e.g. Ramesh Kumar"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-bold uppercase tracking-wider text-neo-muted">
                  {t.authEmail}
                </label>
                <input
                  type="email"
                  className="neo-in w-full rounded-xl px-3 py-2 text-xs font-medium text-neo-text placeholder:text-neo-muted/60 focus:border-neo-accent focus:outline-none transition-all"
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Reset Mode OTP */}
          {mode === "reset" && (
            <div className="space-y-1 animate-in fade-in slide-in-from-top-2 duration-200">
              <label className="text-[11px] font-bold uppercase tracking-wider text-neo-muted">
                {t.authOtp}
              </label>
              <input
                className="neo-in w-full rounded-xl px-3 py-2 text-xs font-medium text-neo-text placeholder:text-neo-muted/60 focus:border-neo-accent focus:outline-none transition-all tracking-widest font-mono"
                placeholder="6-digit verification code"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
              />
            </div>
          )}

          {/* Password Input (for signin, register, reset) */}
          {mode !== "forgot" && (
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-bold uppercase tracking-wider text-neo-muted">
                  {mode === "reset" ? "New Password" : t.authPassword}
                </label>
                {mode === "signin" && (
                  <button
                    type="button"
                    onClick={() => {
                      setErr("");
                      setMode("forgot");
                    }}
                    className="text-[11px] font-semibold text-neo-accent hover:underline"
                  >
                    {t.authForgot}
                  </button>
                )}
              </div>
              <div className="relative flex items-center">
                <input
                  className="neo-in w-full rounded-xl py-2.5 pl-3 pr-10 text-xs font-medium text-neo-text placeholder:text-neo-muted/60 focus:border-neo-accent focus:outline-none transition-all"
                  type={showPassword ? "text" : "password"}
                  placeholder={mode === "register" ? "Minimum 6 characters" : "Enter your password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 text-xs font-bold text-neo-muted hover:text-neo-text select-none"
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>
          )}

          {/* Register Mode GPS & SMS options */}
          {mode === "register" && (
            <div className="space-y-2.5 pt-1 animate-in fade-in slide-in-from-top-2 duration-200">
              <label className="flex items-center gap-2.5 cursor-pointer text-xs font-medium text-neo-text select-none">
                <input
                  type="checkbox"
                  checked={sms}
                  onChange={(e) => setSms(e.target.checked)}
                  className="h-4 w-4 rounded accent-neo-accent cursor-pointer"
                />
                <span>{t.authSmsOptIn}</span>
              </label>

              <div className="rounded-xl border border-[var(--line)] bg-[color-mix(in_srgb,var(--card)_80%,var(--accent)_8%)] p-2.5 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[color-mix(in_srgb,var(--accent)_20%,transparent)] text-neo-accent">
                    <IconPin className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] font-bold text-neo-text truncate">
                      {gps ? "GPS Location Pinned" : "Auto-Detect District"}
                    </p>
                    <p className="text-[10px] text-neo-muted truncate">
                      {gps ? `${gps.lat.toFixed(4)}, ${gps.lon.toFixed(4)}` : "Optional. Automatically pins your exact region."}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  disabled={gpsLoading}
                  onClick={() => void captureGps()}
                  className="chip shrink-0 rounded-lg px-2.5 py-1 text-[10px] font-bold text-neo-accent bg-[color-mix(in_srgb,var(--accent)_15%,transparent)] border border-[color-mix(in_srgb,var(--accent)_30%,transparent)] hover:bg-neo-accent hover:text-white transition-all shadow-xs"
                >
                  {gpsLoading ? "Detecting…" : gps ? "Update GPS" : "Get GPS"}
                </button>
              </div>
            </div>
          )}

          {/* Error Message */}
          {err && (
            <div className="rounded-xl bg-rose-500/10 border border-rose-500/20 p-2.5 text-xs font-semibold text-rose-600 dark:text-rose-400 animate-in fade-in">
              {err}
            </div>
          )}

          {/* Submit Action Button */}
          <button
            type="submit"
            disabled={busy}
            className="group relative flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 via-sky-600 to-indigo-600 dark:from-sky-500 dark:via-cyan-400 dark:to-indigo-500 py-2.5 text-xs font-black uppercase tracking-wider text-white shadow-lg shadow-blue-500/20 transition-all duration-200 hover:shadow-cyan-500/30 hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
          >
            {busy ? (
              <span className="flex items-center gap-2">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                <span>Processing…</span>
              </span>
            ) : (
              <>
                <span>
                  {mode === "signin"
                    ? t.authSignIn
                    : mode === "register"
                    ? t.authRegister
                    : mode === "forgot"
                    ? "Send Verification Code"
                    : "Update Password"}
                </span>
                <IconSparkle className="h-3.5 w-3.5 transition-transform duration-200 group-hover:rotate-12" />
              </>
            )}
          </button>
        </form>

        {/* Footer Sub-links */}
        <div className="mt-4 flex items-center justify-between border-t border-[var(--line)] pt-3 text-[11px] text-neo-muted">
          {mode === "forgot" || mode === "reset" ? (
            <button
              type="button"
              className="text-neo-accent font-bold hover:underline"
              onClick={() => {
                setErr("");
                setMode("signin");
              }}
            >
              ← Back to Sign In
            </button>
          ) : (
            <>
              <span>{mode === "signin" ? "Don't have an account?" : "Already registered?"}</span>
              <button
                type="button"
                className="font-bold text-neo-accent hover:underline"
                onClick={() => {
                  setErr("");
                  setMode(mode === "signin" ? "register" : "signin");
                }}
              >
                {mode === "signin" ? t.authRegister : t.authSignIn}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

