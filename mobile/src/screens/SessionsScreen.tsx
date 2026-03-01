import React, { useState, useCallback } from 'react';
import { View, Text, FlatList, TouchableOpacity, RefreshControl, StyleSheet } from 'react-native';
import { fetchSessions } from '../api/client';
import { SessionResponse } from '../types';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RootStackParamList } from '../types/navigation';

export default function SessionsScreen() {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  const load = async () => {
    setRefreshing(true);
    try {
      const data = await fetchSessions();
      setSessions(data);
    } catch (e) {
      console.warn(e);
    } finally {
      setRefreshing(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      load();
    }, [])
  );

  const renderItem = ({ item }: { item: SessionResponse }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => navigation.navigate('SessionDetail', { sessionId: item.session_id })}
    >
      <Text style={styles.title}>会话 {item.session_id.slice(0, 8)}...</Text>
      <Text>设备: {item.device_id}</Text>
      <Text>开始: {new Date(item.start_time).toLocaleString()}</Text>
      {item.duration_seconds ? <Text>时长: {Math.round(item.duration_seconds)}s</Text> : null}
      <Text style={{ color: item.harmful_count > 0 ? '#c00' : '#090' }}>
        有害句数: {item.harmful_count}
      </Text>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={sessions}
        keyExtractor={(item) => item.session_id}
        renderItem={renderItem}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} />}
        contentContainerStyle={{ paddingBottom: 40 }}
        ListEmptyComponent={<Text style={styles.empty}>暂无会话</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 12 },
  actions: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8, gap: 8 },
  card: {
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#ddd',
    marginBottom: 10,
    backgroundColor: '#fff',
  },
  title: { fontSize: 16, fontWeight: '700' },
  empty: { textAlign: 'center', marginTop: 32, color: '#666' },
});
