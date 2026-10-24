import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, BarChart, ScatterChart, HeatmapChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, VisualMapComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";

echarts.use([LineChart, BarChart, ScatterChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, VisualMapComponent, SVGRenderer]);

/** Thin ECharts wrapper: re-applies `option` whenever it changes (theme change => new option), resizes with its box. */
export default function Chart({ option, tall = false, label, height }) {
  const el = useRef(null);
  const inst = useRef(null);
  useEffect(() => {
    inst.current = echarts.init(el.current, null, { renderer: "svg" });
    const ro = new ResizeObserver(() => inst.current && inst.current.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); inst.current.dispose(); inst.current = null; };
  }, []);
  useEffect(() => { if (inst.current && option) inst.current.setOption({ backgroundColor: "transparent", ...option }, true); }, [option]);
  return <div ref={el} className={`chart ${tall ? "tall" : ""}`} style={{ direction: "ltr", ...(height ? { height } : {}) }} role="img" aria-label={label} />;
}
