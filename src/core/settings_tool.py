"""Refactored core tool utilities with improved structure and error handling."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from config.settings import config
from utils.exceptions import ConfigurationError
from utils.file_utils import ensure_directory
from utils.logger import get_logger

logger = get_logger(__name__)


class SettingsManager:
    """Manages application settings with environment variable override support."""

    def __init__(self, settings_file: Optional[Path] = None):
        """
        Initialize settings manager.

        Args:
            settings_file: Path to settings file (defaults to static/settings.json)
        """
        self.settings_file = settings_file or config.STATIC_DIR / "settings.json"
        self._settings_cache: Optional[Dict[str, Any]] = None
        self._ensure_settings_file()

    def _ensure_settings_file(self) -> None:
        """Ensure settings file exists with default values."""
        if not self.settings_file.exists():
            ensure_directory(self.settings_file.parent)
            default_settings = self._get_default_settings()
            self._write_settings(default_settings)
            logger.info(f"Created settings file with defaults: {self.settings_file}")

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings configuration."""
        return {
            # API Configuration
            "api_port": "15372",
            "enable_api": "True",
            # PT-Gen Configuration
            "pt_gen_api_url": "https://ptgen.agsvpt.work/",
            "pt_gen_api_url_backup": "https://ptgen.agsvpt.work/",
            # Image hosting
            "picture_bed_api_url": "https://freeimage.host/api/1/upload",
            "picture_bed_api_token": "6d207e02198a847aa98d0a2a901485a5",
            # Screenshot settings
            "screenshot_storage_path": "temp/pic",
            "screenshot_number": "3",
            "screenshot_threshold": "30.0",
            "screenshot_start_percentage": "0.10",
            "screenshot_end_percentage": "0.90",
            "auto_upload_screenshot": "True",
            "paste_screenshot_url": "True",
            "delete_screenshot": "True",
            "auto_download_upload_poster": "False",
            # Thumbnail settings
            "do_get_thumbnail": "True",
            "thumbnail_rows": "3",
            "thumbnail_cols": "3",
            "thumbnail_delay": "2.0",
            # File management
            "torrent_storage_path": "temp/torrent",
            "media_info_suffix": "True",
            "make_dir": "True",
            "rename_file": "True",
            "create_hard_link": "True",
            "second_confirm_file_name": "True",
            # Naming templates - Movies
            "main_title_movie": "{en_title} {year} {video_format} {source} {video_codec} {bit_depth} {hdr_format} {frame_rate} {audio_codec} {channels} {audio_num}-{team}",
            "second_title_movie": "{original_title} / {other_titles} | 类型：{categories} | 演员：{actors}",
            "file_name_movie": "{original_title}.{en_title}.{year}.{video_format}.{source}.{video_codec}.{bit_depth}.{hdr_format}.{frame_rate}.{audio_codec}.{channels}.{audio_num}-{team}",
            # Naming templates - TV Shows
            "main_title_tv": "{en_title} S{season} {year} {video_format} {source} {video_codec} {bit_depth} {hdr_format} {frame_rate} {audio_codec} {channels} {audio_num}-{team}",
            "second_title_tv": "{original_title} / {other_titles} | {total_episodes} | 类型：{categories} | 演员：{actors}",
            "file_name_tv": "{original_title}.{en_title}.S{season}E{episode}.{year}.{video_format}.{source}.{video_codec}.{bit_depth}.{hdr_format}.{frame_rate}.{audio_codec}.{channels}.{audio_num}-{team}",
            # Naming templates - Playlets
            "main_title_playlet": "{en_title} S{season} {year} {video_format} {source} {video_codec} {bit_depth} {hdr_format} {frame_rate} {audio_codec} {channels} {audio_num}-{team}",
            "second_title_playlet": "{original_title} | {total_episodes} | {year}年 | {playlet_source} | 类型：{categories}",
            "file_name_playlet": "{original_title}.{en_title}.S{season}E{episode}.{year}.{video_format}.{source}.{video_codec}.{bit_depth}.{hdr_format}.{frame_rate}.{audio_codec}.{channels}.{audio_num}-{team}",
            # Auto feed configuration
            "auto_feed_link": "https://example.com/upload.php#separator#name#linkstr#{主标题}#linkstr#small_descr#linkstr#{副标题}#linkstr#url#linkstr#{IMDB}#linkstr#dburl#linkstr#{豆瓣}#linkstr#descr#linkstr#{简介}[quote]{MediaInfo}[/quote]#linkstr#log_info#linkstr##linkstr#tracklist#linkstr##linkstr#music_type#linkstr##linkstr#music_media#linkstr##linkstr#edition_info#linkstr##linkstr#music_name#linkstr##linkstr#music_author#linkstr##linkstr#animate_info#linkstr##linkstr#anidb#linkstr##linkstr#torrentName#linkstr##linkstr#images#linkstr##linkstr#torrent_name#linkstr#{种子名称}#linkstr#torrent_url#linkstr#{种子链接}#linkstr#type#linkstr#{类型}#linkstr#source_sel#linkstr#{地区}#linkstr#standard_sel#linkstr#{分辨率}#linkstr#audiocodec_sel#linkstr#{音频编码}#linkstr#codec_sel#linkstr#{视频编码}#linkstr#medium_sel#linkstr#{媒介}#linkstr#origin_site#linkstr#{小组}#linkstr#origin_url#linkstr##linkstr#golden_torrent#linkstr#false#linkstr#mediainfo_cmct#linkstr##linkstr#imgs_cmct#linkstr##linkstr#full_mediainfo#linkstr##linkstr#subtitles#linkstr##linkstr#youtube_url#linkstr##linkstr#ptp_poster#linkstr##linkstr#comparisons#linkstr##linkstr#version_info#linkstr##linkstr#multi_mediainfo#linkstr##linkstr#labels#linkstr#0",
            "open_auto_feed_link": "True",
            # Personal signature
            "personalized_signature": "",
        }

    def _read_settings(self) -> Dict[str, Any]:
        """Read settings from file."""
        try:
            with open(self.settings_file, "r", encoding="utf-8") as file:
                settings = json.load(file)
            logger.debug(f"Loaded settings from {self.settings_file}")
            return settings
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read settings file: {e}")
            raise ConfigurationError(f"Invalid settings file: {self.settings_file}")

    def _write_settings(self, settings: Dict[str, Any]) -> None:
        """Write settings to file."""
        try:
            with open(self.settings_file, "w", encoding="utf-8") as file:
                json.dump(settings, file, indent=4, ensure_ascii=False)
            logger.debug(f"Saved settings to {self.settings_file}")
            # Clear cache to force reload
            self._settings_cache = None
        except IOError as e:
            logger.error(f"Failed to write settings file: {e}")
            raise ConfigurationError(
                f"Cannot write to settings file: {self.settings_file}"
            )

    def get_setting(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Get a setting value with environment variable override.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value (environment variable takes precedence)
        """
        # Check environment variable first (uppercase key)
        env_value = os.environ.get(key.upper())
        if env_value is not None:
            logger.debug(f"Using environment variable for {key}: {env_value}")
            return env_value

        # Load from cache or file
        if self._settings_cache is None:
            self._settings_cache = self._read_settings()

        value = self._settings_cache.get(key, default)

        # Handle legacy key compatibility
        value = self._handle_legacy_keys(value)

        logger.debug(f"Retrieved setting {key}: {value}")
        return value

    def _handle_legacy_keys(self, value: Any) -> Any:
        """Handle legacy key compatibility."""
        if isinstance(value, str):
            # Update deprecated template variables
            replacements = {
                "{category}": "{categories}",
                "{total_episode}": "{total_episodes}",
            }

            original_value = value
            for old, new in replacements.items():
                if old in value:
                    value = value.replace(old, new)

            # Update setting if it was changed
            if value != original_value:
                logger.info(
                    f"Updated legacy template variables: {original_value} -> {value}"
                )

        return value

    def update_setting(self, key: str, value: Any) -> None:
        """
        Update a setting value.

        Args:
            key: Setting key
            value: New value
        """
        # Load current settings
        settings = self._read_settings()
        settings[key] = value

        # Save updated settings
        self._write_settings(settings)
        logger.info(f"Updated setting {key}: {value}")

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        if self._settings_cache is None:
            self._settings_cache = self._read_settings()
        return self._settings_cache.copy()

    def update_all_settings(self, settings: Dict[str, Any]) -> None:
        """
        Update all settings.

        Args:
            settings: New settings dictionary
        """
        self._write_settings(settings)
        logger.info("Updated all settings")

    def reset_to_defaults(self) -> None:
        """Reset settings to default values."""
        default_settings = self._get_default_settings()
        self._write_settings(default_settings)
        logger.info("Reset settings to defaults")


# Global settings manager instance
settings_manager = SettingsManager()


def get_settings(key: str, default: Optional[Any] = None) -> Any:
    """
    Convenience function to get a setting value.

    Args:
        key: Setting key
        default: Default value if key not found

    Returns:
        Setting value
    """
    return settings_manager.get_setting(key, default)


def update_settings(key: str, value: Any) -> None:
    """
    Convenience function to update a setting value.

    Args:
        key: Setting key
        value: New value
    """
    settings_manager.update_setting(key, value)


def get_settings_json() -> Dict[str, Any]:
    """
    Convenience function to get all settings.

    Returns:
        All settings as dictionary
    """
    return settings_manager.get_all_settings()


def update_settings_json(settings: Dict[str, Any]) -> None:
    """
    Convenience function to update all settings.

    Args:
        settings: New settings dictionary
    """
    settings_manager.update_all_settings(settings)


def combine_directories(relative_path: str) -> str:
    """
    Combine current working directory with relative path.

    Args:
        relative_path: Relative path to combine

    Returns:
        Combined absolute path
    """
    return str(Path.cwd() / relative_path)
