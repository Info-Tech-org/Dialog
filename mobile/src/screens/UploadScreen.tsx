import React, { useState } from 'react';
import { View, Text, Button, StyleSheet, Alert, TextInput } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { uploadAudio } from '../api/client';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RootStackParamList } from '../types/navigation';
import { useNavigation } from '@react-navigation/native';

export default function UploadScreen() {
  const [file, setFile] = useState<DocumentPicker.DocumentPickerResult | null>(null);
  const [deviceId, setDeviceId] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  const pickFile = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: 'audio/*',
      copyToCacheDirectory: true,
    });
    if (result.canceled) return;
    setFile(result);
  };

  const handleUpload = async () => {
    if (!file || file.canceled) {
      Alert.alert('请选择音频文件');
      return;
    }
    const asset = file.assets[0];
    setUploading(true);
    try {
      const res = await uploadAudio(
        { uri: asset.uri, name: asset.name ?? 'audio.wav', type: asset.mimeType ?? 'audio/mpeg' },
        deviceId || undefined
      );
      navigation.navigate('UploadStatus', { sessionId: res.session_id });
    } catch (e: any) {
      Alert.alert('上传失败', e?.message || '请检查网络或文件格式');
    } finally {
      setUploading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>上传音频文件</Text>
      <TextInput
        style={styles.input}
        placeholder="设备ID（可选）"
        value={deviceId}
        onChangeText={setDeviceId}
      />
      <Button title="选择文件" onPress={pickFile} />
      {file && !file.canceled && <Text style={styles.info}>已选择: {file.assets[0].name}</Text>}
      <Button title={uploading ? '上传中...' : '开始上传'} onPress={handleUpload} disabled={uploading} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 12 },
  title: { fontSize: 18, fontWeight: '700' },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 10,
  },
  info: { marginTop: 8, color: '#555' },
});
