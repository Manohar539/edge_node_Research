from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "settings.yaml"


def load_config():
    """Load and return the project configuration."""

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Configuration file was not found: {CONFIG_FILE}"
        )

    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not config:
        raise ValueError("The configuration file is empty.")

    required_sections = [
        "project",
        "mqtt",
        "experiment",
        "controller",
        "cloud",
        "output",
    ]

    missing_sections = [
        section for section in required_sections if section not in config
    ]

    if missing_sections:
        raise ValueError(
            f"Missing configuration sections: {missing_sections}"
        )

    return config


if __name__ == "__main__":
    settings = load_config()

    print("Configuration loaded successfully")
    print(f"Project: {settings['project']['name']}")
    print(f"MQTT broker: {settings['mqtt']['broker']}")
    print(f"Tasks: {settings['experiment']['number_of_tasks']}")
    print(f"AWS region: {settings['cloud']['region']}")