"""
PyTorch-Based xApp Policy
--------------------------
Lightweight MLP that maps per-UE RAN metrics → RB allocation decisions.
Designed to run inside the Near-RT RIC control loop (<10 ms inference).

Architecture:
  Input:  [CQI, queue_norm, RSRP_norm] × NUM_UES  (30-dim)
  Hidden: 64 → 64 (ReLU)
  Output: NUM_UES soft allocation weights → scaled to RB budget

Training status: UNTRAINED (random weights — training loop in progress)
Planned: Train via policy gradient (REINFORCE) against SE + Jain reward.

Author: Shankar M, Chennai Institute of Technology
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import logging
from config.config import (XAPP_INPUT_DIM, XAPP_HIDDEN_DIM,
                            XAPP_OUTPUT_DIM, NUM_RBS, NUM_CELLS, NUM_UES)

logger = logging.getLogger("xApp")


class xAppPolicyNet(nn.Module):
    """
    MLP policy network.
    Output is passed through softmax per cell to produce
    a valid RB allocation summing to NUM_RBS per cell.
    """

    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(XAPP_INPUT_DIM, XAPP_HIDDEN_DIM)
        self.fc2 = nn.Linear(XAPP_HIDDEN_DIM, XAPP_HIDDEN_DIM)
        self.fc3 = nn.Linear(XAPP_HIDDEN_DIM, XAPP_OUTPUT_DIM)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)   # raw logits — allocation head applies softmax


class xAppController:
    """
    xApp runtime.
    Wraps the policy network with:
      - State extraction from E2SM-KPM reports
      - Per-cell softmax normalisation (respects RB budget)
      - Control message generation (E2SM-RC format)
      - Latency tracking
    """

    def __init__(self):
        self.model     = xAppPolicyNet()
        self.device    = torch.device("cpu")    # ZCU111 ARM core target
        self.model.to(self.device)
        self.model.eval()

        # UE → cell mapping (needed for per-cell RB budget enforcement)
        self.ue_cell_map = {i: i % NUM_CELLS for i in range(NUM_UES)}

        self.inference_times_ms = []
        logger.info("[xApp] Policy network initialised (untrained — random weights)")
        logger.info(f"[xApp] Params: {sum(p.numel() for p in self.model.parameters())}")

    def _extract_state(self, kpm_report):
        """
        Converts E2SM-KPM report → normalised state tensor.
        Shape: (1, NUM_UES * 3)  →  [CQI/15, queue/200, (RSRP+120)/60] per UE
        """
        state = []
        ue_map = {r["ue_id"]: r for r in kpm_report["ue_reports"]}

        for ue_id in range(NUM_UES):
            r = ue_map.get(ue_id, {})
            state.append(r.get("cqi", 7) / 15.0)
            state.append(r.get("queue_depth", 0) / 200.0)
            state.append((r.get("rsrp_dbm", -90) + 120) / 60.0)

        return torch.tensor(state, dtype=torch.float32).unsqueeze(0)

    def _allocate_rbs(self, logits):
        """
        Per-cell softmax → integer RB allocation.
        Ensures sum of RBs per cell == NUM_RBS.
        """
        logits_np = logits.detach().numpy().flatten()
        allocation = {}

        for cell_id in range(NUM_CELLS):
            ue_ids = [uid for uid, cid in self.ue_cell_map.items()
                      if cid == cell_id]
            cell_logits = torch.tensor([logits_np[uid] for uid in ue_ids])
            weights = F.softmax(cell_logits, dim=0).numpy()

            # Scale to integer RBs
            rbs = np.floor(weights * NUM_RBS).astype(int)
            # Distribute remainder to highest-weight UE
            remainder = NUM_RBS - rbs.sum()
            if remainder > 0:
                rbs[np.argmax(weights)] += remainder

            for i, uid in enumerate(ue_ids):
                allocation[uid] = int(rbs[i])

        return allocation

    def run_inference(self, kpm_report):
        """
        Full xApp control cycle:
        1. Extract state from KPM report
        2. Forward pass through policy net
        3. Allocate RBs (per-cell budget enforced)
        4. Return E2SM-RC control dict + latency

        Target: <10 ms end-to-end
        """
        import time
        t0 = time.perf_counter()

        state_tensor = self._extract_state(kpm_report)

        with torch.no_grad():
            logits = self.model(state_tensor)

        allocation = self._allocate_rbs(logits)

        latency_ms = (time.perf_counter() - t0) * 1000
        self.inference_times_ms.append(latency_ms)

        logger.debug(
            f"[xApp] Inference {latency_ms:.3f} ms | "
            f"alloc={list(allocation.values())}"
        )

        return allocation, latency_ms

    def save(self, path):
        torch.save(self.model.state_dict(), path)
        logger.info(f"[xApp] Model saved → {path}")

    def load(self, path):
        self.model.load_state_dict(torch.load(path, map_location=self.device))
        self.model.eval()
        logger.info(f"[xApp] Model loaded ← {path}")

    def latency_summary(self):
        t = self.inference_times_ms
        if not t:
            return {}
        return {
            "count":   len(t),
            "mean_ms": round(np.mean(t), 3),
            "max_ms":  round(np.max(t), 3),
            "min_ms":  round(np.min(t), 3),
            "pct_under_10ms": round(np.mean(np.array(t) < 10.0) * 100, 1)
        }
