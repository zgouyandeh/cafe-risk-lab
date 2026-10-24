import { useState } from "react";
import { runSimulation } from "./api.js";

export function useSim(mode) {
  const [state, setState] = useState({ running: false, progress: 0, message: "", error: null, id: null, result: null });
  const run = async (scenario, dataSource = null) => {
    setState((s) => ({ ...s, running: true, progress: 0, message: "", error: null }));
    try {
      const { id, result } = await runSimulation(scenario, mode, (f, m) => setState((s) => ({ ...s, progress: f, message: m })), dataSource);
      setState({ running: false, progress: 1, message: "", error: null, id, result });
    } catch (e) {
      setState((s) => ({ ...s, running: false, error: e.message }));
    }
  };
  return [state, run];
}
