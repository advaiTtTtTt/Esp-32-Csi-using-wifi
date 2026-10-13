#include <math.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"

#if !CONFIG_IDF_TARGET_ESP32
#error "Build this receiver for the original ESP32 (idf.py set-target esp32)."
#endif

#define RADAR_SSID       "WIFI_RADAR"
#define RADAR_PASSWORD   "radarpass"
#define RADAR_CHANNEL    6
#define RADAR_UDP_PORT   3333
#define CSI_QUEUE_LENGTH 64

/* Fixed local MAC keeps CSI records limited to this project's transmitter. */
static const uint8_t RADAR_TX_MAC[6] = {0x02, 0x57, 0x49, 0x46, 0x49, 0x01};

static const char *TAG = "wifi_radar_rx";

typedef struct {
    uint32_t sequence;
    int64_t timestamp_us;
    int8_t rssi_dbm;
    float amplitude;
    uint16_t csi_bytes;
} radar_sample_t;

static QueueHandle_t sample_queue;
static uint32_t sample_sequence;

static void emit_samples_task(void *arg)
{
    (void)arg;
    radar_sample_t sample;
    while (true) {
        if (xQueueReceive(sample_queue, &sample, portMAX_DELAY) != pdTRUE) {
            continue;
        }
#if CONFIG_RADAR_RSSI_FALLBACK
        printf("{\"type\":\"rssi\",\"seq\":%lu,\"t_us\":%lld,\"rssi_dbm\":%d}\n",
               (unsigned long)sample.sequence, (long long)sample.timestamp_us,
               (int)sample.rssi_dbm);
#else
        printf("{\"type\":\"csi\",\"seq\":%lu,\"t_us\":%lld,\"rssi_dbm\":%d,\"amplitude\":%.3f,\"csi_bytes\":%u}\n",
               (unsigned long)sample.sequence, (long long)sample.timestamp_us,
               (int)sample.rssi_dbm, (double)sample.amplitude,
               (unsigned int)sample.csi_bytes);
#endif
        fflush(stdout);
    }
}

#if CONFIG_RADAR_RSSI_FALLBACK
static void promiscuous_rx_callback(void *packet, wifi_promiscuous_pkt_type_t type)
{
    if (type != WIFI_PKT_DATA || packet == NULL || sample_queue == NULL) {
        return;
    }
    const wifi_promiscuous_pkt_t *data = (const wifi_promiscuous_pkt_t *)packet;
    radar_sample_t sample = {
        .sequence = sample_sequence++,
        .timestamp_us = esp_timer_get_time(),
        .rssi_dbm = (int8_t)data->rx_ctrl.rssi,
        .amplitude = 0.0f,
        .csi_bytes = 0,
    };
    (void)xQueueSend(sample_queue, &sample, 0);
}
#else
static void csi_rx_callback(void *ctx, wifi_csi_info_t *data)
{
    (void)ctx;
    if (data == NULL || data->buf == NULL || data->len < 2 || sample_queue == NULL ||
        memcmp(data->mac, RADAR_TX_MAC, sizeof(RADAR_TX_MAC)) != 0) {
        return;
    }

    /* Classic ESP32 packs signed imaginary/real bytes and can mark the first four invalid. */
    uint16_t offset = data->first_word_invalid ? 4 : 0;
    if (offset >= data->len) {
        return;
    }
    double energy = 0.0;
    uint16_t pairs = 0;
    for (uint16_t index = offset; index + 1 < data->len; index += 2) {
        const double imaginary = (double)data->buf[index];
        const double real = (double)data->buf[index + 1];
        energy += real * real + imaginary * imaginary;
        pairs++;
    }
    if (pairs == 0) {
        return;
    }

    radar_sample_t sample = {
        .sequence = sample_sequence++,
        .timestamp_us = esp_timer_get_time(),
        .rssi_dbm = (int8_t)data->rx_ctrl.rssi,
        .amplitude = (float)sqrt(energy / pairs),
        .csi_bytes = data->len,
    };
    (void)xQueueSend(sample_queue, &sample, 0);
}
#endif

static void udp_sink_task(void *arg)
{
    (void)arg;
    const int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (sock < 0) {
        ESP_LOGE(TAG, "UDP socket creation failed");
        vTaskDelete(NULL);
        return;
    }
    struct sockaddr_in local = {
        .sin_family = AF_INET,
        .sin_port = htons(RADAR_UDP_PORT),
        .sin_addr.s_addr = htonl(INADDR_ANY),
    };
    if (bind(sock, (struct sockaddr *)&local, sizeof(local)) < 0) {
        ESP_LOGE(TAG, "UDP bind failed");
        close(sock);
        vTaskDelete(NULL);
        return;
    }

    char payload[96];
    while (true) {
        const int received = recvfrom(sock, payload, sizeof(payload) - 1, 0, NULL, NULL);
        if (received > 0) {
            payload[received] = '\0';
        }
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

void app_main(void)
{
    init_nvs();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    (void)esp_netif_create_default_wifi_ap();

    sample_queue = xQueueCreate(CSI_QUEUE_LENGTH, sizeof(radar_sample_t));
    if (sample_queue == NULL) {
        ESP_LOGE(TAG, "Could not allocate sample queue");
        return;
    }
    xTaskCreate(emit_samples_task, "radar_serial", 4096, NULL, 5, NULL);

    wifi_init_config_t wifi_init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&wifi_init));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));

    wifi_config_t ap_config = {0};
    memcpy(ap_config.ap.ssid, RADAR_SSID, sizeof(RADAR_SSID) - 1);
    memcpy(ap_config.ap.password, RADAR_PASSWORD, sizeof(RADAR_PASSWORD));
    ap_config.ap.ssid_len = sizeof(RADAR_SSID) - 1;
    ap_config.ap.channel = RADAR_CHANNEL;
    ap_config.ap.max_connection = 1;
    ap_config.ap.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_config));
    ESP_ERROR_CHECK(esp_wifi_start());

#if CONFIG_RADAR_RSSI_FALLBACK
    wifi_promiscuous_filter_t filter = {.filter_mask = WIFI_PROMIS_FILTER_MASK_DATA};
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_filter(&filter));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_rx_cb(promiscuous_rx_callback));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));
    ESP_LOGW(TAG, "RSSI-only fallback enabled; CSI is not being emitted");
#else
    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = false,
        .channel_filter_en = false,
        .manu_scale = false,
        .shift = 0,
        .dump_ack_en = false,
    };
    /* Classic ESP32 requires promiscuous mode for CSI from arbitrary transmitters. */
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(csi_rx_callback, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
    ESP_LOGI(TAG, "CSI receiver ready: SSID=%s channel=%d UDP port=%d",
             RADAR_SSID, RADAR_CHANNEL, RADAR_UDP_PORT);
#endif
    xTaskCreate(udp_sink_task, "radar_udp", 3072, NULL, 4, NULL);
}
