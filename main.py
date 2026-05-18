import argparse
import logging
import os
import json
import sys

os.makedirs("results", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("results/ric_run.log", mode="w"),
    ]
)
logger = logging.getLogger("Main")

from config.config          import SDR_MODE
from sdr_interface.zcu111_hal  import ZCU111Interface
from e2_interface.e2_node      import SimulatedE2Node
from xapp.xapp_controller      import xAppController
from ric_core.ric              import NearRTRIC


def parse_args():
    p = argparse.ArgumentParser(description="O-RAN Near-RT RIC Prototype")
    p.add_argument("--ticks",  type=int, default=500,
                   help="Number of 10 ms control loop ticks")
    p.add_argument("--log",    type=int, default=50,
                   help="Logging interval (ticks)")
    p.add_argument("--mode",   type=str, default="simulated",
                   choices=["simulated", "hardware"],
                   help="SDR mode: simulated or hardware (ZCU111)")
    return p.parse_args()


def main():
    args = parse_args()

    logger.info("=" * 55)
    logger.info("  O-RAN Near-RT RIC Prototype")
    logger.info("  Shankar M | Chennai Institute of Technology")
    logger.info("=" * 55)
    logger.info(f"  Ticks: {args.ticks} | SDR Mode: {args.mode}")
    logger.info("=" * 55)

    # ── 1. SDR Hardware Abstraction Layer ────────────────────────
    sdr = ZCU111Interface()
    sdr.initialise()

    # Quick SDR self-test
    iq  = sdr.rx_iq_samples(num_samples=1024)
    ch  = sdr.estimate_channel(iq)
    logger.info(
        f"[Main] SDR self-test: IQ={iq.shape}, "
        f"mean CQI={ch['cqi_per_rb'].mean():.1f}"
    )

    # ── 2. Simulated E2 Node (gNB) ───────────────────────────────
    e2_node = SimulatedE2Node()

    # ── 3. xApp Policy ───────────────────────────────────────────
    xapp = xAppController()

    # ── 4. Near-RT RIC ───────────────────────────────────────────
    ric = NearRTRIC(e2_node=e2_node, xapp_controller=xapp)
    ric.setup()

    # ── 5. Run Control Loop ──────────────────────────────────────
    ric.run(num_ticks=args.ticks, log_interval=args.log)

    # ── 6. Results ───────────────────────────────────────────────
    summary = ric.save_metrics("results/ric_metrics.json")
    xapp.save("results/xapp_policy.pt")

    logger.info("")
    logger.info("── Final Summary ──────────────────────────────────")
    logger.info(f"  Loop latency  : {summary['loop_latency']['mean_ms']} ms avg")
    logger.info(f"  < 10 ms ticks : {summary['loop_latency']['pct_under_10ms']} %")
    logger.info(f"  xApp inference: {summary['xapp_inference']['mean_ms']} ms avg")
    logger.info("───────────────────────────────────────────────────")
    logger.info("[Main] Done.")


if __name__ == "__main__":
    main()
