/**
 * BLE Device Service — Info-tech ESP32-C6
 * ========================================
 * 基于 react-native-ble-plx 的 BLE 通信服务层。
 * 封装所有 BLE 底层操作，提供高层 Promise API。
 *
 * 依赖: react-native-ble-plx ^3.x
 */

import { BleManager, Device, Subscription, BleError } from 'react-native-ble-plx';
import { Platform, PermissionsAndroid } from 'react-native';
import {
  BLE_SERVICE_UUID,
  BLE_CHAR,
  BLE_SCAN_TIMEOUT,
  BLE_CONNECT_TIMEOUT,
  BLE_RW_TIMEOUT,
  type DeviceInfo,
  type BindCommand,
  type BindStatus,
  type WiFiConfig,
  type WiFiStatus,
  type ScannedDevice,
} from '../types/ble';

// Base64 编解码 (React Native 环境)
import { Buffer } from 'buffer';

function encodeBase64(str: string): string {
  return Buffer.from(str, 'utf-8').toString('base64');
}

function decodeBase64(b64: string): string {
  return Buffer.from(b64, 'base64').toString('utf-8');
}

/**
 * BLE 设备通信服务
 *
 * 使用方法:
 * ```ts
 * const service = new DeviceBLEService();
 * await service.requestPermissions();
 * const devices = await service.scan();
 * await service.connect(devices[0].id);
 * const info = await service.readDeviceInfo();
 * await service.bindDevice({ cmd: 'bind', user_id: 'u123' });
 * await service.disconnect();
 * service.destroy();
 * ```
 */
export class DeviceBLEService {
  private manager: BleManager;
  private connectedDevice: Device | null = null;
  private subscriptions: Subscription[] = [];

  constructor() {
    this.manager = new BleManager();
  }

  // ==================== 权限管理 ====================

  /**
   * 请求 BLE 所需权限 (Android 需要运行时权限)
   * @returns true 如果权限已授予
   */
  async requestPermissions(): Promise<boolean> {
    if (Platform.OS === 'ios') {
      return true; // iOS 在 Info.plist 配置，运行时自动弹窗
    }

    if (Platform.OS === 'android') {
      const apiLevel = Platform.Version;

      if (apiLevel >= 31) {
        // Android 12+
        const results = await PermissionsAndroid.requestMultiple([
          PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
          PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
          PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
        ]);

        return Object.values(results).every(
          (r) => r === PermissionsAndroid.RESULTS.GRANTED
        );
      } else {
        // Android 11 及以下
        const result = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION
        );
        return result === PermissionsAndroid.RESULTS.GRANTED;
      }
    }

