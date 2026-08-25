# User include directories
set(USER_Include_Dirs
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/include/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/include/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/manager/include/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/sys/include/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/include/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/gui/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/gui/include/
    ${CMAKE_CURRENT_SOURCE_DIR}/../../partitions/ELF/include/
)

file(GLOB_RECURSE USER_GUI_Src CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/gui/*.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/gui/*.c
)

file(GLOB_RECURSE USER_MANAGER_Src CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/manager/*.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/manager/*.c
)

file(GLOB_RECURSE USER_SYS_Src CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/sys/*.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/sys/*.c
)

list(FILTER USER_GUI_Src EXCLUDE REGEX ".*/wlan_activity\\.(cpp|c)$")
list(FILTER USER_GUI_Src EXCLUDE REGEX ".*/hotspot_activity\\.(cpp|c)$")
list(FILTER USER_GUI_Src EXCLUDE REGEX ".*/include/wlan_activity\\.hpp$")
list(FILTER USER_GUI_Src EXCLUDE REGEX ".*/include/hotspot_activity\\.hpp$")

set(USER_Application_Src
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/tos.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/init.cpp
    ${USER_SYS_Src}
    ${USER_MANAGER_Src}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/core/sdk/tos_api.cpp

    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/led.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/usart.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/buzzer.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/ssd1315.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/lcd.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/key.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/thid.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/bmp180.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/jy901s.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/pot.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/sn74hc00n.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/tcs3472.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/trtc.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/tsdio.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/sfhd.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/cdc_bridge.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/hardware/oled12864.cpp

    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/libdly.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/libvan.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/liboledgfx.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/libpd.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/libui.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/libemo.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/libehw.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/lib3dox.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/lib3dgyro.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/libfs.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/libjson.c
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/libvideo.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../../src/library/sysdram_compat.c

    ${USER_GUI_Src}
)

target_include_directories(stm32cubemx INTERFACE ${USER_Include_Dirs})
target_sources(${CMAKE_PROJECT_NAME} PRIVATE ${USER_Application_Src})

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O3 -ffast-math -fsingle-precision-constant")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -ffast-math -fsingle-precision-constant")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -mfloat-abi=hard -mfpu=fpv4-sp-d16")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mfloat-abi=hard -mfpu=fpv4-sp-d16")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra")
