export type SessionResponse = {
  session_id: string;
  device_id: string;
  start_time: string;
  end_time: string | null;
  audio_path: string | null;
  audio_url?: string | null;
  harmful_count: number;
  duration_seconds: number | null;
};

export type Utterance = {
  id: string;
  session_id: string;
  start: number;
  end: number;
  speaker: string;
  text: string;
  harmful_flag: boolean;
};

export type SessionDetailResponse = SessionResponse & {
  utterances: Utterance[];
};

export type UploadResponse = {
  session_id: string;
  message: string;
  filename: string;
  size: number;
};

export type UploadStatus = {
  status: string;
  progress: number;
  message: string;
  filename?: string;
  utterance_count?: number;
  harmful_count?: number;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
};
