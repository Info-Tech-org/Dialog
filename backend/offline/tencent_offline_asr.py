"""
Tencent Cloud Offline ASR with Speaker Diarization
"""

import logging
import time
import json
from typing import List, Dict, Any
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.asr.v20190614 import asr_client, models

from config import settings
from realtime.harmful_rules import is_harmful

logger = logging.getLogger(__name__)


class TencentOfflineASR:
    """
    Tencent Cloud Offline ASR with Speaker Diarization
    Docs:
    - ASR: https://cloud.tencent.com/document/product/1093/37823
    - Speaker Diarization: https://cloud.tencent.com/document/product/1093/52097
    """

    def __init__(self):
        cred = credential.Credential(
            settings.tencent_secret_id,
            settings.tencent_secret_key
        )

        http_profile = HttpProfile()
        http_profile.endpoint = "asr.tencentcloudapi.com"

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile

        self.client = asr_client.AsrClient(cred, settings.tencent_asr_region, client_profile)

    def create_recognition_task(self, audio_path: str) -> str:
        """
        Create offline ASR task

        Args:
            audio_path: Audio file URL (must be accessible from Tencent Cloud)
        Returns:
            task_id: Task ID
        """
        try:
            req = models.CreateRecTaskRequest()
            params = {
                "EngineModelType": "16k_zh",
                "ChannelNum": 1,
                "ResTextFormat": 0,  # Format 0 for better speaker diarization
                "SourceType": 0,
                "Url": audio_path,
                "SpeakerDiarization": 1,  # Enable speaker diarization
                "SpeakerNumber": 0,  # 0: auto-detect
                "FilterDirty": 0,
                "FilterModal": 0,
                "FilterPunc": 0,
                "ConvertNumMode": 1,
            }
            req.from_json_string(json.dumps(params))

            resp = self.client.CreateRecTask(req)
            result = json.loads(resp.to_json_string())

            task_id = result['Data']['TaskId']
            logger.info(f"Created ASR task: {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"Failed to create ASR task: {e}", exc_info=True)
            raise

    def query_recognition_result(self, task_id: str) -> Dict[str, Any]:
        """
        Query ASR task result

        Args:
            task_id: Task ID

        Returns:
            Recognition result
        """
        try:
            req = models.DescribeTaskStatusRequest()
            params = {
                "TaskId": task_id
            }
            req.from_json_string(json.dumps(params))

            resp = self.client.DescribeTaskStatus(req)
            result = json.loads(resp.to_json_string())

            return result['Data']

        except Exception as e:
            logger.error(f"Failed to query ASR result: {e}", exc_info=True)
            raise

    def wait_for_completion(self, task_id: str, max_wait: int = 600) -> Dict[str, Any]:
        """
        Wait for task completion

        Args:
            task_id: Task ID
            max_wait: Maximum wait time in seconds

        Returns:
            Recognition result
        """
        start_time = time.time()

        while True:
            result = self.query_recognition_result(task_id)
            status = result.get('Status', 0)

            if status == 2:
                # Success
                logger.info(f"ASR task {task_id} completed successfully")
                return result
            elif status == 3:
                # Failed
                error_msg = result.get('ErrorMsg', 'Unknown error')
                logger.error(f"ASR task {task_id} failed: {error_msg}")
                raise Exception(f"ASR task failed: {error_msg}")
            elif time.time() - start_time > max_wait:
                # Timeout
                logger.error(f"ASR task {task_id} timed out")
                raise Exception("ASR task timed out")
            else:
                # In progress
                logger.info(f"ASR task {task_id} in progress... status={status}")
                time.sleep(5)

    def parse_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse ASR result

        Args:
            result: Raw ASR result

        Returns:
            List of utterances
        """
        utterances = []

        result_text = result.get('Result', '')
        if not result_text:
            logger.warning("No recognition result found")
            return utterances

        result_detail_raw = result.get('ResultDetail')

        if result_detail_raw is None:
            # Parse Result field when ResultDetail is None
            # Format: [start:end,speaker_id] text
            logger.info("Parsing Result field (ResultDetail is None)")

            import re
            # Match pattern: [0:0.820,0:3.290,0]  text content
            pattern = r'\[0:([\d.]+),0:([\d.]+),(\d+)\]\s+(.+?)(?=\n\[|$)'
            matches = re.findall(pattern, result_text, re.DOTALL)

            for match in matches:
                start_time = float(match[0])
                end_time = float(match[1])
                speaker_id = int(match[2])
                text = match[3].strip()

                # Speaker label: 0 -> A, 1 -> B
                speaker = chr(65 + speaker_id)

                utterances.append({
                    "start": start_time,
                    "end": end_time,
                    "speaker": speaker,
                    "text": text,
                    "harmful_flag": is_harmful(text)
                })

            logger.info(f"Parsed {len(utterances)} utterances from Result field")
            return utterances

        # Parse ResultDetail when available
        if isinstance(result_detail_raw, str):
            result_detail = json.loads(result_detail_raw)
        else:
            result_detail = result_detail_raw

        for segment in result_detail:
            # Get speaker ID
            speaker_id = segment.get('SpeakerId', segment.get('SpeakerTag', 0))
            speaker = chr(65 + speaker_id)  # 0 -> A, 1 -> B, etc.

            # Get text
            text = segment.get('FinalSentence', '')

            # Get timestamps (convert ms to seconds)
            start_time = segment.get('StartMs', segment.get('StartTime', 0)) / 1000
            end_time = segment.get('EndMs', segment.get('EndTime', 0)) / 1000

            # Check if harmful
            harmful = is_harmful(text)

            utterances.append({
                "start": start_time,
                "end": end_time,
                "speaker": speaker,
                "text": text,
                "harmful_flag": harmful
            })

        logger.info(f"Parsed {len(utterances)} utterances from ASR result")
        return utterances

    def process(self, audio_url: str) -> List[Dict[str, Any]]:
        """
        Process audio file (complete workflow)

        Args:
            audio_url: Audio file URL (must be publicly accessible)
        Returns:
            List of utterances
        """
        # Create task
        task_id = self.create_recognition_task(audio_url)

        # Wait for completion
        result = self.wait_for_completion(task_id)

        # Parse result
        utterances = self.parse_result(result)

        return utterances
