import configparser
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("minegit.settings")


class SettingsController:
    SECTION_NAME = "minegit"
    REPOSITORY_PATH_KEY = "repository_path"
    SHOW_DEBUG_LOGS_KEY = "show_debug_logs"

    def __init__(self, settings_file_path: str = "./minegitSettings.ini") -> None:
        self.settings_file_path = Path(settings_file_path).expanduser().resolve()
        logger.debug("Settings controller initialized with file '%s'.", self.settings_file_path)

    def load_repository_path(self) -> Optional[str]:
        parser = self._load_parser()
        if parser is None:
            return None
        if not parser.has_section(self.SECTION_NAME):
            logger.debug("Settings file has no '%s' section.", self.SECTION_NAME)
            return None

        repository_path = parser.get(self.SECTION_NAME, self.REPOSITORY_PATH_KEY, fallback="").strip()
        if repository_path:
            logger.debug("Loaded repository_path from settings: '%s'.", repository_path)
            return repository_path

        logger.debug("repository_path key is missing or empty in settings file.")
        return None

    def save_repository_path(self, repository_path: str) -> None:
        parser = self._load_parser_for_write()
        self._ensure_section(parser)

        normalized_path = repository_path.strip()
        parser.set(self.SECTION_NAME, self.REPOSITORY_PATH_KEY, normalized_path)
        self._write_parser(parser)
        logger.info("Saved repository path to settings file.")

    def load_show_debug_logs(self, default: bool = False) -> bool:
        parser = self._load_parser()
        if parser is None or not parser.has_section(self.SECTION_NAME):
            logger.debug(
                "Using default show_debug_logs=%s because settings are missing.",
                default,
            )
            return default

        value = parser.get(self.SECTION_NAME, self.SHOW_DEBUG_LOGS_KEY, fallback="").strip()
        if not value:
            logger.debug(
                "show_debug_logs key missing/empty; using default value %s.",
                default,
            )
            return default

        normalized = value.lower()
        if normalized in {"1", "true", "yes", "on"}:
            logger.debug("Loaded show_debug_logs=True from settings.")
            return True
        if normalized in {"0", "false", "no", "off"}:
            logger.debug("Loaded show_debug_logs=False from settings.")
            return False

        logger.warning(
            "Invalid show_debug_logs value '%s' in settings; using default %s.",
            value,
            default,
        )
        return default

    def save_show_debug_logs(self, show_debug_logs: bool) -> None:
        parser = self._load_parser_for_write()
        self._ensure_section(parser)
        parser.set(self.SECTION_NAME, self.SHOW_DEBUG_LOGS_KEY, "true" if show_debug_logs else "false")
        self._write_parser(parser)
        logger.info("Saved show_debug_logs=%s to settings file.", show_debug_logs)

    def _load_parser(self) -> Optional[configparser.ConfigParser]:
        if not self.settings_file_path.exists():
            logger.debug("Settings file does not exist yet: '%s'.", self.settings_file_path)
            return None

        parser = configparser.ConfigParser()
        parser.read(self.settings_file_path, encoding="utf-8")
        return parser

    def _load_parser_for_write(self) -> configparser.ConfigParser:
        parser = configparser.ConfigParser()
        if self.settings_file_path.exists():
            parser.read(self.settings_file_path, encoding="utf-8")
        return parser

    def _ensure_section(self, parser: configparser.ConfigParser) -> None:
        if not parser.has_section(self.SECTION_NAME):
            parser.add_section(self.SECTION_NAME)

    def _write_parser(self, parser: configparser.ConfigParser) -> None:
        self.settings_file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.settings_file_path.open("w", encoding="utf-8") as settings_file:
            parser.write(settings_file)
