/** Visibility-aware timers.
 *
 * visibleInterval: like setInterval but skips ticks while the tab is hidden and catches up
 * once when it becomes visible again (no 90 s polls from background tabs).
 * subscribeSecond: one shared 1 Hz clock for every "live" label instead of one timer per
 * component (3–4 separate 1 Hz re-renders before). Also paused while hidden.
 */

export function visibleInterval(fn: () => void, ms: number): () => void {
  if (typeof window === "undefined") return () => {};
  let last = Date.now();
  const run = () => {
    last = Date.now();
    fn();
  };
  const id = window.setInterval(() => {
    if (document.hidden) return;
    run();
  }, ms);
  const onVis = () => {
    if (!document.hidden && Date.now() - last >= ms) run();
  };
  document.addEventListener("visibilitychange", onVis);
  return () => {
    window.clearInterval(id);
    document.removeEventListener("visibilitychange", onVis);
  };
}

const subs = new Set<() => void>();
let stopTick: (() => void) | null = null;

export function subscribeSecond(cb: () => void): () => void {
  subs.add(cb);
  if (!stopTick) stopTick = visibleInterval(() => subs.forEach((f) => f()), 1000);
  return () => {
    subs.delete(cb);
    if (!subs.size && stopTick) {
      stopTick();
      stopTick = null;
    }
  };
}
