"""
Near-RT RIC Core
-----------------
Orchestrates the 10 ms control loop:
  1. Subscribe to E2 node KPM reports
  2. Feed metrics to xApp
  3. Push RB allocation back via E2SM-RC control

This mimics the OSC Near-RT RIC (RIC platform) internal structure:
  - Subscription Manager  → manages E2SM-KPM subscriptions
  - xApp Manager          → registers and invokes xApps
  - E2 Termination (E2T)  → handles E2 message routing

Current mode: fully simulated (no actual OSC Docker stack yet)
Planned: wrap this logic inside OSC xApp SDK framework

Author: Shankar M, Chennai Institute of Technology
"""

import time
import logging
import json
import numpy as np
from config.config import RIC_TICK_INTERVAL_S, RIC_CONTROL_LOOP_MS

logger = logging.getLogger("NearRT_RIC")


class SubscriptionManager:
    """
    Manages E2SM-KPM subscription state.
    In OSC, this maps to the Subscription Manager microservice.
    """

    def __init__(self):
        self.subscriptions = {}

    def subscribe(self, e2_node, report_interval_ms=10):
        node_id = e2_node.node_id
        self.subscriptions[node_id] = {
            "e2_node":           e2_node,
            "report_interval_ms": report_interval_ms,
            "sub_id":            f"sub-{node_id}-kpm",
            "active":            True,
        }
        logger.info(
            f"[SubMgr] KPM subscription created: {node_id} "
            f"@ {report_interval_ms} ms interval"
        )

    def get_report(self, node_id):
        sub = self.subscriptions.get(node_id)
        if not sub or not sub["active"]:
            raise RuntimeError(f"No active subscription for {node_id}")
        return sub["e2_node"].get_kpm_report()


class xAppManager:
    """
    Registers xApps and routes KPM indications to them.
    In OSC, xApps register via the xApp Manager REST API.
    """

    def __init__(self):
        self.xapps = {}

    def register(self, name, xapp):
        self.xapps[name] = xapp
        logger.info(f"[xAppMgr] xApp registered: '{name}'")

    def invoke(self, name, kpm_report):
        xapp = self.xapps.get(name)
        if xapp is None:
            raise RuntimeError(f"xApp '{name}' not registered")
        return xapp.run_inference(kpm_report)


class NearRTRIC:
    """
    Near-RT RIC main controller.
    Runs the 10 ms control loop: KPM → xApp → RC Control.
    """

    def __init__(self, e2_node, xapp_controller):
        self.sub_mgr   = SubscriptionManager()
        self.xapp_mgr  = xAppManager()
        self.e2_node   = e2_node
        self.xapp      = xapp_controller

        self.loop_latencies_ms = []
        self.metrics_log       = []
        self._tick             = 0

    def setup(self):
        """E2 Setup + subscription + xApp registration."""
        logger.info("[RIC] Starting E2 Setup procedure...")
        self.e2_node.connect()

        self.sub_mgr.subscribe(self.e2_node, report_interval_ms=10)
        self.xapp_mgr.register("rb_scheduler", self.xapp)
        logger.info("[RIC] Setup complete. Ready to run control loop.")

    def run(self, num_ticks=500, log_interval=50):
        """
        Main Near-RT RIC control loop.

        Each iteration:
          T0  — request KPM report from E2 node
          T1  — xApp inference → RB allocation
          T2  — push RC control to E2 node
          Tmeasure loop latency, enforce 10 ms tick budget
        """
        logger.info(
            f"[RIC] Control loop started | "
            f"ticks={num_ticks} | target={RIC_CONTROL_LOOP_MS} ms"
        )

        for tick in range(num_ticks):
            t_loop_start = time.perf_counter()

            # ── Step 1: KPM Indication ────────────────────────────
            kpm = self.sub_mgr.get_report(self.e2_node.node_id)

            # ── Step 2: xApp inference ────────────────────────────
            allocation, infer_ms = self.xapp_mgr.invoke("rb_scheduler", kpm)

            # ── Step 3: E2SM-RC Control ───────────────────────────
            self.e2_node.apply_rc_control(allocation)

            # ── Metrics ───────────────────────────────────────────
            loop_ms = (time.perf_counter() - t_loop_start) * 1000
            self.loop_latencies_ms.append(loop_ms)

            ue_reports  = kpm["ue_reports"]
            avg_cqi     = np.mean([u["cqi"] for u in ue_reports])
            avg_queue   = np.mean([u["queue_depth"] for u in ue_reports])
            total_tp    = sum(u["throughput_mbps"] for u in ue_reports)

            self.metrics_log.append({
                "tick":        tick,
                "loop_ms":     round(loop_ms, 3),
                "infer_ms":    round(infer_ms, 3),
                "avg_cqi":     round(avg_cqi, 2),
                "avg_queue":   round(avg_queue, 1),
                "total_tp_mbps": round(total_tp, 3),
            })

            if (tick + 1) % log_interval == 0:
                recent = self.metrics_log[-log_interval:]
                avg_loop  = np.mean([m["loop_ms"]       for m in recent])
                avg_tp    = np.mean([m["total_tp_mbps"] for m in recent])
                under_10  = np.mean([m["loop_ms"] < 10  for m in recent]) * 100
                logger.info(
                    f"[RIC] Tick {tick+1:>4} | "
                    f"AvgLoop: {avg_loop:.2f} ms | "
                    f"TotalTP: {avg_tp:.2f} Mbps | "
                    f"<10ms: {under_10:.0f}%"
                )

            # Enforce tick budget (sleep remainder of 10 ms slot)
            elapsed = (time.perf_counter() - t_loop_start)
            sleep_s = max(0, RIC_TICK_INTERVAL_S - elapsed)
            time.sleep(sleep_s)

            self._tick += 1

        logger.info("[RIC] Control loop complete.")

    def save_metrics(self, path="results/ric_metrics.json"):
        summary = {
            "loop_latency": {
                "mean_ms":        round(np.mean(self.loop_latencies_ms), 3),
                "max_ms":         round(np.max(self.loop_latencies_ms), 3),
                "pct_under_10ms": round(
                    np.mean(np.array(self.loop_latencies_ms) < 10) * 100, 1
                )
            },
            "xapp_inference": self.xapp.latency_summary(),
            "tick_log":       self.metrics_log
        }
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"[RIC] Metrics saved → {path}")
        return summary
