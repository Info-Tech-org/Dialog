import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { useAuth } from '../context/AuthContext';
import * as Application from 'expo-application';

export default function SettingsScreen() {
  const { logout } = useAuth();
  const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  const APP_VERSION = Application.nativeApplicationVersion || '1.0.0';
  const BUILD_VERSION = Application.nativeBuildVersion || '1';

  const handleLogout = () => {
    Alert.alert(
      '确认退出',
      '确定要退出登录吗？',
      [
        { text: '取消', style: 'cancel' },
        {
          text: '退出',
          style: 'destructive',
          onPress: logout,
        },
      ]
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>API 配置</Text>
        <View style={styles.item}>
          <Text style={styles.label}>Base URL</Text>
          <Text style={styles.value}>{API_BASE}</Text>
        </View>
        <Text style={styles.hint}>
          提示：修改 .env 文件中的 EXPO_PUBLIC_API_BASE_URL 来切换环境
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>应用信息</Text>
        <View style={styles.item}>
          <Text style={styles.label}>版本号</Text>
          <Text style={styles.value}>v{APP_VERSION} (Build {BUILD_VERSION})</Text>
        </View>
        <View style={styles.item}>
          <Text style={styles.label}>应用名称</Text>
          <Text style={styles.value}>家庭情绪系统</Text>
        </View>
      </View>

      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Text style={styles.logoutText}>退出登录</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 16,
  },
  section: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 12,
    color: '#333',
  },
  item: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  label: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  value: {
    fontSize: 16,
    color: '#333',
    fontWeight: '500',
  },
  hint: {
    fontSize: 12,
    color: '#999',
    marginTop: 8,
    fontStyle: 'italic',
  },
  logoutButton: {
    backgroundColor: '#ff3b30',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginTop: 'auto',
  },
  logoutText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
