from pathlib import Path
import inject
from omegaconf import DictConfig, OmegaConf
import os
import json
import tempfile
import logging

from .utils import add_attribute
from .session_manager import AWSSessionManager

logging.basicConfig(level=logging.INFO)

class ConfigManager:
    CONFIG_CACHE_PATH = Path(tempfile.gettempdir()) / "intellipat_config_cache.yaml"
    CREDENTIALS_FILE = Path(tempfile.gettempdir()) / "aws_credentials.json"

    def __init__(self):
        self._config_cache = None

    def config_binder(self, binder, cfg):
        """Bind the configuration to the injector."""
        binder.bind(DictConfig, cfg)

    def load_config(self, config_file: str):
        """Load configuration from a local file and cache it on disk."""
        try:
            self._config_cache = OmegaConf.load(config_file)
            inject.configure(lambda binder: self.config_binder(binder, self._config_cache))
            OmegaConf.save(self._config_cache, self.CONFIG_CACHE_PATH)
            logging.info("Configuration loaded successfully from local file.")
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")

    def load_default_config(self, config_file: str = 'config/default.yaml'):
        """Load the default yaml from a local file"""
        try:
            default_config = OmegaConf.load(config_file)
            environment = str(default_config['current_environment'])
            if environment in default_config['downloadable_configs']:
                s3_config_bucket = str(default_config['s3_config_bucket'])
                s3_config_file = str(Path(f"{default_config['s3_config_path']}/{environment}.yaml"))
                return s3_config_bucket, s3_config_file
            else:
                local_config_file = f"config/{environment}.yaml"
                return None, local_config_file
        except Exception as e:
            logging.error(f"Error loading default configuration file: {e}")

    def load_config_from_dict(self, dict_config_template: dict):
        """Load the configuration from a dictionary"""
        try:
            self._config_cache = OmegaConf.create(dict_config_template)
            inject.configure(lambda binder: self.config_binder(binder, self._config_cache))
            logging.info("Configuration loaded successfully from dictionary.")
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")

    def load_config_from_s3(self, bucket: str, config_file: str, save_cache: bool = True):
        """Load configuration from an S3 bucket and cache it on disk using AWSSessionManager."""
        try:
            # Use AWSSessionManager to get the current AWS session
            aws_session_manager = AWSSessionManager.instance()
            session = aws_session_manager.get_session()
            
            # Create S3 client from the AWS session
            s3 = session.client('s3')
            
            # Fetch the configuration file from S3
            s3_object = s3.get_object(Bucket=bucket, Key=config_file)
            config_data = s3_object['Body'].read().decode('utf-8')
            
            # Create OmegaConf from the retrieved config data
            self._config_cache = OmegaConf.create(config_data)
            inject.configure(lambda binder: self.config_binder(binder, self._config_cache))

            if save_cache:
                if not hasattr(self, 'CONFIG_CACHE_PATH'):
                    raise ValueError("CONFIG_CACHE_PATH is not defined.")

                # Save the loaded config to a local cache
                OmegaConf.save(self._config_cache, self.CONFIG_CACHE_PATH)
            logging.info("Configuration loaded successfully from S3.")
        except Exception as e:
            logging.error(f"Error loading configuration from S3: {e}")

    def load_config_from_default(self):
        bucket, file = self.load_default_config()
        if bucket is not None:
            self.load_config_from_s3(bucket, file)
        else:
            self.load_config(file)

    def load_cached_config(self):
        """Check and load cached configuration from disk."""
        if self.CONFIG_CACHE_PATH.is_file():
            try:
                self._config_cache = OmegaConf.load(self.CONFIG_CACHE_PATH)
                inject.configure(lambda binder: self.config_binder(binder, self._config_cache))
                self.load_aws_credentials()
                return True
            except Exception as e:
                logging.error(f"Error loading cached configuration: {e}")
        return False

    def load_aws_credentials(self):
        """Load AWS credentials from the cached file."""
        if os.path.exists(self.CREDENTIALS_FILE):
            try:
                with open(self.CREDENTIALS_FILE, 'r') as file:
                    credentials = json.load(file)
                    os.environ.update(credentials)
                    logging.info("AWS credentials loaded from cache.")
            except Exception as e:
                logging.error(f"Error loading AWS credentials: {e}")

    def test_aws_credentials(self):
        """Test AWS credentials to check if they are valid."""
        try:
            # Use AWSSessionManager to validate the credentials
            aws_session_manager = AWSSessionManager.instance()
            session = aws_session_manager.get_session()
            sts = session.client("sts")
            sts.get_caller_identity()
            return True
        except Exception as e:
            logging.error(f"Invalid AWS credentials: {e}")
            return False

    def reset_aws_credentials(self):
        """Reset AWS credentials for a session."""
        keys_to_unset = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "REGION"]
        for key in keys_to_unset:
            os.environ.pop(key, None)

        try:
            aws_access_key_id = input("Enter your AWS Access Key ID: ").strip()
            aws_secret_access_key = input("Enter your AWS Secret Access Key: ").strip()
            aws_session_token = input("Enter your AWS Session Token: ").strip()
            region = input("Enter your region: ").strip()

            if not aws_access_key_id or not aws_secret_access_key or not aws_session_token:
                raise ValueError("AWS credentials must not be empty.")

            os.environ["AWS_ACCESS_KEY_ID"] = aws_access_key_id
            os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret_access_key
            os.environ["AWS_SESSION_TOKEN"] = aws_session_token
            os.environ["REGION"] = region

            credentials = {
                "AWS_ACCESS_KEY_ID": aws_access_key_id,
                "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
                "AWS_SESSION_TOKEN": aws_session_token,
                "REGION": region
            }

            with open(self.CREDENTIALS_FILE, 'w') as file:
                json.dump(credentials, file)

            logging.info("AWS credentials have been reset and cached in the file.")
        except Exception as e:
            logging.error(f"Error resetting AWS credentials: {e}")

    def ensure_config_loaded(self):
        """Ensure configuration is loaded before executing commands."""
        if not self.load_cached_config() or not self.test_aws_credentials():
            raise Exception("Configuration must be loaded before running any other command.")

    def clear_cache(self):
        """Clear cached configuration."""
        if self.CONFIG_CACHE_PATH.is_file():
            self.CONFIG_CACHE_PATH.unlink()
            logging.info("Configuration cache cleared.")
        else:
            logging.info("No cached configuration found.")

