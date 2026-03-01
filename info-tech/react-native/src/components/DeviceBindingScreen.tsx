/**
 * DeviceBindingScreen — 设备绑定完整界面
 * ========================================
 * 包含：扫描 → 连接 → 设备信息展示 → 绑定 → WiFi 配网
 *
 * 用法:
 * ```tsx
 * import { DeviceBindingScreen } from './components/DeviceBindingScreen';
 * // 在导航中注册:
 * <Stack.Screen name="DeviceBinding" component={DeviceBindingScreen} />
 * ```
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  FlatList,
  TextInput,
  ActivityIndicator,
  StyleSheet,
  Alert,
  ScrollView,
} from 'react-native';
import { useDeviceBinding } from '../hooks/useDeviceBinding';
import type { ScannedDevice } from '../types/ble';

// ⚠️ 实际项目中，userId 应从 App 的认证系统获取
const MOCK_USER_ID = 'app_user_001';
const MOCK_USER_TOKEN = '';

export function DeviceBindingScreen() {
  const {
    state,
    startScan,
    stopScan,
    connectDevice,
    bindDevice,
    unbindDevice,
    configureWiFi,
    disconnect,
    reset,
  } = useDeviceBinding();

  const [wifiSSID, setWifiSSID] = useState('');
  const [wifiPassword, setWifiPassword] = useState('');

  const isLoading = ['scanning', 'connecting', 'reading_info', 'binding', 'configuring_wifi'].includes(state.step);

  // ==================== 设备列表项 ====================

  const renderDevice = ({ item }: { item: ScannedDevice }) => (
    <TouchableOpacity
      style={styles.deviceItem}
      onPress={() => connectDevice(item.id)}
      disabled={isLoading}
    >
      <View style={styles.deviceInfo}>
        <Text style={styles.deviceName}>{item.name || '未知设备'}</Text>
        <Text style={styles.deviceId}>{item.id}</Text>
      </View>
      <Text style={styles.rssi}>{item.rssi ?? '--'} dBm</Text>
    </TouchableOpacity>
  );

  // ==================== 主渲染 ====================

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <Text style={styles.title}>设备绑定</Text>

      {/* Error Banner */}
      {state.error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{state.error}</Text>
          <TouchableOpacity onPress={reset}>
            <Text style={styles.errorAction}>重试</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Step Indicator */}
      <View style={styles.stepBar}>
        {(['scanning', 'connecting', 'binding', 'configuring_wifi', 'done'] as const).map(
          (s, i) => (
            <View
              key={s}
              style={[
                styles.stepDot,
                state.step === s && styles.stepDotActive,
                state.step === 'done' && styles.stepDotDone,
              ]}
            >
              <Text style={styles.stepText}>{i + 1}</Text>
            </View>
          )
        )}
      </View>

      {/* Section 1: Scan */}
      {!state.deviceInfo && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>1. 搜索设备</Text>
          <TouchableOpacity
            style={[styles.button, isLoading && styles.buttonDisabled]}
            onPress={state.step === 'scanning' ? stopScan : startScan}
            disabled={isLoading && state.step !== 'scanning'}
          >
            {state.step === 'scanning' ? (
              <View style={styles.buttonRow}>
                <ActivityIndicator color="#fff" size="small" />
                <Text style={styles.buttonText}>  搜索中... 点击停止</Text>
              </View>
            ) : (
              <Text style={styles.buttonText}>开始搜索</Text>
            )}
          </TouchableOpacity>

          {state.devices.length > 0 && (
            <FlatList
              data={state.devices}
              renderItem={renderDevice}
              keyExtractor={(item) => item.id}
              style={styles.deviceList}
              scrollEnabled={false}
            />
          )}

          {state.step === 'connecting' && (
            <View style={styles.loadingRow}>
              <ActivityIndicator />
              <Text style={styles.loadingText}>连接中...</Text>
            </View>
          )}
        </View>
      )}

      {/* Section 2: Device Info */}
      {state.deviceInfo && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>2. 设备信息</Text>
          <View style={styles.infoCard}>
            <InfoRow label="设备名" value={state.deviceInfo.ble_name} />
            <InfoRow label="设备 ID" value={state.deviceInfo.device_id} />
            <InfoRow label="MAC" value={state.deviceInfo.mac} />
            <InfoRow label="固件版本" value={state.deviceInfo.fw_version} />
          </View>

          <TouchableOpacity
            style={[styles.button, styles.buttonSecondary]}
            onPress={disconnect}
          >
            <Text style={[styles.buttonText, styles.buttonTextSecondary]}>
              断开连接
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Section 3: Binding */}
      {state.deviceInfo && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>3. 用户绑定</Text>

          {state.bindStatus?.bound ? (
            <View>
              <View style={styles.infoCard}>
                <InfoRow label="状态" value="✅ 已绑定" />
                <InfoRow label="用户 ID" value={state.bindStatus.user_id || '-'} />
              </View>
              <TouchableOpacity
                style={[styles.button, styles.buttonDanger]}
                onPress={() => {
                  Alert.alert('确认解绑', '解绑后设备将不再关联您的账户', [
                    { text: '取消', style: 'cancel' },
                    { text: '确认解绑', style: 'destructive', onPress: unbindDevice },
                  ]);
                }}
                disabled={isLoading}
              >
                <Text style={styles.buttonText}>解绑设备</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View>
              <Text style={styles.hint}>
                将此设备绑定到您的账户 (User: {MOCK_USER_ID})
              </Text>
              <TouchableOpacity
                style={[styles.button, isLoading && styles.buttonDisabled]}
                onPress={() => bindDevice(MOCK_USER_ID, MOCK_USER_TOKEN)}
                disabled={isLoading}
              >
                {state.step === 'binding' ? (
                  <View style={styles.buttonRow}>
                    <ActivityIndicator color="#fff" size="small" />
                    <Text style={styles.buttonText}>  绑定中...</Text>
                  </View>
                ) : (
                  <Text style={styles.buttonText}>绑定设备</Text>
                )}
              </TouchableOpacity>
            </View>
          )}
        </View>
      )}

      {/* Section 4: WiFi Config */}
      {state.deviceInfo && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>4. WiFi 配网</Text>

          {state.wifiStatus?.connected && (
            <View style={styles.infoCard}>
              <InfoRow label="状态" value="✅ 已连接" />
              <InfoRow label="SSID" value={state.wifiStatus.ssid || '-'} />
              <InfoRow label="IP" value={state.wifiStatus.ip || '-'} />
              <InfoRow label="信号" value={`${state.wifiStatus.rssi ?? '-'} dBm`} />
            </View>
          )}

          <TextInput
            style={styles.input}
            placeholder="WiFi 名称 (SSID)"
            value={wifiSSID}
            onChangeText={setWifiSSID}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TextInput
            style={styles.input}
            placeholder="WiFi 密码"
            value={wifiPassword}
            onChangeText={setWifiPassword}
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
          />

          <TouchableOpacity
            style={[
              styles.button,
              (!wifiSSID || isLoading) && styles.buttonDisabled,
            ]}
            onPress={() => configureWiFi(wifiSSID, wifiPassword)}
            disabled={!wifiSSID || isLoading}
          >
            {state.step === 'configuring_wifi' ? (
              <View style={styles.buttonRow}>
                <ActivityIndicator color="#fff" size="small" />
                <Text style={styles.buttonText}>  配网中...</Text>
              </View>
            ) : (
              <Text style={styles.buttonText}>配置 WiFi</Text>
            )}
          </TouchableOpacity>
        </View>
      )}

      {/* Done */}
      {state.step === 'done' && (
        <View style={styles.doneBanner}>
          <Text style={styles.doneText}>✅ 设备配置完成！</Text>
        </View>
      )}
    </ScrollView>
  );
}

