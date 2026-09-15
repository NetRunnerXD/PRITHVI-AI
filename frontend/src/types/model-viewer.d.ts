declare namespace JSX {
  interface IntrinsicElements {
    "model-viewer": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
      src?: string;
      alt?: string;
      "auto-rotate"?: boolean;
      "rotation-per-second"?: string;
      "camera-orbit"?: string;
      "field-of-view"?: string;
      exposure?: string;
      "shadow-intensity"?: string;
      "disable-zoom"?: boolean;
      "interaction-prompt"?: string;
    };
  }
}
