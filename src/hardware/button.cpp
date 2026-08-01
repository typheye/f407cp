#include "include/button.hpp"

namespace {
constexpr uint32_t kDebounceMs = 30U;
}

Button::Button(GPIO_TypeDef *port, uint16_t pin, bool activeLow)
    : _port(port), _pin(pin), _activeLow(activeLow), _stablePressed(false),
      _lastSample(false), _sampleChangedAt(0U), _initialized(false) {}

bool Button::readPressed() const {
  const bool high = HAL_GPIO_ReadPin(_port, _pin) == GPIO_PIN_SET;
  return _activeLow ? !high : high;
}

void Button::init() {
  _stablePressed = readPressed();
  _lastSample = _stablePressed;
  _sampleChangedAt = HAL_GetTick();
  _initialized = true;
}

bool Button::pressed() {
  if (!_initialized)
    init();

  const uint32_t now = HAL_GetTick();
  const bool sample = readPressed();
  if (sample != _lastSample) {
    _lastSample = sample;
    _sampleChangedAt = now;
  }

  if (sample != _stablePressed &&
      static_cast<uint32_t>(now - _sampleChangedAt) >= kDebounceMs) {
    _stablePressed = sample;
    return _stablePressed;
  }
  return false;
}

Button key1(GPIOA, GPIO_PIN_0);
Button key2(GPIOE, GPIO_PIN_4);
Button key3(GPIOE, GPIO_PIN_3);
Button key4(GPIOE, GPIO_PIN_2);
