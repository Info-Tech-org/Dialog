#include "drv2605l.h"

// Register map (DRV2605L)
static constexpr uint8_t REG_STATUS = 0x00;
static constexpr uint8_t REG_MODE = 0x01;
static constexpr uint8_t REG_RTP_INPUT = 0x02;
static constexpr uint8_t REG_LIB_SEL = 0x03;
static constexpr uint8_t REG_WAVESEQ1 = 0x04; // 0x04..0x0B
static constexpr uint8_t REG_GO = 0x0C;
static constexpr uint8_t REG_RATED_VOLTAGE = 0x16;
static constexpr uint8_t REG_OVERDRIVE_CLAMP = 0x17;
static constexpr uint8_t REG_FEEDBACK_CTRL = 0x1A;
static constexpr uint8_t REG_CONTROL1 = 0x1B;
static constexpr uint8_t REG_CONTROL2 = 0x1C;
static constexpr uint8_t REG_CONTROL3 = 0x1D;
static constexpr uint8_t REG_CONTROL4 = 0x1E;

DRV2605L::DRV2605L(uint8_t i2cAddr) : addr(i2cAddr) {}

bool DRV2605L::begin(TwoWire& wire) {
  wireBus = &wire;

  // Basic probe
  uint8_t status = 0;
  if (!readReg(REG_STATUS, status)) {
    return false;
  }

  // Put in internal trigger mode by default.
  // MODE bits: 0x00 = internal trigger
  if (!setMode(0x00)) return false;

  // Select library 1 (ERM) as a safe default; users can change later.
  if (!setLibrary(0x01)) return false;

  // Clear waveforms
  for (uint8_t i = 0; i < 8; i++) {
    if (!setWaveform(i, 0x00)) return false;
  }
  (void)stop();
  return true;
}

bool DRV2605L::setMode(uint8_t mode) {
  return writeReg(REG_MODE, mode);
}

bool DRV2605L::setLibrary(uint8_t library) {
  return writeReg(REG_LIB_SEL, library);
}

bool DRV2605L::setRtpValue(uint8_t value) {
  return writeReg(REG_RTP_INPUT, value);
}

bool DRV2605L::selectERM() {
  uint8_t v = 0;
  if (!readReg(REG_FEEDBACK_CTRL, v)) return false;
  // Bit7: 0=ERM, 1=LRA
  v = (uint8_t)(v & ~(1u << 7));
  return writeReg(REG_FEEDBACK_CTRL, v);
}

bool DRV2605L::selectLRA() {
  uint8_t v = 0;
  if (!readReg(REG_FEEDBACK_CTRL, v)) return false;
  v = (uint8_t)(v | (1u << 7));
  return writeReg(REG_FEEDBACK_CTRL, v);
}

bool DRV2605L::setRatedVoltage(uint8_t value) {
  return writeReg(REG_RATED_VOLTAGE, value);
}

bool DRV2605L::setOverdriveClamp(uint8_t value) {
  return writeReg(REG_OVERDRIVE_CLAMP, value);
}

bool DRV2605L::setControl1(uint8_t value) {
  return writeReg(REG_CONTROL1, value);
}

bool DRV2605L::setControl2(uint8_t value) {
  return writeReg(REG_CONTROL2, value);
}

bool DRV2605L::setControl3(uint8_t value) {
  return writeReg(REG_CONTROL3, value);
}

bool DRV2605L::setControl4(uint8_t value) {
  return writeReg(REG_CONTROL4, value);
}

bool DRV2605L::autoCalibrate(uint32_t timeoutMs) {
  // Datasheet: MODE=0x07 triggers auto-calibration when GO is set.
  if (!setMode(0x07)) return false;
  if (!go()) return false;
  if (!waitUntilDone(timeoutMs)) return false;

  // Return to internal trigger mode afterwards.
  return setMode(0x00);
}

bool DRV2605L::setWaveform(uint8_t slot, uint8_t effect) {
  if (slot >= 8) return false;
  return writeReg((uint8_t)(REG_WAVESEQ1 + slot), effect);
}

bool DRV2605L::go() {
  return writeReg(REG_GO, 0x01);
}

bool DRV2605L::stop() {
  return writeReg(REG_GO, 0x00);
}

bool DRV2605L::waitUntilDone(uint32_t timeoutMs) {
  const uint32_t start = millis();
  while ((millis() - start) < timeoutMs) {
    uint8_t go = 0;
    if (!readReg(REG_GO, go)) return false;
    if ((go & 0x01) == 0) return true;
    delay(5);
  }
  return false;
}

bool DRV2605L::playEffect(uint8_t effect, bool wait, uint32_t timeoutMs) {
  // Internal trigger mode
  if (!setMode(0x00)) return false;

  // Waveform sequence: slot0=effect, slot1=0(end)
  if (!setWaveform(0, effect)) return false;
  if (!setWaveform(1, 0x00)) return false;

  if (!go()) return false;
  if (!wait) return true;
  return waitUntilDone(timeoutMs);
}

bool DRV2605L::readStatus(uint8_t& status) {
  return readReg(REG_STATUS, status);
}

bool DRV2605L::writeReg(uint8_t reg, uint8_t value) {
  if (wireBus == nullptr) return false;

  wireBus->beginTransmission(addr);
  wireBus->write(reg);
  wireBus->write(value);
  return (wireBus->endTransmission() == 0);
}

bool DRV2605L::readReg(uint8_t reg, uint8_t& value) {
  if (wireBus == nullptr) return false;

  wireBus->beginTransmission(addr);
  wireBus->write(reg);
  if (wireBus->endTransmission(false) != 0) return false;

  const uint8_t n = wireBus->requestFrom((int)addr, 1);
  if (n != 1) return false;
  value = wireBus->read();
  return true;
}
