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
        return;
      } else if (sel == 2 && app->can_hide) {
        if (confirm_show("APP", app->hidden ? "Need to display application?"
                                             : "Need to hide application?"))
          (void)AppManager_SetHidden(index, app->hidden == 0U);
        return;
      } else if (sel == 3 && app->can_uninstall) {
        if (confirm_show("APP", "Need to uninstall the application?"))
          (void)AppManager_Uninstall(index);
        return;
      } else {
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

static int app_ordered_index(const uint16_t *order, uint16_t count, int pos) {
  return pos >= 0 && pos < (int)count ? (int)order[pos] : -1;
}

void application_activity_run(void) {
  (void)AppManager_Init();
  int sel = 0;
  uint8_t last_enter = 0U;
  while (1) {
    const uint16_t count = AppManager_Count();
    uint16_t order[APP_MANAGER_MAX];
    uint16_t order_count = 0U;
    for (uint16_t pass = 0U; pass < 2U; ++pass) {
      for (uint16_t i = 0U; i < count; ++i) {
        const AppManager_App *app = AppManager_Get(i);
        if (app && ((pass == 0U && !app->hidden) ||
                    (pass == 1U && app->hidden)))
          order[order_count++] = i;
      }
    }
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
      const int ordered = app_ordered_index(order, order_count, sel - 1);
      const AppManager_App *app = ordered >= 0 ? AppManager_Get((uint16_t)ordered) : NULL;
      if (app) app_menu(app, (uint16_t)ordered);
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
          const int ordered = app_ordered_index(order, order_count, idx - 1);
          const AppManager_App *app = ordered >= 0 ? AppManager_Get((uint16_t)ordered) : NULL;
          char label[40];
          snprintf(label, sizeof(label), "   %s", app ? app->name : "");
          UI_DrawMenuCardEx(idx, sel, 33 + i * 25, label,
                            app && app->hidden);
        }
      }
      PD_DrawFooterCenter("ENTER", NULL, "UP/DOWN");
    });
    JPDelay(1U);
  }
}
