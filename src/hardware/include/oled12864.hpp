#ifndef TOS_OLED12864_HPP
#define TOS_OLED12864_HPP

#include <cstdint>

void Oled12864_Init();
void Oled12864_Tick();
void Oled12864_SetDisplayOn(bool enabled);
void Oled12864_SetMode(uint8_t mode);

#endif
