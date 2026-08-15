# TOS GUI Port

This GUI port is based on `typheye/tos`, branch `slave-board`, commit
`8ba85d7c`.

Hardware adaptation in this tree:

- fixed 240x240 LCD orientation using native MADCTL `0x60` plus a software
  180-degree window and pixel-order transform;
- direct `KeyManager` mapping: PA0 up, PE4 down, PE3 confirm, PE2 back/spare;
- manual TIM4_CH2 backlight control with RTC backup-register persistence;
- SD, RTC, offline network and watchdog status pages;
- USB CDC/USART1 bridge in place of HID;
- no external sensor, collision-switch or physical fault-LED code;
- SSD1315 remains a secondary RTC clock display.