    return false;
  }

  // ==================== 扫描 ====================

  /**
   * 扫描 Info-tech BLE 设备
   * @param timeoutMs 扫描超时时间 (默认 10s)
   * @param onDeviceFound 发现设备时的回调
   * @returns 扫描到的设备列表
   */
  async scan(
    timeoutMs: number = BLE_SCAN_TIMEOUT,
    onDeviceFound?: (device: ScannedDevice) => void
  ): Promise<ScannedDevice[]> {
    const devices = new Map<string, ScannedDevice>();

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.manager.stopDeviceScan();
        resolve(Array.from(devices.values()));
      }, timeoutMs);

      this.manager.startDeviceScan(
        [BLE_SERVICE_UUID],
        { allowDuplicates: false },
        (error: BleError | null, device: Device | null) => {
          if (error) {
            clearTimeout(timer);
            this.manager.stopDeviceScan();
            reject(new Error(`BLE scan error: ${error.message}`));
            return;
          }

          if (device && device.id) {
            const scanned: ScannedDevice = {
              id: device.id,
              name: device.localName || device.name || null,
              rssi: device.rssi,
              isInfoTech: true,
            };

            devices.set(device.id, scanned);
            onDeviceFound?.(scanned);
          }
        }
      );
    });
  }

  /** 停止扫描 */
  stopScan(): void {
    this.manager.stopDeviceScan();
  }

  // ==================== 连接 ====================

  /**
   * 连接到 BLE 设备
   * @param deviceId BLE 设备 ID
   */
  async connect(deviceId: string): Promise<void> {
    // 先确保断开旧连接
    await this.disconnect();

    const device = await this.manager.connectToDevice(deviceId, {
      timeout: BLE_CONNECT_TIMEOUT,
      requestMTU: 256,
    });

    await device.discoverAllServicesAndCharacteristics();
    this.connectedDevice = device;

    console.log(`[BLE] Connected to ${device.name || device.id}`);
  }

  /** 断开 BLE 连接 */
  async disconnect(): Promise<void> {
    // 取消所有订阅
    this.subscriptions.forEach((sub) => sub.remove());
    this.subscriptions = [];

    if (this.connectedDevice) {
      try {
        const isConnected = await this.connectedDevice.isConnected();
        if (isConnected) {
          await this.connectedDevice.cancelConnection();
        }
      } catch {
        // 忽略断开时的错误
      }
      this.connectedDevice = null;
    }
  }

  /** 检查是否已连接 */
  async isConnected(): Promise<boolean> {
    if (!this.connectedDevice) return false;
    try {
      return await this.connectedDevice.isConnected();
    } catch {
      return false;
    }
  }

  // ==================== 读取设备信息 ====================

  /**
   * 读取设备信息
   * @returns DeviceInfo 对象
   */
  async readDeviceInfo(): Promise<DeviceInfo> {
    this.ensureConnected();

    const char = await this.connectedDevice!.readCharacteristicForService(
      BLE_SERVICE_UUID,
      BLE_CHAR.DEVICE_INFO
    );

    if (!char.value) {
      throw new Error('Empty device info response');
    }

    const json = decodeBase64(char.value);
    const info: DeviceInfo = JSON.parse(json);

    // 数据校验
    if (!info.device_id || typeof info.device_id !== 'string') {
      throw new Error('Invalid device_id in device info');
    }

    console.log(`[BLE] Device info: ${info.device_id} (${info.fw_version})`);
    return info;
  }

  // ==================== 绑定操作 ====================

  /**
   * 读取绑定状态
   */
  async readBindStatus(): Promise<BindStatus> {
    this.ensureConnected();

    const char = await this.connectedDevice!.readCharacteristicForService(
      BLE_SERVICE_UUID,
      BLE_CHAR.BIND_STATUS
    );

    if (!char.value) {
      throw new Error('Empty bind status response');
    }

    return JSON.parse(decodeBase64(char.value));
  }

  /**
   * 发送绑定命令
   * @param command 绑定命令 (bind/unbind/query)
   */
  async sendBindCommand(command: BindCommand): Promise<void> {
    this.ensureConnected();

    const json = JSON.stringify(command);
    const base64 = encodeBase64(json);

    await this.connectedDevice!.writeCharacteristicWithResponseForService(
      BLE_SERVICE_UUID,
      BLE_CHAR.BIND_CMD,
      base64
    );

    console.log(`[BLE] Bind command sent: ${command.cmd}`);
  }

  /**
   * 绑定设备到用户 (写入命令 + 等待通知确认)
   * @param userId 用户 ID
   * @param userToken 用户令牌 (可选)
   * @param timeoutMs 等待确认超时
   * @returns 绑定状态
   */
  async bindDevice(
    userId: string,
    userToken?: string,
    timeoutMs: number = BLE_RW_TIMEOUT
  ): Promise<BindStatus> {
    this.ensureConnected();

    return new Promise(async (resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error('Bind confirmation timeout'));
      }, timeoutMs);

      try {
        // 先订阅 Bind Status 通知
        const sub = this.connectedDevice!.monitorCharacteristicForService(
          BLE_SERVICE_UUID,
          BLE_CHAR.BIND_STATUS,
          (error, char) => {
            if (error) {
              clearTimeout(timer);
              sub.remove();
              reject(new Error(`Bind status notify error: ${error.message}`));
              return;
            }

            if (char?.value) {
              clearTimeout(timer);
              sub.remove();
              try {
                const status: BindStatus = JSON.parse(decodeBase64(char.value));
                resolve(status);
              } catch (e) {
                reject(new Error('Invalid bind status JSON'));
              }
            }
          }
        );

        this.subscriptions.push(sub);

        // 发送绑定命令
        const cmd: BindCommand = {
          cmd: 'bind',
          user_id: userId,
          ...(userToken ? { user_token: userToken } : {}),
        };
        await this.sendBindCommand(cmd);
      } catch (e) {
        clearTimeout(timer);
        reject(e);
      }
    });
  }

  /**
   * 解绑设备 (写入命令 + 等待通知确认)
   * @returns 解绑后的状态
   */
  async unbindDevice(timeoutMs: number = BLE_RW_TIMEOUT): Promise<BindStatus> {
    this.ensureConnected();

    return new Promise(async (resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error('Unbind confirmation timeout'));
      }, timeoutMs);

      try {
        const sub = this.connectedDevice!.monitorCharacteristicForService(
          BLE_SERVICE_UUID,
          BLE_CHAR.BIND_STATUS,
          (error, char) => {
            if (error) {
              clearTimeout(timer);
              sub.remove();
              reject(new Error(`Unbind notify error: ${error.message}`));
              return;
            }

            if (char?.value) {
              clearTimeout(timer);
              sub.remove();
              try {
                const status: BindStatus = JSON.parse(decodeBase64(char.value));
                resolve(status);
              } catch (e) {
                reject(new Error('Invalid bind status JSON'));
              }
            }
          }
        );

        this.subscriptions.push(sub);
        await this.sendBindCommand({ cmd: 'unbind' });
      } catch (e) {
        clearTimeout(timer);
        reject(e);
      }
    });
  }

  // ==================== WiFi 配网 ====================

  /**
   * 读取 WiFi 状态
   */
  async readWiFiStatus(): Promise<WiFiStatus> {
    this.ensureConnected();

    const char = await this.connectedDevice!.readCharacteristicForService(
      BLE_SERVICE_UUID,
      BLE_CHAR.WIFI_STATUS
    );

    if (!char.value) {
      throw new Error('Empty WiFi status response');
    }

    return JSON.parse(decodeBase64(char.value));
  }

  /**
   * 配置 WiFi (写入配置 + 等待连接结果通知)
   * @param config WiFi SSID 和密码
   * @param timeoutMs 等待 WiFi 连接超时
   * @returns WiFi 连接状态
   */
  async configureWiFi(
    config: WiFiConfig,
    timeoutMs: number = 15000
  ): Promise<WiFiStatus> {
    this.ensureConnected();

    if (!config.ssid || config.ssid.length === 0) {
      throw new Error('SSID cannot be empty');
    }
    if (config.ssid.length > 32) {
      throw new Error('SSID too long (max 32 characters)');
    }

    return new Promise(async (resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error('WiFi configuration timeout'));
      }, timeoutMs);

      try {
        // 订阅 WiFi Status 通知
        const sub = this.connectedDevice!.monitorCharacteristicForService(
          BLE_SERVICE_UUID,
          BLE_CHAR.WIFI_STATUS,
          (error, char) => {
            if (error) {
              clearTimeout(timer);
              sub.remove();
              reject(new Error(`WiFi status notify error: ${error.message}`));
              return;
            }

            if (char?.value) {
              clearTimeout(timer);
              sub.remove();
              try {
                const status: WiFiStatus = JSON.parse(decodeBase64(char.value));
                resolve(status);
              } catch (e) {
                reject(new Error('Invalid WiFi status JSON'));
              }
            }
          }
        );

        this.subscriptions.push(sub);

        // 写入 WiFi 配置
        const json = JSON.stringify(config);
        const base64 = encodeBase64(json);

        await this.connectedDevice!.writeCharacteristicWithResponseForService(
          BLE_SERVICE_UUID,
          BLE_CHAR.WIFI_CONFIG,
          base64
        );

        console.log(`[BLE] WiFi config sent: SSID=${config.ssid}`);
      } catch (e) {
        clearTimeout(timer);
        reject(e);
      }
    });
  }

  // ==================== 订阅 ====================

  /**
   * 订阅绑定状态变更
   */
  onBindStatusChange(callback: (status: BindStatus) => void): Subscription {
    this.ensureConnected();

    const sub = this.connectedDevice!.monitorCharacteristicForService(
      BLE_SERVICE_UUID,
      BLE_CHAR.BIND_STATUS,
      (error, char) => {
        if (error) {
          console.warn(`[BLE] Bind status monitor error: ${error.message}`);
          return;
        }
        if (char?.value) {
          try {
            callback(JSON.parse(decodeBase64(char.value)));
          } catch {
            console.warn('[BLE] Invalid bind status notification');
          }
        }
      }
    );

    this.subscriptions.push(sub);
    return sub;
  }

  /**
   * 订阅 WiFi 状态变更
   */
  onWiFiStatusChange(callback: (status: WiFiStatus) => void): Subscription {
    this.ensureConnected();

    const sub = this.connectedDevice!.monitorCharacteristicForService(
      BLE_SERVICE_UUID,
      BLE_CHAR.WIFI_STATUS,
      (error, char) => {
        if (error) {
          console.warn(`[BLE] WiFi status monitor error: ${error.message}`);
          return;
        }
        if (char?.value) {
          try {
            callback(JSON.parse(decodeBase64(char.value)));
          } catch {
            console.warn('[BLE] Invalid WiFi status notification');
          }
        }
      }
    );

    this.subscriptions.push(sub);
    return sub;
  }

  // ==================== 生命周期 ====================

  /** 销毁 BLE Manager (App 退出时调用) */
  destroy(): void {
    this.subscriptions.forEach((sub) => sub.remove());
    this.subscriptions = [];
    this.connectedDevice = null;
    this.manager.destroy();
  }

  // ==================== 内部工具 ====================

  private ensureConnected(): void {
    if (!this.connectedDevice) {
      throw new Error('BLE device not connected');
    }
  }
}

/** 全局单例 */
export const deviceBLE = new DeviceBLEService();
