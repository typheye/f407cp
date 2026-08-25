#include "include/application_activity.hpp"
#include "core/manager/include/app_manager.h"
#include "gui/components/include/alert.hpp"
#include "gui/components/include/confirm.hpp"
#include "library/include/libdly.h"
#include "library/include/libui.h"

extern KeyManager keyManager;

static void app_info(const AppManager_App *app) {
  char msg[192];
  snprintf(msg, sizeof(msg), "[App Name]\n%s\n[App Version]\n%s\n[App Package Name]\n%s",
           app->name, app->version, app->package_name);
  alert_show("APP", msg);
}

static void app_menu(const AppManager_App *app, uint16_t index) {
  char visibility_item[20];
  snprintf(visibility_item, sizeof(visibility_item), "02 %s",
           app->hidden ? "Display" : "Hide");
  const char *items[] = {"00 Return", "01 Information", visibility_item,
                         "03 Uninstall"};
  int sel = 0;
  uint8_t last_enter = 0U;
  while (1) {
    TosApi_Tick();
    keyManager._collisionA8.tick();
    keyManager._collisionD0.tick();
    keyManager._btnEnter.tick();
    if (keyManager._collisionA8.getState() == KEY_PRESSED) sel = (sel + 1) % 4;
    if (keyManager._collisionD0.getState() == KEY_PRESSED) sel = (sel + 3) % 4;
    uint8_t enter = keyManager._btnEnter.getState() == KEY_PRESSED;
    if (enter && !last_enter) {
      if (sel == 0) return;
      if (sel == 1) {
        app_info(app);
      } else if (sel == 2 && app->can_hide) {
        if (confirm_show("APP", app->hidden ? "Need to display application?"
                                             : "Need to hide application?"))
          (void)AppManager_SetHidden(index, app->hidden == 0U);
        return;
      } else if (sel == 3 && app->can_uninstall) {
        if (confirm_show("APP", "Need to uninstall the application?"))
          (void)AppManager_Uninstall(index);
        return;
      }
    }
    last_enter = enter;
    LCD_FLUSH({
      UI_DrawFrameTitle("APP");
      UI_DrawMenuCard(0, sel, 33, items[0]);
      UI_DrawMenuCard(1, sel, 58, items[1]);
      UI_DrawMenuCardEx(2, sel, 83, items[2], !app->can_hide);
      UI_DrawMenuCardEx(3, sel, 108, items[3], !app->can_uninstall);
      PD_DrawFooterCenter("ENTER", NULL, "UP/DOWN");
    });
    JPDelay(1U);
  }
}

void application_activity_run(void) {
  (void)AppManager_Init();
  int sel = 0;
  uint8_t last_enter = 0U;
  while (1) {
    const uint16_t count = AppManager_Count();
    const int total = (int)count + 1;
    if (sel >= total) sel = 0;
    TosApi_Tick();
    keyManager._collisionA8.tick();
    keyManager._collisionD0.tick();
    keyManager._btnEnter.tick();
    if (keyManager._collisionA8.getState() == KEY_PRESSED) sel = (sel + 1) % total;
    if (keyManager._collisionD0.getState() == KEY_PRESSED) sel = (sel + total - 1) % total;
    uint8_t enter = keyManager._btnEnter.getState() == KEY_PRESSED;
    if (enter && !last_enter) {
      if (sel == 0) return;
      const AppManager_App *app = AppManager_Get((uint16_t)(sel - 1));
      if (app) app_menu(app, (uint16_t)(sel - 1));
    }
    last_enter = enter;
    LCD_FLUSH({
      UI_DrawFrameTitle("APP");
      int visible = total < 7 ? total : 7;
      int start = UI_MenuVisibleStart(total, sel, visible);
      for (int i = 0; i < visible; ++i) {
        int idx = start + i;
        if (idx == 0) {
          UI_DrawMenuCard(idx, sel, 33 + i * 25, "00 Return");
        } else {
          const AppManager_App *app = AppManager_Get((uint16_t)(idx - 1));
          char label[40];
          snprintf(label, sizeof(label), "   %s", app ? app->name : "");
          UI_DrawMenuCard(idx, sel, 33 + i * 25, label);
        }
      }
      PD_DrawFooterCenter("ENTER", NULL, "UP/DOWN");
    });
    JPDelay(1U);
  }
}