// ==================== 子组件 ====================

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

// ==================== 样式 ====================

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: '#1a1a1a',
    marginBottom: 16,
  },

  // Step Bar
  stepBar: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 12,
    marginBottom: 20,
  },
  stepDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#ddd',
    justifyContent: 'center',
    alignItems: 'center',
  },
  stepDotActive: {
    backgroundColor: '#4A90D9',
  },
  stepDotDone: {
    backgroundColor: '#4CAF50',
  },
  stepText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },

  // Sections
  section: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
  },

  // Buttons
  button: {
    backgroundColor: '#4A90D9',
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 20,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonDisabled: {
    backgroundColor: '#B0C4DE',
  },
  buttonSecondary: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#4A90D9',
  },
  buttonDanger: {
    backgroundColor: '#E74C3C',
    marginTop: 12,
  },
  buttonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
  },
  buttonTextSecondary: {
    color: '#4A90D9',
  },
  buttonRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  // Device List
  deviceList: {
    marginTop: 12,
  },
  deviceItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 12,
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    marginBottom: 8,
  },
  deviceInfo: {
    flex: 1,
  },
  deviceName: {
    fontSize: 15,
    fontWeight: '500',
    color: '#333',
  },
  deviceId: {
    fontSize: 11,
    color: '#999',
    marginTop: 2,
  },
  rssi: {
    fontSize: 13,
    color: '#666',
    marginLeft: 12,
  },

  // Info Card
  infoCard: {
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  infoLabel: {
    fontSize: 14,
    color: '#666',
  },
  infoValue: {
    fontSize: 14,
    color: '#333',
    fontWeight: '500',
    maxWidth: '60%',
    textAlign: 'right',
  },

  // Input
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
    fontSize: 15,
    backgroundColor: '#fff',
    marginBottom: 8,
  },

  // Loading
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
  },
  loadingText: {
    marginLeft: 8,
    color: '#666',
  },

  // Hint
  hint: {
    fontSize: 13,
    color: '#888',
    marginBottom: 8,
  },

  // Error
  errorBanner: {
    backgroundColor: '#FFF3F3',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderLeftWidth: 3,
    borderLeftColor: '#E74C3C',
  },
  errorText: {
    color: '#C0392B',
    fontSize: 13,
    flex: 1,
  },
  errorAction: {
    color: '#4A90D9',
    fontWeight: '600',
    marginLeft: 12,
  },

  // Done
  doneBanner: {
    backgroundColor: '#E8F5E9',
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    borderLeftWidth: 3,
    borderLeftColor: '#4CAF50',
  },
  doneText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#2E7D32',
  },
});