########################################################################################


def setup_aws(opt={}):
    opt = add_attribute("region", opt)
    try:
        aws_session_manager = AWSSessionManager.instance(opt=opt)
        session = aws_session_manager.get_session()
        return session
    except Exception as e:
        logging.error(f"Unable to create AWS session. {e}")
        raise e
    

def init_config(method, **kwargs):
    """
    Function to load configuration using the Configuration Manager class\n\n

    Methods:\n
        s3 - [bucket] and [config_file]. For the file, specify api/dev.yaml or gateway/dev.yaml.\n
        local - [config_file]
        dict - [dict_config_template]
        default - No arguments
    
    """
    config_manager = ConfigManager()
    config_types = {
        "s3": config_manager.load_config_from_s3,
        "local": config_manager.load_config,
        "dict": config_manager.load_config_from_dict,
        "default": config_manager.load_config_from_default,
    }

    if method == "s3":
        if 'bucket' in kwargs and 'config_file' in kwargs:
            return config_types[method](kwargs['bucket'], kwargs['config_file'], kwargs.get('save_cache', True))
        else:
            raise ValueError("For 's3' method, 'bucket' and 'config_file' must be provided.")
    
    elif method == "local":
        if 'config_file' in kwargs:
            return config_types[method](kwargs['config_file'])
        else:
            raise ValueError("For 'local' method, 'config_file' must be provided.")
    
    elif method == "dict":
        if 'dict_config_template' in kwargs:
            return config_types[method](kwargs['dict_config_template'])
        else:
            raise ValueError("For 'dict' method, 'dict_config_template' must be provided.")
    
    elif method == "default":
        return config_types[method]()
    
    else:
        raise ValueError(f"Invalid method '{method}' specified.")
