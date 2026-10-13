#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"

#if !CONFIG_IDF_TARGET_ESP32
#error "Build this transmitter for the original ESP32 (idf.py set-target esp32)."
#endif

#define RADAR_SSID       "WIFI_RADAR"
#define RADAR_PASSWORD   "radarpass"
#define RADAR_CHANNEL    6
#define RADAR_UDP_PORT   3333
#define CONNECTED_BIT    (1U << 0)

static const uint8_t RADAR_TX_MAC[6] = {0x02, 0x57, 0x49, 0x46, 0x49, 0x01};

static const char *TAG = "wifi_radar_tx";
static EventGroupHandle_t wifi_events;

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    (void)arg;
    (void)event_data;
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_ERROR_CHECK(esp_wifi_connect());
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(wifi_events, CONNECTED_BIT);
        ESP_LOGW(TAG, "Disconnected; retrying Wi-Fi connection");
        (void)esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(wifi_events, CONNECTED_BIT);
        ESP_LOGI(TAG, "Connected to receiver access point");
    }
}

static void init_nvs(void)
{
    esp_err_t result = nvs_flash_init();
    if (result == ESP_ERR_NVS_NO_FREE_PAGES || result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        result = nvs_flash_init();
    }
    ESP_ERROR_CHECK(result);
}

static void packet_task(void *arg)
{
    (void)arg;
    const struct sockaddr_in receiver = {
        .sin_family = AF_INET,
        .sin_port = htons(RADAR_UDP_PORT),
        .sin_addr.s_addr = inet_addr("192.168.4.1"),
    };
    int sock = -1;
    uint32_t sequence = 0;
    char payload[64];
    while (true) {
        if (sock < 0) {
            sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
            if (sock < 0) {
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
        }
        EventBits_t bits = xEventGroupWaitBits(wifi_events, CONNECTED_BIT,
                                               pdFALSE, pdTRUE,
                                               pdMS_TO_TICKS(100));
        if ((bits & CONNECTED_BIT) != 0) {
            const int length = snprintf(payload, sizeof(payload), "WIFIRADAR,%lu,%lld",
                                        (unsigned long)sequence,
                                        (long long)esp_timer_get_time());
            if (length > 0) {
                (void)sendto(sock, payload, (size_t)length, 0,
                             (const struct sockaddr *)&receiver, sizeof(receiver));
            }
            sequence++;
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

void app_main(void)
{
    init_nvs();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    (void)esp_netif_create_default_wifi_sta();
    wifi_events = xEventGroupCreate();
    if (wifi_events == NULL) {
        ESP_LOGE(TAG, "Could not allocate Wi-Fi event group");
        return;
    }

    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                               &wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                               &wifi_event_handler, NULL));

    wifi_init_config_t wifi_init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&wifi_init));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_mac(WIFI_IF_STA, RADAR_TX_MAC));
    wifi_config_t station = {0};
    memcpy(station.sta.ssid, RADAR_SSID, sizeof(RADAR_SSID) - 1);
    memcpy(station.sta.password, RADAR_PASSWORD, sizeof(RADAR_PASSWORD));
    station.sta.channel = RADAR_CHANNEL;
    station.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &station));
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    ESP_ERROR_CHECK(esp_wifi_start());

    xTaskCreate(packet_task, "radar_tx_packets", 3072, NULL, 5, NULL);
    ESP_LOGI(TAG, "Sending periodic Wi-Fi packets to the receiver at 192.168.4.1");
}
