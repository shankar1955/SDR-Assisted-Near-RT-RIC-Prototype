# O-RAN Near-RT RIC Prototype
**SDR-Assisted Near-RT RIC Prototype for AI-Driven xApp Deployment on O-RAN OSC Stack**

**Author:** Shankar M, B.E. EEE, Chennai Institute of Technology
**Platform:** Zynq UltraScale+ ZCU111
**Status:** 🔧 Work in Progress — Simulated end-to-end, hardware integration pending

---

## Overview
This project prototypes a Near-Real-Time RAN Intelligent Controller (Near-RT RIC) targeting the O-RAN Software Community (OSC) architecture. A PyTorch-based xApp runs inside the RIC control loop and drives per-UE resource block (RB) allocation via a simulated E2 interface, targeting sub-10ms closed-loop latency.

The SDR platform (ZCU111) provides the radio front-end, with a hardware abstraction layer (HAL) designed for drop-in replacement once the PYNQ overlay and real E2 agent are ready.

---

## System Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Near-RT RIC                         │
│                                                       │
│  ┌─────────────────┐     ┌────────────────────────┐  │
│  │ Subscription Mgr│     │     xApp Manager        │  │
│  │ (E2SM-KPM sub)  │────▶│  ┌──────────────────┐  │  │
│  └─────────────────┘     │  │ xApp Policy (MLP) │  │  │
│           │              │  │ PyTorch | <1ms    │  │  │
│           │              │  └──────────────────┘  │  │
│           ▼              └────────────────────────┘  │
│  ┌─────────────────┐              │                   │
│  │  E2 Termination │◀─────────────┘ RC Control        │
│  └────────┬────────┘                                  │
└───────────┼──────────────────────────────────────────┘
            │  E2 Interface (simulated / srsRAN planned)
            ▼
┌──────────────────────────────────────────────────────┐
│            Simulated E2 Node (gNB)                    │
│  E2SM-KPM: per-UE CQI, RSRP, queue, throughput       │
│  E2SM-RC:  RB allocation override → MAC scheduler     │
│                                                       │
│  Planned: srsRAN / OAI gNB with real E2 agent         │
└──────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────┐
│         ZCU111 SDR (Hardware Abstraction Layer)       │
│  RFdc tile | 4x ADC/DAC @ 4 GSPS | 3.5 GHz n78       │
│  PYNQ overlay + GNU Radio integration (planned)       │
└──────────────────────────────────────────────────────┘
```

---

## Project Structure
```
oran_nearrt_ric/
├── config/
│   └── config.py              # All system parameters
├── e2_interface/
│   └── e2_node.py             # Simulated E2 node (E2SM-KPM + E2SM-RC)
├── xapp/
│   └── xapp_controller.py     # PyTorch MLP policy + inference loop
├── ric_core/
│   └── ric.py                 # Near-RT RIC: SubMgr, xAppMgr, control loop
├── sdr_interface/
│   └── zcu111_hal.py          # ZCU111 HAL (simulated / hardware stub)
├── utils/                     # Plotting and metrics (in progress)
├── results/                   # Run logs, Q-table, model checkpoints
└── main.py                    # Entry point
```

---

## Current Progress
- [x] Simulated E2 node with E2SM-KPM report structure (CQI, RSRP, queue, throughput)
- [x] E2SM-RC control message application (RB allocation override)
- [x] Near-RT RIC control loop: SubMgr → xApp → E2T (10 ms tick)
- [x] PyTorch MLP xApp policy (architecture defined, untrained)
- [x] Per-cell RB budget enforcement (softmax allocation head)
- [x] ZCU111 HAL with simulated IQ samples + channel estimation
- [x] Latency profiling (loop ms, inference ms, % ticks under 10 ms)
- [ ] xApp policy training (REINFORCE / policy gradient — in progress)
- [ ] OSC Near-RT RIC Docker deployment (next milestone)
- [ ] Real E2 interface: srsRAN e2_agent → SCTP → RIC E2T
- [ ] PYNQ overlay for ZCU111 RFdc tile (hardware bring-up)
- [ ] xApp registration via OSC xApp Manager REST API

---

## Requirements
```
numpy
torch
```
Install:
```bash
pip install numpy torch
```

---

## Run
```bash
python main.py                 # 500 ticks, simulated
python main.py --ticks 200     # shorter run
```

Sample output:
```
[RIC] Tick   50 | AvgLoop: 1.23 ms | TotalTP: 18.4 Mbps | <10ms: 100%
[RIC] Tick  100 | AvgLoop: 1.19 ms | TotalTP: 17.9 Mbps | <10ms: 100%
...
── Final Summary ──────────────────────────────────
  Loop latency  : 1.21 ms avg
  < 10 ms ticks : 100.0 %
  xApp inference: 0.43 ms avg
```

---

## Planned Next Steps (pre-NTUST arrival)
1. Train xApp policy via REINFORCE against spectral efficiency + Jain fairness reward
2. Deploy OSC Near-RT RIC locally (Docker Compose)
3. Connect srsRAN E2 agent to RIC E2T via SCTP (loopback first)
4. Migrate xApp into OSC xApp SDK (Python SDK, REST registration)
5. ZCU111 PYNQ overlay bring-up (RFdc tile, DMA IQ pipeline)
