import boto3
import os
import logging
from botocore.exceptions import ClientError, NoCredentialsError, NoRegionError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AWSSessionManager:
    _instance = None
    _session = None
    _opt = {}

    def __new__(cls, opt={}):
        if cls._instance is None:
            cls._instance = super(AWSSessionManager, cls).__new__(cls)
            cls._opt = opt
        return cls._instance

    @classmethod
    def instance(cls, opt={}):
        if cls._instance is None:
            cls._instance = cls(opt)
        cls._opt = opt
        return cls._instance

    def get_session(self, opt=None):
        if self._session is None or not self._is_session_valid():
            self._create_session(opt=opt)
        return self._session

    def refresh_session(self, opt=None):
        """Always create a new session, used for retrying failed operations"""
        self._create_session(opt=opt)
        return self._session

    def _create_session(self, opt=None):
        """Create a session based on credentials (temp creds, access keys, or instance role)"""
        region = opt.get("region") if opt else self._opt.get("region") or os.getenv("AWS_DEFAULT_REGION", "us-east-2")
        use_keys = os.getenv("USE_KEYS", "false").lower() == "true"

        logger.info(f"Creating AWS session. Region: {region}. Use Keys: {use_keys}")

        # Check if temporary credentials are provided via options
        if self._opt.get("use_temp_creds"):
            logger.info("Using temporary credentials from options")
            self._session = boto3.Session(
                aws_access_key_id=self._opt.get("aws_access_key_id"),
                aws_secret_access_key=self._opt.get("aws_secret_access_key"),
                aws_session_token=self._opt.get("aws_session_token"),
                region_name=region,
            )
        elif use_keys:
            # Manual credentials from environment variables
            if os.getenv("AWS_SESSION_TOKEN"):
                logger.info("Using environment variables for temporary credentials")
                self._session = boto3.Session(
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
                    region_name=region,
                )
            else:
                logger.info("Using environment variables for access and secret key")
                self._session = boto3.Session(
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                    region_name=region,
                )
        else:
            # Fallback to instance role or profile-based session
            try:
                profile_name = self._opt.get("profile", os.getenv("AWS_PROFILE"))
                if profile_name:
                    logger.info(f"Using profile: {profile_name}")
                    self._session = boto3.Session(profile_name=profile_name, region_name=region)
                else:
                    logger.info("Using default boto3 session (e.g., instance role)")
                    self._session = boto3.Session(region_name=region)
            except (NoCredentialsError, NoRegionError) as e:
                logger.error(f"Failed to create session: {e}")
                raise

    def _is_session_valid(self):
        """Check if the session is valid by calling a simple STS API"""
        try:
            sts = self._session.client("sts")
            sts.get_caller_identity()
            return True
        except (ClientError, AttributeError) as e:
            logger.warning(f"Session invalid: {e}")
            return False
