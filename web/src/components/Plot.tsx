"use client";

import { useEffect, useRef } from "react";

/** Figure Plotly serialisee par l'etage 1 ; plotly.js n'est charge qu'a la premiere figure. */
export function Plot({ spec }: { spec: { data: unknown[]; layout?: Record<string, unknown> } }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    let disposed = false;
    let Plotly: typeof import("plotly.js-dist-min") | null = null;

    const draw = async () => {
      Plotly = (await import("plotly.js-dist-min")).default as unknown as typeof import("plotly.js-dist-min");
      if (disposed) return;
      const css = getComputedStyle(document.documentElement);
      const ink = css.getPropertyValue("--ink").trim() || "#1c1b19";
      const grid = css.getPropertyValue("--line").trim() || "#e2dfd8";
      const layout = {
        ...spec.layout,
        template: undefined,
        autosize: true,
        height: 340,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: ink, family: "inherit" },
        margin: { l: 56, r: 16, t: 36, b: 48 },
        xaxis: { ...(spec.layout?.xaxis as object), gridcolor: grid, zerolinecolor: grid },
        yaxis: { ...(spec.layout?.yaxis as object), gridcolor: grid, zerolinecolor: grid },
      };
      await Plotly.newPlot(node, spec.data as never, layout as never, { responsive: true, displaylogo: false });
    };
    draw().catch(() => {
      node.textContent = "Figure non affichable.";
    });

    return () => {
      disposed = true;
      if (Plotly) Plotly.purge(node);
    };
  }, [spec]);

  return <div ref={ref} className="plot" />;
}
