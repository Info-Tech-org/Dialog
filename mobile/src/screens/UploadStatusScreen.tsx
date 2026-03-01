import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, Alert, Button } from 'react-native';
import { RouteProp, useNavigation, useRoute } from '@react-navigation/native';
import { RootStackParamList } from '../types/navigation';
import { fetchUploadStatus } from '../api/client';
import { UploadStatus } from '../types';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';

export default function UploadStatusScreen() {
  const route = useRoute<RouteProp<RootStackParamList, 'UploadStatus'>>();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { sessionId } = route.params;
  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetchUploadStatus(sessionId);
        setStatus(res);
        if (res.status === 'completed' || (res.utterance_count && res.utterance_count > 0)) {
          navigation.replace('SessionDetail', { sessionId });
        }
      } catch (e: any) {
        if (e?.message?.includes('404')) {
          setError('状态不存在或已过期（可能服务重启导致内存状态丢失）。');
          stop();
        } else {
          setError(e?.message || '轮询失败');
        }
      }
    };
    poll();
    timer.current = setInterval(poll, 2500);
    return stop;
  }, [sessionId, navigation]);

  const stop = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>处理中...</Text>
      <Text>Session: {sessionId}</Text>
      {status ? (
        <View style={{ marginTop: 12 }}>
          <Text>状态: {status.status}</Text>
          <Text>进度: {status.progress ?? 0}%</Text>
          <Text>消息: {status.message}</Text>
          {typeof status.utterance_count === 'number' && <Text>转写条数: {status.utterance_count}</Text>}
          {typeof status.harmful_count === 'number' && <Text>有害条数: {status.harmful_count}</Text>}
        </View>
      ) : (
        <ActivityIndicator style={{ marginTop: 12 }} />
      )}
      {error && <Text style={styles.error}>{error}</Text>}
      <Button title="返回列表" onPress={() => navigation.navigate('Sessions')} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 8 },
  title: { fontSize: 18, fontWeight: '700' },
  error: { color: '#c00', marginTop: 8 },
});
