"""
SDR Interface — Zynq UltraScale+ ZCU111
-----------------------------------------
Abstracts the SDR hardware layer from the RIC control logic.

Current status: STUB / SIMULATED
- Returns synthetic IQ samples and channel estimates
- Hardware abstraction layer (HAL) is defined so real ZCU111
  driver calls can be dropped in without changing upper layers

Planned hardware path:
  ZCU111 (RFdc tile, 4x ADC/DAC @ 4 GSPS)
    → PYNQ framework (Python control plane over AXI4)
      → GNU Radio / UHD driver
        → This interface

Real integration requires:
  - PYNQ overlay with RF data converter IP
  - UHD ZCU111 BSP or custom DMA driver
  - GNU Radio ZCU111 source/sink block

Author: Shankar M, Chennai Institute of Technology
"""

import numpy as np
import logging
from config.config import (SDR_PLATFORM, SDR_MODE,
                            SDR_SAMPLE_RATE, SDR_CENTER_FREQ,
                            SDR_BANDWIDTH, NUM_RBS)

logger = logging.getLogger("SDR")


class SDRConfig:
    def __init__(self):
        self.platform     = SDR_PLATFORM
        self.sample_rate  = SDR_SAMPLE_RATE
        self.center_freq  = SDR_CENTER_FREQ
        self.bandwidth    = SDR_BANDWIDTH
        self.rx_gain_db   = 30
        self.tx_gain_db   = 20

    def __repr__(self):
        return (
            f"SDRConfig(platform={self.platform}, "
            f"fs={self.sample_rate/1e6:.2f} MSPS, "
            f"fc={self.center_freq/1e9:.2f} GHz, "
            f"BW={self.bandwidth/1e6:.1f} MHz)"
        )


class ZCU111Interface:
    """
    Hardware Abstraction Layer for ZCU111 SDR platform.

    Methods mirror what a real PYNQ/UHD driver would expose,
    so upper layers (RIC, xApp) are hardware-agnostic.
    """

    def __init__(self):
        self.config   = SDRConfig()
        self.mode     = SDR_MODE
        self._active  = False
        logger.info(f"[SDR] {self.config}")
        if self.mode == "simulated":
            logger.warning(
                "[SDR] Running in SIMULATED mode. "
                "Real ZCU111 PYNQ driver integration pending."
            )

    def initialise(self):
        """
        Real: Load PYNQ overlay, configure RFdc tiles, set Fs and Fc.
        Simulated: log and proceed.
        """
        if self.mode == "hardware":
            # TODO: from pynq import Overlay
            # TODO: ol = Overlay("oran_ric.bit")
            # TODO: ol.rfdc.set_mixer_freq(0, self.config.center_freq)
            raise NotImplementedError(
                "Hardware mode not yet implemented. "
                "Requires PYNQ overlay and ZCU111 BSP."
            )
        logger.info("[SDR] Initialised (simulated RFdc tile, 4x ADC @ 4 GSPS)")
        self._active = True

    def rx_iq_samples(self, num_samples=1024):
        """
        Receive IQ samples from RF front-end.
        Real: DMA transfer from PL → PS memory via AXI4-Stream.
        Simulated: AWGN + tone at carrier.
        """
        if not self._active:
            raise RuntimeError("SDR not initialised.")

        if self.mode == "hardware":
            raise NotImplementedError("Hardware RX not yet implemented.")

        # Simulated: multi-UE uplink signals (OFDM subcarriers + noise)
        t    = np.arange(num_samples) / self.config.sample_rate
        sig  = np.zeros(num_samples, dtype=complex)
        for k in range(1, 5):    # 4 simulated UEs transmitting
            fc_offset = (k - 2) * 180e3   # 180 kHz subcarrier spacing
            sig += (0.3 / k) * np.exp(1j * 2 * np.pi * fc_offset * t)
        noise = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * 0.05
        return sig + noise

    def estimate_channel(self, iq_samples):
        """
        Coarse per-RB channel estimation (power-based).
        Real: pilot-based LS/MMSE estimation over DMRS symbols.
        Simulated: FFT power per RB bin.
        """
        spectrum = np.abs(np.fft.fft(iq_samples, n=NUM_RBS * 12)) ** 2
        rb_power = np.array([
            np.mean(spectrum[k * 12:(k + 1) * 12])
            for k in range(NUM_RBS)
        ])
        # Map power to simulated CQI (1–15)
        rb_power_norm = rb_power / (rb_power.max() + 1e-9)
        cqi_per_rb    = np.clip((rb_power_norm * 14).astype(int) + 1, 1, 15)
        return {"rb_power_dbm": 10 * np.log10(rb_power + 1e-12),
                "cqi_per_rb":   cqi_per_rb}

    def tx_control_signal(self, allocation: dict):
        """
        Transmit RB allocation as downlink control (DCI-like).
        Real: encode as PDCCH DCI format 0_1, IFFT → DAC → RF.
        Simulated: log only.
        """
        logger.debug(f"[SDR] TX control | allocation={allocation}")
        # TODO: encode allocation into DCI, OFDM modulate, send via DAC

    def shutdown(self):
        self._active = False
        logger.info("[SDR] Interface shutdown.")
