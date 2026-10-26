#include <stdio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <led.h>
#include <camera.h>
#include <string.h>
#include <sys/unistd.h>
#include <sys/stat.h>
#include <esp_heap_caps.h>
#include <sd_card.h>
#include <esp_psram.h>
#include <sd_card.h>

void led_blink_task(void * param)
{
  
    while(1)
    {
    led_on();
    vTaskDelay(pdMS_TO_TICKS(500));
    led_off();
    vTaskDelay(pdMS_TO_TICKS(500));
    }
}





void app_main(void)
{
    esp_err_t ret;
    led_init();
        

 // 检测 PSRAM 存在性和大小
    if(esp_psram_get_size() == 0) {
        ESP_LOGE("BOOT", "PSRAM NOT DETECTED! Check hardware connection.");
        vTaskDelay(pdMS_TO_TICKS(1000));
        esp_restart(); // 自动重启
    }
    
    ESP_LOGI("BOOT", "PSRAM Size: %d KB", esp_psram_get_size() / 1024);
    
    // 初始化 PSRAM 缓存
    esp_psram_init();
    
    // 启用 PSRAM 分配
    // heap_caps_malloc_extmem_enable(64); // 最小分配单元64字节
    bsp_camera_init();
   
    esp_vfs_fat_sdmmc_mount_config_t mount_config ={
        .format_if_mount_failed = false,
        .max_files=5,
        .allocation_unit_size=16*1024,

     };
    sdmmc_card_t *card;
    const char mount_point[] = MOUNT_POINT;
    ESP_LOGI(TAG, "Initializing SD card");
    ESP_LOGI(TAG, "Using SDMMC peripheral");
    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
sdmmc_slot_config_t slot_config = SDMMC_SLOT_CONFIG_DEFAULT();
    slot_config.width=1;
    slot_config.clk=SD_PIN_CLK;
    slot_config.cmd=SD_PIN_CMD;
    slot_config.d0=SD_PIN_D0;
    slot_config.flags |= SDMMC_SLOT_FLAG_INTERNAL_PULLUP;
    ESP_LOGI(TAG, "Mounting filesystem");
    ret = esp_vfs_fat_sdmmc_mount(mount_point, &host, &slot_config, &mount_config, &card);

    if (ret != ESP_OK) {
        if (ret == ESP_FAIL) {
            ESP_LOGE(TAG, "Failed to mount filesystem. "
                     "If you want the card to be formatted, set the EXAMPLE_FORMAT_IF_MOUNT_FAILED menuconfig option.");
        } else {
            ESP_LOGE(TAG, "Failed to initialize the card (%s). "
                     "Make sure SD card lines have pull-up resistors in place.", esp_err_to_name(ret));
        }
        return;
    }
    ESP_LOGI(TAG, "Filesystem mounted");
 sdmmc_card_print_info(stdout, card);
 camera_capture();
 ESP_LOGE("test","666");

 xTaskCreatePinnedToCore(led_blink_task,"led",4096,NULL,3,NULL,1);
//  xTaskCreatePinnedToCore(camera_run_task,"capture",4096,NULL,3,NULL,1);
}

