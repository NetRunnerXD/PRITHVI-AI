"use client";

import { useEffect } from "react";

/** NASA Blue Marble (public domain USGov) on a local UV-sphere GLB. */
export const EARTH_GLB = "/models/earth.glb";
const MODEL_VIEWER_SRC = "https://ajax.googleapis.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js";

export function useModelViewer() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (customElements.get("model-viewer")) return;
    if (document.querySelector(`script[data-prithvi-model-viewer]`)) return;
    const s = document.createElement("script");
    s.type = "module";
    s.src = MODEL_VIEWER_SRC;
    s.dataset.prithviModelViewer = "1";
    document.head.appendChild(s);
  }, []);
}

type Size = "fab" | "header";

export function ChatAssistant3D({ size = "fab", className = "" }: { size?: Size; className?: string }) {
  useModelViewer();
  const box = size === "fab" ? "h-full w-full" : "h-8 w-8";
  return (
    <div className={`${box} ${className}`} aria-hidden>
      <model-viewer
        src={EARTH_GLB}
        alt="Earth — NASA Blue Marble, public domain"
        auto-rotate
        rotation-per-second="22deg"
        camera-orbit="250deg 78deg 2.35m"
        field-of-view="26deg"
        exposure="1.05"
        shadow-intensity="0"
        disable-zoom
        interaction-prompt="none"
        style={{ width: "100%", height: "100%", background: "transparent" }}
      />
    </div>
  );
}
