#include "include/key.hpp"

namespace {
constexpr uint32_t kDebounceMs = 25U;
constexpr uint32_t kLongPressMs = 700U;
}

Key::Key(GPIO_TypeDef *port, uint16_t pin)
    : _port(port), _pin(pin), _stable(false), _sample(false),
      _longSent(false), _changedAt(0U), _pressedAt(0U), _event(KEY_IDLE) {}

bool Key::isDown() const {
  return HAL_GPIO_ReadPin(_port, _pin) == GPIO_PIN_RESET;
}

void Key::init() {
  _stable = isDown();
  _sample = _stable;
  _changedAt = HAL_GetTick();
  _pressedAt = _changedAt;
  _longSent = false;
  _event = KEY_IDLE;
}

void Key::tick() {
  const uint32_t now = HAL_GetTick();
  const bool sample = isDown();
  if (sample != _sample) {
    _sample = sample;
    _changedAt = now;
  }
  if (sample != _stable && static_cast<uint32_t>(now - _changedAt) >= kDebounceMs) {
    _stable = sample;
    if (_stable) {
      _pressedAt = now;
      _longSent = false;
      _event = KEY_PRESSED;
    } else {
      _event = KEY_RELEASED;
    }
  }
  if (_stable && !_longSent &&
      static_cast<uint32_t>(now - _pressedAt) >= kLongPressMs) {
    _longSent = true;
    _event = KEY_LONG_PRESS;
  }
}

KeyState Key::getState() {
  tick();
  const KeyState result = _event;
  _event = KEY_IDLE;
  return result;
}

KeyManager keyManager;

void KeyManager::init() {
  up.init();
  down.init();
  confirm.init();
  spare.init();
}

void KeyManager::tick() {
  up.tick();
  down.tick();
  confirm.tick();
  spare.tick();
}
