#ifndef _SD_CARD_H__
#define _SD_CARD_H__
#include <string.h>
#include <sys/unistd.h>
#include <sys/stat.h>
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdmmc_host.h"
#include "sd_pwr_ctrl_by_on_chip_ldo.h"
#include <dirent.h>
#include <string.h>
#include <ctype.h>
#include <strings.h>
#include <dirent.h>
#include <string.h>
#include <unistd.h>
#define EXAMPLE_MAX_CHAR_SIZE    64

static const char *TAG = "example";
#define MOUNT_POINT "/sdcard"
#define EXAMPLE_IS_UHS1    (CONFIG_EXAMPLE_SDMMC_SPEED_UHS_I_SDR50 || CONFIG_EXAMPLE_SDMMC_SPEED_UHS_I_DDR50)

#define SD_PIN_CMD 38
#define SD_PIN_CLK 39
#define SD_PIN_D0 40

 esp_err_t s_example_write_file(const char *path, char *data);
 esp_err_t s_example_read_file(const char *path);

 #endif
