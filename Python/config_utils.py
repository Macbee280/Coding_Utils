# The lowest-level utilities, able to be imported anywhere

# Global Package Imports
import os
import boto3
from pathlib import Path
import inject
from omegaconf import DictConfig
import hydra
from hydra.core.global_hydra import GlobalHydra
from omegaconf import DictConfig, OmegaConf
import logging


def configure_opt(app, **kwargs):
    applications = {
        "default": configure_opt_default,
    }
    return applications[app](**kwargs)

def configure_opt_default(**kwargs):
    return {
        "application": "Unknown"
        if "application" not in kwargs.keys()
        else kwargs["application"],
        "name_space": os.getenv("NAME_SPACE")
        if "name_space" not in kwargs.keys()
        else kwargs["name_space"],
        "region": os.getenv("REGION")
        if "region" not in kwargs.keys()
        else kwargs["region"],
        "s3_bucket": None if "s3_bucket" not in kwargs.keys() else kwargs["name_space"],
        "s3_file": None if "s3_file" not in kwargs.keys() else kwargs["name_space"],
        "current_directory": Path("../")
        if "current_directory" not in kwargs.keys()
        else kwargs["current_directory"],
        "local_only": False,
        "verbose": False,
        "use_keys": False if "use_keys" not in kwargs.keys() else kwargs["use_keys"],
    }

def find_key(data, target):
    def search(data, target, path):
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = path + [key]
                if key == target:
                    return new_path
                result = search(value, target, new_path)
                if result is not None:
                    return result
        return None

    return search(data, target, [])


def get_value(data, path):
    for key in path:
        if isinstance(data, dict):
            data = data.get(key)
            if data is None:
                return None
        else:
            return None
    return data


def add_attribute(key, opt: dict):
    if key not in opt:
        try:
            config = inject.instance(DictConfig)
            config_dict = OmegaConf.to_container(config, resolve=True)
            path = find_key(config_dict, key)
        except:
            pass

        if path is not None:
            opt[key] = get_value(config_dict, path)

        else:
            opt[key] = None
    return opt


def add_attributes(keys: list, opt: dict):
    for key in keys:
        opt = add_attribute(key, opt)
    return opt


def hydra_config_provider(environment: str, config_folder_path: str):
    GlobalHydra.instance().clear()
    hydra.initialize(config_path=str(config_folder_path), version_base=str(1.1))
    cfg = hydra.compose(config_name=f"{environment}.yaml")
    return cfg


def load_config(config_file: str) -> DictConfig:
    cfg = OmegaConf.load(config_file)
    return cfg


def init_omegaconf_config(config_folder: Path):
    init_config = load_config(str(config_folder / "default.yaml"))
    environment = str(init_config["current_environment"])
    config_path = config_folder / f"{environment}.yaml"
    return load_config(str(config_path))


def init_hydra_config(config_folder: Path):
    init_config = OmegaConf.load(str(config_folder / "default.yaml"))
    environment = str(init_config["current_environment"])
    return hydra_config_provider(environment, str(config_folder))


def config_binder(binder, cfg):
    # load_dotenv()
    binder.bind(DictConfig, cfg)


def init_config(config_folder: Path):
    print(config_folder.resolve())
    cfg = init_omegaconf_config(config_folder.resolve())
    # cfg = init_hydra_config(config_folder)
    inject.configure(lambda binder: config_binder(binder, cfg))


def init_config_from_dict(dict_based_config):
    # Initialize/bind an omegaconf config from a dictionary
    cfg = OmegaConf.create(dict_based_config)
    inject.configure(lambda binder: config_binder(binder, cfg))


def setup_aws(opt={}):
    opt = add_attribute("region", opt)
    use_keys = os.getenv("USE_KEYS")

    if use_keys is not None and use_keys == "true":
        if os.getenv("AWS_SESSION_TOKEN") is not None:
            session = boto3.Session(
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
                region_name=opt["region"],
            )
        else:
            session = boto3.Session(
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=opt["region"],
            )
    else:
        session = boto3.Session(region_name=opt["region"])

    return session


def download_configs(config_folder):
    # Config Setup
    config_logger = logging.getLogger(__name__)
    initial_config = OmegaConf.load(str(config_folder / "default.yaml"))
    environment = str(initial_config["current_environment"])

    if environment in initial_config["downloadable_configs"]:
        s3_config_bucket = str(initial_config["s3_config_bucket"])
        s3_config_file = str(
            Path(str(initial_config["s3_config_path"])) / f"{environment}.yaml"
        )
        local_config_file = str(config_folder / f"{environment}.yaml")
        running_in_aws = os.getenv("USE_KEYS")

        if running_in_aws is not None and running_in_aws == "true":
            # Local development, provide credentials via environment variables
            if os.getenv("AWS_SESSION_TOKEN") is not None:
                session = boto3.Session(
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
                    region_name=initial_config["s3_config_region"],
                )
            else:
                session = boto3.Session(
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                    region_name=initial_config["s3_config_region"],
                )

        else:
            # In AWS, rely on the default credential provider chain (IAM role, etc.)
            session = boto3.Session(region_name=initial_config["s3_config_region"])

        s3_client = session.client("s3")

        try:
            s3_client.download_file(s3_config_bucket, s3_config_file, local_config_file)
            config_logger.info(
                f"Successfully updated local config {local_config_file} from {s3_config_bucket}/{s3_config_file}"
            )
        except Exception as e:
            config_logger.error(
                f"Error updating local config {local_config_file} from {s3_config_bucket}/{s3_config_file}: {e}"
            )
            raise e

def setup_configs(config_folder):
    config_folder = Path(config_folder)

    download_configs(config_folder = config_folder)

    init_config(config_folder)

    cfg = inject.instance(DictConfig)
