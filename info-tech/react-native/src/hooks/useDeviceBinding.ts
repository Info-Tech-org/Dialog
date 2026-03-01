/**
 * useDeviceBinding — React Hook for BLE Device Binding
 * =====================================================
 * 封装完整的设备发现 → 连接 → 绑定 → 配网流程。
 *
 * 用法:
 * ```tsx
 * const {
 *   state, startScan, stopScan, connectDevice,
 *   bindDevice, unbindDevice, configureWiFi, disconnect
 * } = useDeviceBinding();
 * ```
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { DeviceBLEService } from '../services/BLEService';
import type {
  BindingState,
  BindingStep,
  ScannedDevice,
  DeviceInfo,
  BindStatus,
  WiFiStatus,
} from '../types/ble';

const INITIAL_STATE: BindingState = {
  step: 'idle',
  devices: [],
  deviceInfo: null,
  bindStatus: null,
  wifiStatus: null,
  error: null,
};

export function useDeviceBinding() {
  const [state, setState] = useState<BindingState>(INITIAL_STATE);
  const serviceRef = useRef<DeviceBLEService>(new DeviceBLEService());

  // 清理
  useEffect(() => {
    return () => {
      serviceRef.current.disconnect().catch(() => {});
      serviceRef.current.destroy();
    };
  }, []);

  // 更新部分状态
  const updateState = useCallback((partial: Partial<BindingState>) => {
    setState((prev) => ({ ...prev, ...partial }));
  }, []);

  const setStep = useCallback(
    (step: BindingStep, error?: string) => {
      updateState({ step, error: error || null });
    },
    [updateState]
  );

  // ==================== 扫描 ====================

  const startScan = useCallback(async () => {
    try {
      const hasPermission = await serviceRef.current.requestPermissions();
      if (!hasPermission) {
        setStep('error', '蓝牙权限未授予，请在设置中开启');
        return;
      }

      updateState({ step: 'scanning', devices: [], error: null });

      const devices = await serviceRef.current.scan(10000, (device) => {
        setState((prev) => {
          const exists = prev.devices.some((d) => d.id === device.id);
          if (exists) {
            return {
              ...prev,
              devices: prev.devices.map((d) =>
                d.id === device.id ? device : d
              ),
            };
          }
          return { ...prev, devices: [...prev.devices, device] };
        });
      });

      updateState({ step: 'idle', devices });
    } catch (e: any) {
      setStep('error', `扫描失败: ${e.message}`);
    }
  }, [updateState, setStep]);

  const stopScan = useCallback(() => {
    serviceRef.current.stopScan();
    setStep('idle');
  }, [setStep]);

  // ==================== 连接 ====================

  const connectDevice = useCallback(
    async (deviceId: string) => {
      try {
        setStep('connecting');

        await serviceRef.current.connect(deviceId);

        // 自动读取设备信息
        setStep('reading_info');
        const deviceInfo = await serviceRef.current.readDeviceInfo();
        const bindStatus = await serviceRef.current.readBindStatus();

        let wifiStatus: WiFiStatus | null = null;
        try {
          wifiStatus = await serviceRef.current.readWiFiStatus();
        } catch {
          // WiFi 状态可能还没更新，忽略错误
        }

        updateState({
          step: 'idle',
          deviceInfo,
          bindStatus,
          wifiStatus,
          error: null,
        });
      } catch (e: any) {
        setStep('error', `连接失败: ${e.message}`);
      }
    },
    [updateState, setStep]
  );

  // ==================== 绑定 ====================

  const bindDevice = useCallback(
    async (userId: string, userToken?: string) => {
      try {
        setStep('binding');

        const bindStatus = await serviceRef.current.bindDevice(
          userId,
          userToken,
          5000
        );

        updateState({
          step: 'done',
          bindStatus,
          error: null,
        });

        return bindStatus;
      } catch (e: any) {
        setStep('error', `绑定失败: ${e.message}`);
        return null;
      }
    },
    [updateState, setStep]
  );

  const unbindDevice = useCallback(async () => {
    try {
      setStep('binding');

      const bindStatus = await serviceRef.current.unbindDevice(5000);

      updateState({
        step: 'idle',
        bindStatus,
        error: null,
      });

      return bindStatus;
    } catch (e: any) {
      setStep('error', `解绑失败: ${e.message}`);
      return null;
    }
  }, [updateState, setStep]);

  // ==================== WiFi 配网 ====================

  const configureWiFi = useCallback(
    async (ssid: string, password: string) => {
      try {
        setStep('configuring_wifi');

        const wifiStatus = await serviceRef.current.configureWiFi(
          { ssid, password },
          15000
        );

        updateState({
          step: 'done',
          wifiStatus,
          error: null,
        });

        return wifiStatus;
      } catch (e: any) {
        setStep('error', `WiFi 配置失败: ${e.message}`);
        return null;
      }
    },
    [updateState, setStep]
  );

  // ==================== 断开 ====================

  const disconnect = useCallback(async () => {
    await serviceRef.current.disconnect();
    setState(INITIAL_STATE);
  }, []);

  // ==================== 重置 ====================

  const reset = useCallback(() => {
    serviceRef.current.stopScan();
    serviceRef.current.disconnect().catch(() => {});
    setState(INITIAL_STATE);
  }, []);

  return {
    state,
    startScan,
    stopScan,
    connectDevice,
    bindDevice,
    unbindDevice,
    configureWiFi,
    disconnect,
    reset,
  };
}
