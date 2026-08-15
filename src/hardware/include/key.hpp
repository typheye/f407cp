#ifndef KEY_HPP
#define KEY_HPP

#include "main.h"
#include "stm32f4xx_hal.h"
#include "core/sdk/include/tos_api.h"

typedef enum { SW_OFF = 0, SW_ON = 1 } SwitchState_t;
typedef enum {
  KEY_IDLE = 0,
  KEY_PRESSED = 1,
  KEY_RELEASED = 2,
  KEY_LONG_PRESS = 3
} KeyState_t;

class Switch {
public:
  Switch(GPIO_TypeDef *port = nullptr, uint16_t pin = 0U, bool inverted = false);
  void init(void);
  bool isOn(void);
  bool isOff(void);
private:
  GPIO_TypeDef *_port;
  uint16_t _pin;
  bool _inverted;
  bool _initialized;
};

#define KEY_DEBOUNCE_CNT 3
#define KEY_SCAN_INTERVAL_MS 1U

class Key {
public:
  Key(GPIO_TypeDef *port = nullptr, uint16_t pin = 0U, bool inverted = false);
  void init(void);
  bool isPressed(void);
  bool isReleased(void);
  KeyState_t getState(void);
  void tick(void);
  void setLongPressTime(uint32_t ms);

private:
  bool rawPressed(void) const;
  void latchEvent(KeyState_t event);

  GPIO_TypeDef *_port;
  uint16_t _pin;
  bool _inverted;
  bool _lastState;
  bool _longPressTriggered;
  uint32_t _pressStartTime;
  uint32_t _longPressTime;
  uint32_t _lastSampleTime;
  uint8_t _debounce;
  KeyState_t _event;
  bool _initialized;
};

class KeyManager {
public:
  KeyManager();
  void init(void);
  void tick(void);

  Switch _sw1E0{nullptr, 0U, false};
  Switch _sw2G13{nullptr, 0U, false};
  Switch _sw3E2{nullptr, 0U, false};
  Switch _sw4E4{nullptr, 0U, false};
  Switch _sw5D6{nullptr, 0U, true};
  Switch _sw6G9{nullptr, 0U, true};
  Switch _sw7G11{nullptr, 0U, true};
  Switch _sw8G10{nullptr, 0U, true};
  Switch _sw9G15{nullptr, 0U, true};
  Switch _sw10G3{nullptr, 0U, false};
  Switch _sw11D15{nullptr, 0U, false};
  Switch _sw12B12{nullptr, 0U, false};
  Switch _sw13B14{nullptr, 0U, false};
  Switch _swSdDetect{GPIOE, GPIO_PIN_1, true};
  Switch _swMute{nullptr, 0U, true};

  Key up{GPIOA, GPIO_PIN_0, true};
  Key down{GPIOE, GPIO_PIN_4, true};
  Key confirm{GPIOE, GPIO_PIN_3, true};
  Key spare{GPIOE, GPIO_PIN_2, true};

  Key &_collisionA8; /* TOS "next/down" semantic */
  Key &_collisionD0; /* TOS "previous/up" semantic */
  Key &_btnEnter;

  uint8_t getGroup1Config(void);
  uint8_t getGroup2Config(void);
  uint8_t getGroup3Config(void);
  bool isSdCardInserted(void);
  bool isMuted(void);
  bool isAnyCollision(void);
};

extern KeyManager keyManager;

#endif
