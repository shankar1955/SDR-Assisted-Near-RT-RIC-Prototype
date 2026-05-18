"""
System Configuration
O-RAN Near-RT RIC Prototype — Shankar M, Chennai Institute of Technology

All tunable parameters in one place.
"""

# ── RIC Core ──────────────────────────────────────────────────────
RIC_CONTROL_LOOP_MS   = 10        # Near-RT RIC target: 10–1000 ms
RIC_TICK_INTERVAL_S   = 0.01      # 10 ms control loop
RIC_MAX_UES           = 10

# ── E2 Interface (Simulated) ─────────────────────────────────────
E2_NODE_ID            = "gNB-001"
E2_INTERFACE_MODE     = "simulated"   # "simulated" | "srsran" (planned)
E2_REPORT_INTERVAL_MS = 10

# ── SDR Platform ─────────────────────────────────────────────────
SDR_PLATFORM          = "ZCU111"      # Zynq UltraScale+ ZCU111
SDR_MODE              = "simulated"   # "simulated" | "hardware" (planned)
SDR_SAMPLE_RATE       = 30.72e6       # 30.72 MSPS (LTE/NR standard)
SDR_CENTER_FREQ       = 3.5e9        # 3.5 GHz — 5G NR n78 band
SDR_BANDWIDTH         = 10e6         # 10 MHz → 50 RBs (NR μ=0)

# ── RAN Parameters ────────────────────────────────────────────────
NUM_CELLS             = 3
NUM_UES               = 10
NUM_RBS               = 50           # Resource blocks (10 MHz, NR μ=0)
SLOT_DURATION_MS      = 1            # 1 ms slot (NR μ=0)

# ── xApp ─────────────────────────────────────────────────────────
XAPP_POLICY           = "pytorch_mlp"   # "pytorch_mlp" | "rule_based"
XAPP_MODEL_PATH       = "results/xapp_policy.pt"
XAPP_INPUT_DIM        = NUM_UES * 3     # [CQI, queue, RSRP] per UE
XAPP_HIDDEN_DIM       = 64
XAPP_OUTPUT_DIM       = NUM_UES         # RB allocation per UE

# ── Logging ───────────────────────────────────────────────────────
LOG_DIR               = "results/"
LOG_LEVEL             = "INFO"
