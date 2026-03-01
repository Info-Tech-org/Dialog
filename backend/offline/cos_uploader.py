"""
腾讯云对象存储 (COS) 上传工具
用于将本地音频文件上传到 COS，获取公网可访问的 URL
"""

import logging
import os
from qcloud_cos import CosConfig, CosS3Client
from config import settings

logger = logging.getLogger(__name__)


class COSUploader:
    """
    腾讯云 COS 上传器

    使用前需要：
    1. 开通腾讯云对象存储服务
    2. 创建存储桶（Bucket）
    3. 在 config/settings.py 中配置：
       - tencent_cos_region: COS 地域（如 ap-guangzhou）
       - tencent_cos_bucket: 存储桶名称
       - tencent_secret_id: SecretId
       - tencent_secret_key: SecretKey
    """

    def __init__(self):
        # COS 配置
        config = CosConfig(
            Region=settings.tencent_cos_region,
            SecretId=settings.tencent_secret_id,
            SecretKey=settings.tencent_secret_key,
            Scheme='https'
        )
        self.client = CosS3Client(config)
        self.bucket = settings.tencent_cos_bucket

    def upload_file(self, local_path: str, cos_key: str = None, use_presigned_url: bool = True, expire_seconds: int = 86400) -> tuple[str, str]:
        """
        上传文件到 COS

        Args:
            local_path: 本地文件路径
            cos_key: COS 对象键（路径），如果不指定则使用文件名
            use_presigned_url: 是否使用预签名 URL（用于私有读权限的存储桶）
            expire_seconds: 预签名 URL 有效期（秒）

        Returns:
            (cos_key, URL) 公网可访问的 URL（如果使用预签名，则为临时授权 URL）
        """
        if cos_key is None:
            cos_key = f"audio/{os.path.basename(local_path)}"

        try:
            logger.info(f"Uploading {local_path} to COS: {cos_key}")

            # 上传文件
            with open(local_path, 'rb') as fp:
                response = self.client.put_object(
                    Bucket=self.bucket,
                    Body=fp,
                    Key=cos_key,
                    ContentType='audio/mpeg'  # 可以根据文件类型动态设置
                )

            # 如果使用预签名 URL（适用于私有读权限）
            if use_presigned_url:
                url = self.generate_presigned_url(cos_key, expire_seconds)
                logger.info(f"Upload successful with presigned URL (valid for {expire_seconds}s)")
            else:
                url = f"https://{self.bucket}.cos.{settings.tencent_cos_region}.myqcloud.com/{cos_key}"
                logger.info(f"Upload successful: {url}")

            return cos_key, url

        except Exception as e:
            logger.error(f"Failed to upload to COS: {e}", exc_info=True)
            raise

    def generate_presigned_url(self, cos_key: str, expire_seconds: int) -> str:
        """生成下载预签名 URL"""
        return self.client.get_presigned_download_url(
            Bucket=self.bucket,
            Key=cos_key,
            Expired=expire_seconds
        )

    def delete_file(self, cos_key: str):
        """
        删除 COS 上的文件

        Args:
            cos_key: COS 对象键
        """
        try:
            self.client.delete_object(
                Bucket=self.bucket,
                Key=cos_key
            )
            logger.info(f"Deleted from COS: {cos_key}")
        except Exception as e:
            logger.error(f"Failed to delete from COS: {e}", exc_info=True)
