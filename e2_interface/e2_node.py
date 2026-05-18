"""
Simulated E2 Node (gNB-side)
-----------------------------
In a real O-RAN deployment, this would be a gNB running OAI or srsRAN
reporting RAN metrics to the Near-RT RIC via the E2 Application Protocol
(E2AP) over SCTP.

Current status: SIMULATED
- Generates realistic per-UE KPMs (CQI, RSRP, queue depth, throughput)
- Mimics E2SM-KPM report service model structure
- Accepts E2SM-RC control messages (RB allocation commands)

Planned:
- Replace with real srsRAN E2 agent connection
- Implement actual E2AP message serialisation (ASN.1)

Author: Shankar M, Chennai Institute of Technology
"""

import numpy as np
import time
import logging
from config.config import (NUM_UES, NUM_CELLS, NUM_RBS,
                            E2_NODE_ID, E2_REPORT_INTERVAL_MS)

logger = logging.getLogger("E2Node")


class UEContext:
    """Holds live RAN state for a single UE."""

    def __init__(self, ue_id):
        self.ue_id       = ue_id
        self.cell_id     = ue_id % NUM_CELLS
        self.rsrp        = np.random.uniform(-110, -70)   # dBm
        self.cqi         = self._rsrp_to_cqi(self.rsrp)
        self.queue_depth = np.random.randint(5, 40)       # packets
        self.throughput  = 0.0                             # Mbps
        self.rb_alloc    = 0                               # current RBs
        self.traffic     = np.random.choice(["eMBB", "URLLC", "mMTC"])

    def _rsrp_to_cqi(self, rsrp):
        cqi = int((rsrp + 110) / 40 * 14) + 1
        return int(np.clip(cqi, 1, 15))

    def step(self):
        """Advance channel and queue by one slot."""
        # Rayleigh random walk
        self.rsrp += np.random.normal(0, 1.5)
        self.rsrp  = float(np.clip(self.rsrp, -120, -60))
        self.cqi   = self._rsrp_to_cqi(self.rsrp)

        # Throughput from allocation
        self.throughput = self.rb_alloc * self.cqi * 0.075   # simplified Mbps

        # Queue drain + Poisson arrivals
        drain = int(self.throughput * 2)
        lam   = {"eMBB": 4, "URLLC": 1, "mMTC": 2}[self.traffic]
        arrival = np.random.poisson(lam)
        self.queue_depth = int(np.clip(self.queue_depth - drain + arrival, 0, 200))

    def to_kpm_report(self):
        """
        Mimics E2SM-KPM Indication Message structure.
        Real implementation would serialise this as ASN.1 PER.
        """
        return {
            "ue_id":        self.ue_id,
            "cell_id":      self.cell_id,
            "rsrp_dbm":     round(self.rsrp, 2),
            "cqi":          self.cqi,
            "queue_depth":  self.queue_depth,
            "throughput_mbps": round(self.throughput, 3),
            "traffic_type": self.traffic,
        }


class SimulatedE2Node:
    """
    Simulated gNB E2 Agent.

    Exposes two interfaces matching real E2AP service models:
      - get_kpm_report()  : E2SM-KPM (Key Performance Metrics)
      - apply_rc_control(): E2SM-RC  (RAN Control — RB allocation)

    TODO: Replace internals with srsRAN e2_agent socket connection.
    """

    def __init__(self):
        self.node_id  = E2_NODE_ID
        self.ues      = [UEContext(i) for i in range(NUM_UES)]
        self.tick     = 0
        self._connected = False
        logger.info(f"[E2Node] Simulated E2 node initialised: {self.node_id}")
        logger.info(f"[E2Node] {NUM_UES} UEs | {NUM_CELLS} cells | {NUM_RBS} RBs")

    def connect(self):
        """
        Simulate E2 Setup Procedure (E2AP Setup Request/Response).
        Real: SCTP connect to Near-RT RIC on port 36421.
        """
        logger.info(f"[E2Node] E2 Setup Request → RIC (simulated SCTP handshake)")
        time.sleep(0.01)   # simulate handshake latency
        self._connected = True
        logger.info(f"[E2Node] E2 Setup Response received — connection established")

    def get_kpm_report(self):
        """
        E2SM-KPM Indication — reports per-UE metrics to Near-RT RIC.
        Called every E2_REPORT_INTERVAL_MS by the RIC subscription.
        """
        if not self._connected:
            raise RuntimeError("E2 node not connected. Call connect() first.")

        for ue in self.ues:
            ue.step()

        report = {
            "node_id":    self.node_id,
            "tick":       self.tick,
            "timestamp":  round(time.time(), 4),
            "ue_reports": [ue.to_kpm_report() for ue in self.ues]
        }
        self.tick += 1
        return report

    def apply_rc_control(self, allocation: dict):
        """
        E2SM-RC Control Message — receives RB allocation from xApp.
        allocation: {ue_id: num_rbs}

        Real implementation: deserialise E2AP RIC Control Request,
        apply scheduling override to gNB MAC scheduler.
        """
        for ue in self.ues:
            ue.rb_alloc = allocation.get(ue.ue_id, 0)

        total_per_cell = {}
        for ue in self.ues:
            total_per_cell[ue.cell_id] = (
                total_per_cell.get(ue.cell_id, 0) + ue.rb_alloc
            )

        for cell_id, used in total_per_cell.items():
            if used > NUM_RBS:
                logger.warning(
                    f"[E2Node] Cell {cell_id} RB overuse: {used}/{NUM_RBS}"
                )

        logger.debug(f"[E2Node] RC Control applied | tick={self.tick}")
