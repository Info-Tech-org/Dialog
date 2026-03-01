export type RootStackParamList = {
  Login: undefined;
  MainTabs: undefined;
  SessionDetail: { sessionId: string };
  UploadStatus: { sessionId: string };
};

export type MainTabParamList = {
  Sessions: undefined;
  Upload: undefined;
  Settings: undefined;
};
