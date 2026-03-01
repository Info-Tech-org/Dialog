import logging
from typing import List, Dict, Any
from sqlmodel import Session as DBSession
from models import Utterance, Session, engine
from realtime.harmful_rules import is_harmful
from offline.tencent_offline_asr import TencentOfflineASR
from offline.cos_uploader import COSUploader
from config import settings
import os

logger = logging.getLogger(__name__)


class OfflineProcessor:
    """
    Offline ASR and speaker diarization processor.

    In production, this would:
    1. Call offline ASR API (e.g., Alibaba, Tencent) for better accuracy
    2. Call speaker diarization API to separate speakers
    3. Store results in database

    For MVP, this is a placeholder with hooks for integration.
    """

    def __init__(self):
        self.tencent_asr = TencentOfflineASR()
        self.cos_uploader = COSUploader() if settings.tencent_cos_bucket else None

    def process(self, audio_path: str, session_id: str) -> List[Dict[str, Any]]:
        """
        Process recorded audio file with offline ASR and diarization

        Args:
            audio_path: Path to audio file
            session_id: Session identifier

        Returns:
            List of utterances with format:
            [
                {
                    "start": 0.0,
                    "end": 3.5,
                    "speaker": "A",
                    "text": "..."
                },
                ...
            ]
        """
        logger.info(f"Starting offline processing for {audio_path}")

        # 使用腾讯云录音文件识别 + 说话人分离
        try:
            cos_key = None
            if audio_path.startswith("http"):
                # 已是 URL，直接识别
                utterances = self.tencent_asr.process(audio_path)
            else:
                logger.info(f"Local audio file detected, attempting COS upload: {audio_path}")
                if self.cos_uploader:
                    try:
                        # 生成可追踪 cos_key
                        base_name = os.path.basename(audio_path)
                        cos_key = f"audio/uploads/{session_id}/{base_name}"
                        use_presigned = getattr(settings, 'tencent_cos_use_presigned_url', True)
                        asr_expire = getattr(settings, 'cos_presign_asr_expire_seconds', 86400)
                        cos_key, audio_url = self.cos_uploader.upload_file(
                            audio_path,
                            cos_key=cos_key,
                            use_presigned_url=use_presigned,
                            expire_seconds=asr_expire,
                        )
                        logger.info(f"COS upload success: key={cos_key}, asr_url ttl={asr_expire}s")
                        utterances = self.tencent_asr.process(audio_url)
                    except Exception as e:
                        logger.error(f"COS upload/ASR failed: {e}", exc_info=True)
                        logger.warning("Falling back to placeholder data")
                        utterances = self._placeholder_processing(audio_path)
                else:
                    logger.warning("COS not configured, using placeholder data.")
                    utterances = self._placeholder_processing(audio_path)

            # Save to database
            self._save_utterances(session_id, utterances, cos_key=cos_key)

            logger.info(f"Completed offline processing for {session_id}")
            return utterances

        except Exception as e:
            logger.error(f"Offline processing failed: {e}", exc_info=True)
            # 失败时返回占位数据
            utterances = self._placeholder_processing(audio_path)
            self._save_utterances(session_id, utterances)
            return utterances

    def _placeholder_processing(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Placeholder for offline processing

        In production, replace with actual API calls
        """
        # Return example data structure
        return [
            {
                "start": 0.0,
                "end": 2.5,
                "speaker": "A",
                "text": "示例文本 - 家长说话"
            },
            {
                "start": 2.5,
                "end": 5.0,
                "speaker": "B",
                "text": "示例文本 - 孩子回应"
            }
        ]

    def _call_alibaba_asr(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Placeholder for Alibaba Cloud ASR integration (future extension).

        Implementation would:
        1. Upload audio file or send via API
        2. Get transcription with timestamps
        3. Return list of utterances
        """
        # Future: optional Alibaba Cloud ASR; current production uses Tencent ASR.
        pass

    def _call_speaker_diarization(
        self,
        audio_path: str,
        utterances: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Placeholder for standalone speaker diarization (future extension).

        Current production uses Tencent ASR with ResTextFormat for speaker labels.
        This hook could integrate additional diarization (e.g. pyannote.audio).
        """
        # Future: optional standalone diarization; Tencent ASR already returns speaker IDs.
        pass

    def _save_utterances(self, session_id: str, utterances: List[Dict[str, Any]], cos_key: str = None):
        """
        Save utterances to database

        Args:
            session_id: Session identifier
            utterances: List of utterance dictionaries
            cos_key: COS object key for the audio (optional)
        """
        with DBSession(engine) as db:
            for utt_data in utterances:
                text = utt_data.get("text", "")
                harmful = is_harmful(text)

                utterance = Utterance(
                    session_id=session_id,
                    start=utt_data.get("start", 0.0),
                    end=utt_data.get("end", 0.0),
                    speaker=utt_data.get("speaker", "A"),
                    text=text,
                    harmful_flag=harmful,
                )

                db.add(utterance)

            # Update session cos_key if provided
            if cos_key:
                session = db.get(Session, session_id)
                if session:
                    session.cos_key = cos_key
                    db.add(session)

            db.commit()

        logger.info(f"Saved {len(utterances)} utterances for session {session_id}")
