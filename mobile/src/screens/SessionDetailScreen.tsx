import React, { useEffect, useState } from 'react';
import { View, Text, ActivityIndicator, FlatList, StyleSheet, TouchableOpacity, Alert, ScrollView, Clipboard } from 'react-native';
import { fetchSessionDetail } from '../api/client';
import { SessionDetailResponse, Utterance } from '../types';
import { RouteProp, useRoute } from '@react-navigation/native';
import { RootStackParamList } from '../types/navigation';
import { Audio } from 'expo-av';

interface DiagnosticInfo {
  audioUrl: string;
  status?: number;
  contentType?: string;
  contentLength?: number;
  acceptRanges?: string;
  contentRange?: string;
  error?: string;
  timestamp: string;
}

interface PlaybackError {
  message: string;
  code?: string | number;
  stack?: string;
  raw: string;
}

export default function SessionDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, 'SessionDetail'>>();
  const { sessionId } = route.params;
  const [data, setData] = useState<SessionDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [diagnostic, setDiagnostic] = useState<DiagnosticInfo | null>(null);
  const [playbackError, setPlaybackError] = useState<PlaybackError | null>(null);
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchSessionDetail(sessionId);
        setData(res);
      } catch (e: any) {
        Alert.alert('加载失败', e?.message || '请检查网络');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [sessionId]);

  const checkAudioUrl = async () => {
    const url = data?.audio_url;
    if (!url) {
      Alert.alert('提示', '音频路径不可用');
      return;
    }

    try {
      setDiagnostic(null);

      // Try HEAD first, fallback to GET with Range if HEAD fails
      let response: Response;
      try {
        response = await fetch(url, { method: 'HEAD' });
      } catch (headError) {
        console.log('HEAD failed, trying GET with Range:', headError);
        response = await fetch(url, {
          method: 'GET',
          headers: { 'Range': 'bytes=0-1023' }
        });
      }

      const info: DiagnosticInfo = {
        audioUrl: url.length > 60 ? url.substring(0, 60) + '...' : url,
        status: response.status,
        contentType: response.headers.get('content-type') || undefined,
        contentLength: parseInt(response.headers.get('content-length') || '0') || undefined,
        acceptRanges: response.headers.get('accept-ranges') || undefined,
        contentRange: response.headers.get('content-range') || undefined,
        timestamp: new Date().toLocaleTimeString(),
      };

      setDiagnostic(info);
      setShowDiagnostics(true);

      // Validate response
      if (response.status !== 200 && response.status !== 206) {
        Alert.alert('警告', `HTTP状态码: ${response.status}，可能无法播放`);
      } else if (info.contentType?.includes('text/html')) {
        Alert.alert('错误', 'Content-Type是HTML而非音频文件，无法播放');
      } else if ((info.contentLength || 0) < 10000) {
        Alert.alert('警告', `文件太小 (${info.contentLength} bytes)，可能不是有效音频`);
      }

    } catch (e: any) {
      const errorInfo: DiagnosticInfo = {
        audioUrl: url.length > 60 ? url.substring(0, 60) + '...' : url,
        error: e?.message || String(e),
        timestamp: new Date().toLocaleTimeString(),
      };
      setDiagnostic(errorInfo);
      setShowDiagnostics(true);
      Alert.alert('检查失败', e?.message || '网络请求失败');
    }
  };

  const playAudio = async () => {
    const url = data?.audio_url;
    if (!url) {
      Alert.alert('提示', '音频路径不可用');
      return;
    }

    try {
      setPlaying(true);
      setPlaybackError(null);

      console.log('[播放音频] URL:', url);
      const { sound } = await Audio.Sound.createAsync({ uri: url });

      console.log('[播放音频] Sound创建成功，开始播放');
      await sound.playAsync();

      sound.setOnPlaybackStatusUpdate((status) => {
        if (!status.isLoaded) {
          console.log('[播放状态] 未加载');
          return;
        }
        if (!status.isPlaying) {
          console.log('[播放状态] 已停止');
          setPlaying(false);
          sound.unloadAsync();
        }
      });

    } catch (e: any) {
      console.error('[播放失败]', e);

      setPlaying(false);

      // Capture detailed error information
      const errorDetail: PlaybackError = {
        message: e?.message || '未知错误',
        code: e?.code || e?.name,
        stack: e?.stack,
        raw: JSON.stringify(e, Object.getOwnPropertyNames(e), 2),
      };

      setPlaybackError(errorDetail);
      setShowDiagnostics(true);

      Alert.alert(
        '播放失败',
        `错误: ${errorDetail.message}\n代码: ${errorDetail.code || 'N/A'}\n\n详细信息已显示在诊断面板`,
        [{ text: '确定' }]
      );
    }
  };

  const copyDiagnostics = () => {
    const text = [
      '=== 音频诊断信息 ===',
      diagnostic ? [
        `URL: ${diagnostic.audioUrl}`,
        `状态码: ${diagnostic.status || 'N/A'}`,
        `Content-Type: ${diagnostic.contentType || 'N/A'}`,
        `Content-Length: ${diagnostic.contentLength || 'N/A'}`,
        `Accept-Ranges: ${diagnostic.acceptRanges || 'N/A'}`,
        `Content-Range: ${diagnostic.contentRange || 'N/A'}`,
        `错误: ${diagnostic.error || 'N/A'}`,
        `检查时间: ${diagnostic.timestamp}`,
      ].join('\n') : '未检查',
      '',
      '=== 播放错误信息 ===',
      playbackError ? [
        `消息: ${playbackError.message}`,
        `代码: ${playbackError.code || 'N/A'}`,
        `堆栈:\n${playbackError.stack || 'N/A'}`,
        `原始:\n${playbackError.raw}`,
      ].join('\n') : '无错误',
    ].join('\n');

    Clipboard.setString(text);
    Alert.alert('已复制', '诊断信息已复制到剪贴板');
  };

  const renderUtterance = ({ item }: { item: Utterance }) => (
    <View style={[styles.utter, item.harmful_flag && styles.harmful]}>
      <Text style={styles.utterHeader}>
        {item.speaker} [{item.start.toFixed(1)}s - {item.end.toFixed(1)}s]
      </Text>
      <Text>{item.text}</Text>
      {item.harmful_flag && <Text style={styles.warn}>⚠ 有害</Text>}
    </View>
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.center}>
        <Text>未找到会话</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView>
        <View style={styles.header}>
          <Text style={styles.title}>会话 {data.session_id.slice(0, 8)}...</Text>
          <Text>设备: {data.device_id}</Text>
          <Text>开始: {new Date(data.start_time).toLocaleString()}</Text>
          {data.end_time && <Text>结束: {new Date(data.end_time).toLocaleString()}</Text>}
          <Text style={{ color: data.harmful_count > 0 ? '#c00' : '#090' }}>
            有害句数: {data.harmful_count}
          </Text>

          {/* Audio URL Display */}
          {data.audio_url && (
            <Text style={styles.urlText} numberOfLines={1} ellipsizeMode="middle">
              音频: {data.audio_url}
            </Text>
          )}

          {/* Action Buttons */}
          <View style={styles.buttonRow}>
            <TouchableOpacity
              style={[styles.actionBtn, styles.checkBtn]}
              onPress={checkAudioUrl}
            >
              <Text style={{ color: '#fff', fontSize: 13 }}>检查音频链接</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.actionBtn, styles.playBtn]}
              onPress={playAudio}
              disabled={playing}
            >
              <Text style={{ color: '#fff', fontSize: 13 }}>
                {playing ? '播放中...' : '播放音频'}
              </Text>
            </TouchableOpacity>
          </View>

          {/* Diagnostics Panel */}
          {showDiagnostics && (
            <View style={styles.diagnosticPanel}>
              <View style={styles.diagnosticHeader}>
                <Text style={styles.diagnosticTitle}>诊断信息</Text>
                <TouchableOpacity onPress={copyDiagnostics}>
                  <Text style={styles.copyBtn}>复制</Text>
                </TouchableOpacity>
              </View>

              {diagnostic && (
                <View style={styles.diagnosticSection}>
                  <Text style={styles.sectionTitle}>音频链接检查:</Text>
                  <Text style={styles.diagnosticText}>URL: {diagnostic.audioUrl}</Text>
                  <Text style={[styles.diagnosticText, styles.statusText]}>
                    状态码: {diagnostic.status || 'N/A'}
                    {diagnostic.status === 200 && ' ✓'}
                    {diagnostic.status === 206 && ' ✓ (Partial)'}
                  </Text>
                  <Text style={styles.diagnosticText}>
                    Content-Type: {diagnostic.contentType || 'N/A'}
                  </Text>
                  <Text style={styles.diagnosticText}>
                    Content-Length: {diagnostic.contentLength?.toLocaleString() || 'N/A'} bytes
                  </Text>
                  <Text style={styles.diagnosticText}>
                    Accept-Ranges: {diagnostic.acceptRanges || 'N/A'}
                  </Text>
                  {diagnostic.contentRange && (
                    <Text style={styles.diagnosticText}>
                      Content-Range: {diagnostic.contentRange}
                    </Text>
                  )}
                  {diagnostic.error && (
                    <Text style={[styles.diagnosticText, styles.errorText]}>
                      错误: {diagnostic.error}
                    </Text>
                  )}
                  <Text style={styles.timestampText}>检查时间: {diagnostic.timestamp}</Text>
                </View>
              )}

              {playbackError && (
                <View style={styles.diagnosticSection}>
                  <Text style={styles.sectionTitle}>播放错误:</Text>
                  <Text style={[styles.diagnosticText, styles.errorText]}>
                    消息: {playbackError.message}
                  </Text>
                  {playbackError.code && (
                    <Text style={styles.diagnosticText}>代码: {playbackError.code}</Text>
                  )}
                  {playbackError.stack && (
                    <ScrollView horizontal style={styles.stackScroll}>
                      <Text style={styles.stackText}>{playbackError.stack}</Text>
                    </ScrollView>
                  )}
                  <ScrollView horizontal style={styles.stackScroll}>
                    <Text style={styles.rawText}>{playbackError.raw}</Text>
                  </ScrollView>
                </View>
              )}
            </View>
          )}
        </View>

        {/* Utterances List */}
        <View style={styles.utteranceContainer}>
          {data.utterances.length > 0 ? (
            data.utterances.map((item) => (
              <View key={item.id} style={[styles.utter, item.harmful_flag && styles.harmful]}>
                <Text style={styles.utterHeader}>
                  {item.speaker} [{item.start.toFixed(1)}s - {item.end.toFixed(1)}s]
                </Text>
                <Text>{item.text}</Text>
                {item.harmful_flag && <Text style={styles.warn}>⚠ 有害</Text>}
              </View>
            ))
          ) : (
            <Text style={styles.empty}>暂无转写</Text>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 12, backgroundColor: '#f5f5f5' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { marginBottom: 12, gap: 4, backgroundColor: '#fff', padding: 12, borderRadius: 8 },
  title: { fontSize: 18, fontWeight: '700' },
  urlText: { fontSize: 11, color: '#666', marginTop: 4 },
  buttonRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  actionBtn: {
    flex: 1,
    padding: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  checkBtn: { backgroundColor: '#34C759' },
  playBtn: { backgroundColor: '#007AFF' },
  diagnosticPanel: {
    marginTop: 12,
    padding: 12,
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#ddd',
  },
  diagnosticHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  diagnosticTitle: { fontSize: 16, fontWeight: '700' },
  copyBtn: { color: '#007AFF', fontSize: 14 },
  diagnosticSection: { marginBottom: 12 },
  sectionTitle: { fontSize: 14, fontWeight: '700', marginBottom: 4 },
  diagnosticText: { fontSize: 12, marginBottom: 2, fontFamily: 'monospace' },
  statusText: { fontWeight: '600' },
  errorText: { color: '#c00' },
  timestampText: { fontSize: 11, color: '#666', marginTop: 4 },
  stackScroll: { maxHeight: 100, marginTop: 4 },
  stackText: { fontSize: 10, fontFamily: 'monospace', color: '#666' },
  rawText: { fontSize: 10, fontFamily: 'monospace', color: '#333' },
  utteranceContainer: { gap: 8 },
  utter: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#eee',
    backgroundColor: '#fff',
  },
  harmful: {
    borderColor: '#f5c2c0',
    backgroundColor: '#fff5f5',
  },
  utterHeader: { fontWeight: '700', marginBottom: 4 },
  warn: { color: '#c00', marginTop: 4 },
  empty: { textAlign: 'center', color: '#666', marginTop: 20 },
});
