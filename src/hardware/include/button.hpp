#ifndef BUTTON_HPP
#define BUTTON_HPP

#include "main.h"

class Button {
public:
  Button(GPIO_TypeDef *port, uint16_t pin, bool activeLow = true);

  void init();
  bool pressed();

private:
  bool readPressed() const;

  GPIO_TypeDef *_port;
  uint16_t _pin;
  bool _activeLow;
  bool _stablePressed;
  bool _lastSample;
  uint32_t _sampleChangedAt;
  bool _initialized;
};

extern Button key1;
extern Button key2;
extern Button key3;
extern Button key4;

#endif
