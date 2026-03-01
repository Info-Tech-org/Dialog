#pragma once

#include <Arduino.h>
#include <Wire.h>

// Minimal DRV2605L (DRV2605LDGST) driver for Arduino/PlatformIO.
// Datasheet register map compatible with DRV2605L family.

class DRV2605L {
 public:
  explicit DRV2605L(uint8_t i2cAddr = 0x5A);

  bool begin(TwoWire& wire = Wire);

  bool setMode(uint8_t mode);
  bool setLibrary(uint8_t library);

  // Real-time playback (RTP)
  bool setRtpValue(uint8_t value);

  // Actuator selection (Feedback Control register bit7)
  bool selectERM();
  bool selectLRA();

  // Common configuration registers
  bool setRatedVoltage(uint8_t value);
  bool setOverdriveClamp(uint8_t value);
  bool setControl1(uint8_t value);
  bool setControl2(uint8_t value);
  bool setControl3(uint8_t value);
  bool setControl4(uint8_t value);

  // Auto calibration (MODE=0x07). Returns true if GO clears within timeout.
  bool autoCalibrate(uint32_t timeoutMs = 2000);

  bool setWaveform(uint8_t slot, uint8_t effect);
  bool go();
  bool stop();
  bool waitUntilDone(uint32_t timeoutMs = 1500);

  // Convenience: internal trigger playback (MODE=0)
  bool playEffect(uint8_t effect, bool wait = true, uint32_t timeoutMs = 1500);

  bool readStatus(uint8_t& status);

 private:
  bool writeReg(uint8_t reg, uint8_t value);
  bool readReg(uint8_t reg, uint8_t& value);

  uint8_t addr;
  TwoWire* wireBus = nullptr;
};
