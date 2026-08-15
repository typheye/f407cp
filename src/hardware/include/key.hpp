#ifndef TOS_KEY_HPP
#define TOS_KEY_HPP

#include "main.h"

enum KeyState : uint8_t {
  KEY_IDLE = 0U,
  KEY_PRESSED,
  KEY_RELEASED,
  KEY_LONG_PRESS,
};

class Key {
public:
  Key(GPIO_TypeDef *port, uint16_t pin);
  void init();
  void tick();
  KeyState getState();
  bool isDown() const;

private:
  GPIO_TypeDef *_port;
  uint16_t _pin;
  bool _stable;
  bool _sample;
  bool _longSent;
  uint32_t _changedAt;
  uint32_t _pressedAt;
  KeyState _event;
};

class KeyManager {
public:
  void init();
  void tick();

  Key up{GPIOA, GPIO_PIN_0};
  Key down{GPIOE, GPIO_PIN_4};
  Key confirm{GPIOE, GPIO_PIN_3};
  Key spare{GPIOE, GPIO_PIN_2};
};

extern KeyManager keyManager;

#endif
