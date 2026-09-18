#!/usr/bin/env python3
"""
Publish Helper - Interactive CLI Mode
Provides a command-line interface for the one-key workflow.

Usage:
    python src/main_cli.py
"""
# isort: skip_file
# NOTE: Import order is critical - stdlib must come before local imports
# to avoid UnboundLocalError with os module
import sys
from pathlib import Path

# Add project root to sys.path so 'src.core' imports work when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.completion import PathCompleter, Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.key_binding import KeyBindings
from typing import Iterable
from src.core.autofeed import get_auto_feed_link
from src.core.mediainfo import get_media_info
from src.core.picturebed import upload_picture
from src.core.poster import process_poster
from src.core.ptgen import get_pt_gen_description
from src.core.rename import (
    create_hard_link,
    get_name_from_template,
    get_pt_gen_info,
    get_video_info,
    move_file_to_folder,
    rename_file,
    rename_folder,
)
from src.core.screenshot import get_screenshot, get_thumbnail
from src.core.tool import (
    check_path_and_find_video,
    chinese_name_to_pinyin,
    delete_season_number,
    get_playlet_description,
    get_settings,
    get_video_files,
    make_torrent,
)
import os
import shlex
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Import prompt_toolkit for enhanced path completion


class PathCompleterWithSlash(PathCompleter):
    """Custom PathCompleter that adds '/' or '\\' to directory completions when unambiguous."""

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Generate completions with trailing slash for directories when there's only one match."""
        # Collect all completions first to check count
        completions = list(super().get_completions(document, complete_event))

        # Debug: print completion count (remove after testing)
        # import sys
        # print(f"\nDEBUG: Found {len(completions)} completions", file=sys.stderr)
        # for c in completions:
        #     print(f"  - text='{c.text}' display='{c.display}' start_pos={c.start_position}", file=sys.stderr)

        # Only add separator if there's exactly one completion (unambiguous) AND it's a directory
        if len(completions) == 1:
            completion = completions[0]
            # PathCompleter adds "/" to display for directories but not to completion.text
            # Use display_text to get plain string from FormattedText
            display_str = completion.display_text
            is_directory = display_str.endswith('/')

            if is_directory:
                # Add os.sep to both completion text and display for directories
                # On Windows, also update display to show backslash instead of forward slash
                new_display = display_str
                if os.sep == '\\':
                    # On Windows, replace the trailing / with \
                    new_display = display_str[:-1] + '\\'

                # If completion.text is empty or None, insert just the separator
                # Otherwise append separator to the completion text
                if completion.text:
                    new_text = completion.text + os.sep
                else:
                    new_text = os.sep

                yield Completion(
                    text=new_text,
                    start_position=completion.start_position,
                    display=new_display,
                    display_meta=completion.display_meta,
                    style=completion.style,
                    selected_style=completion.selected_style,
                )
            else:
                # Single file, yield as-is
                yield completion
        else:
            # Multiple completions: yield them all as-is for cycling
            # But also add separator to directory completions for display consistency
            for completion in completions:
                # Use display_text to get plain string from FormattedText
                display_str = completion.display_text
                is_directory = display_str.endswith('/')

                if is_directory and os.sep == '\\':
                    # On Windows, show backslash in display even when multiple options
                    new_display = display_str[:-1] + '\\'
                    yield Completion(
                        text=completion.text,
                        start_position=completion.start_position,
                        display=new_display,
                        display_meta=completion.display_meta,
                        style=completion.style,
                        selected_style=completion.selected_style,
                    )
                else:
                    yield completion


def getch():
    """Read a single character from stdin without waiting for Enter."""
    if sys.platform == 'win32':
        import msvcrt
        ch = msvcrt.getch()
        # Handle special characters (arrows, etc.) that return two bytes
        if ch in (b'\x00', b'\xe0'):
            msvcrt.getch()  # Consume second byte
            return None
        return ch.decode('utf-8', errors='ignore')
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


def process_poster_in_description(description):
    """Process poster URLs in description if auto download/upload is enabled.

    Finds the first [img]URL[/img] tag in the description, downloads the poster,
    re-uploads it to the configured picture bed, and replaces the URL.
    """
    import re

    auto_download_upload_poster = get_settings('auto_download_upload_poster') == 'True'
    if not auto_download_upload_poster:
        return description

    # Extract poster URL from [img]...[/img] tag
    img_pattern = r'\[img\](https?://[^\]]+)\[/img\]'
    match = re.search(img_pattern, description)

    if not match:
        return description

    original_poster_url = match.group(1)
    print(f"检测到海报链接: {original_poster_url}")

    picture_bed_api_url = get_settings('picture_bed_api_url')
    picture_bed_api_token = get_settings('picture_bed_api_token')
    screenshot_storage_path = get_settings('screenshot_storage_path')

    print("正在下载并上传海报...")

    # Process the poster
    success, result = process_poster(
        original_poster_url,
        picture_bed_api_url,
        picture_bed_api_token,
        screenshot_storage_path
    )

    if success:
        uploaded_url = result
        print(f"{Colors.GREEN}✓ 海报上传成功: {uploaded_url}{Colors.END}")

        # Replace the original URL with uploaded URL
        description = description.replace(
            f'[img]{original_poster_url}[/img]',
            f'[img]{uploaded_url}[/img]'
        )
        print(f"{Colors.GREEN}✓ 已替换简介中的海报链接{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠ 海报上传失败: {result}{Colors.END}")

    return description


# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header():
    """Print the CLI header."""
    print(f"\n{Colors.CYAN}{'='*50}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  Publish Helper - Interactive CLI{Colors.END}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}\n")


def print_settings_summary():
    """Print active settings summary."""
    print(f"{Colors.BOLD}当前配置 / Current Settings:{Colors.END}")

    # File management
    rename_file = get_settings('rename_file') == 'True'
    make_dir = get_settings('make_dir') == 'True'
    create_hardlink = get_settings('create_hard_link') == 'True'

    # Screenshot settings
    auto_upload = get_settings('auto_upload_screenshot') == 'True'
    delete_after_upload = get_settings('delete_screenshot') == 'True'
    do_thumbnail = get_settings('do_get_thumbnail') == 'True'
    screenshot_num = get_settings('screenshot_number')

    print(
        f"  文件管理: 重命名={_status(rename_file)} | 创建目录={_status(make_dir)} | 硬链接={_status(create_hardlink)}")
    print(f"  截图设置: 数量={screenshot_num} | 缩略图={_status(do_thumbnail)} | 自动上传={_status(auto_upload)} | 上传后删除={_status(delete_after_upload)}")

    # Show path completion hint
    print(f"\n  {Colors.GREEN}✓ 路径自动补全已启用 (Tab 键选择补全，Enter 提交){Colors.END}")


def _status(enabled):
    """Format boolean status for display."""
    return f"{Colors.GREEN}✓{Colors.END}" if enabled else f"{Colors.RED}✗{Colors.END}"


def print_step(step_num, total, message):
    """Print a step indicator."""
    print(f"{Colors.BLUE}[{step_num}/{total}]{Colors.END} {message}")


def print_success(message):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_error(message):
    """Print an error message."""
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def print_warning(message):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")


def prompt(message, default=None):
    """Prompt user for input."""
    if default:
        user_input = input(
            f"{Colors.BOLD}{message}{Colors.END} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{Colors.BOLD}{message}{Colors.END}: ").strip()


def prompt_path(message, default=None):
    """Prompt for file path with tab completion support using prompt_toolkit."""
    # Use custom PathCompleter that adds slash to directories
    completer = PathCompleterWithSlash(expanduser=True)

    # Custom key bindings to refresh completions after accepting a directory
    kb = KeyBindings()

    @kb.add('tab')
    def _(event):
        """Handle Tab: start/cycle completion and refresh if directory completed."""
        b = event.app.current_buffer

        # Store text before completion to detect if we completed a directory
        text_before = b.text

        if b.complete_state:
            # Completion menu is open
            if b.complete_state.current_completion:
                # Apply the current completion
                b.apply_completion(b.complete_state.current_completion)
                # Check if we completed to a directory (text now ends with separator)
                if b.text.endswith(os.sep) or b.text.endswith('/'):
                    # Trigger new completion to show directory contents
                    b.start_completion(select_first=False)
            else:
                # No completion selected, cycle to next
                b.complete_next()
        else:
            # No completion menu - start completion
            b.start_completion(select_first=True)

    if default:
        result = pt_prompt(
            f"{message} [{default}]: ",
            completer=completer,
            complete_style=CompleteStyle.MULTI_COLUMN,
            complete_while_typing=True,
            key_bindings=kb,
            default=""
        )
        return result.strip() if result.strip() else default
    else:
        result = pt_prompt(
            f"{message}: ",
            completer=completer,
            complete_style=CompleteStyle.MULTI_COLUMN,
            complete_while_typing=True,
            key_bindings=kb
        )
        return result.strip()


def prompt_media_type():
    """Prompt user for media type."""
    print(f"\n{Colors.BOLD}选择媒体类型 / Select Media Type:{Colors.END}")
    print("  1. 电影 / Movie")
    print("  2. 电视剧 / TV Series")
    print("  3. 短剧 / Playlet")
    print("  0/q. 退出 / Quit")

    while True:
        print(f"\n选择 / Choice: ", end='', flush=True)
        choice = getch()
        if choice is None:
            continue
        print(choice)  # Echo the character
        if choice in ['1', '2', '3']:
            return {'1': 'movie', '2': 'tv', '3': 'playlet'}[choice]
        if choice in ['0', 'q', 'Q']:
            return None
        print_error("请输入 0, 1, 2, 或 3")


def select_from_combo_box(label, combo_data_name):
    """
    Interactive selection from combo box data with numbered options.
    User can select by number or enter custom value.

    Args:
        label: Display label(e.g., "来源 Source")
        combo_data_name: Name of combo box data('source', 'team', etc.)

    Returns:
        Selected or custom value
    """
    from src.core.tool import get_combo_box_data

    print(f"\n{Colors.BOLD}选择 {label}:{Colors.END}")

    # Get combo box data
    success, data_list = get_combo_box_data(combo_data_name)

    if not success or not data_list:
        # Fallback if no data available
        return prompt(f"{label}", "")

    # Filter out empty strings and display options
    valid_options = [item for item in data_list if item.strip()]

    if not valid_options:
        return prompt(f"{label}", "")

    # Display numbered options
    for idx, option in enumerate(valid_options, 1):
        print(f"  [{idx}] {option}")
    print(f"  [0] 自定义 / Custom")
    print()

    while True:
        choice = prompt(f"选择数字或直接输入 / Select number or enter custom", "1")

        # Check if it's a number selection
        if choice.isdigit():
            choice_num = int(choice)
            if choice_num == 0:
                # Custom input
                custom = prompt(f"输入自定义 {label}", "")
                return custom if custom else valid_options[0]
            elif 1 <= choice_num <= len(valid_options):
                return valid_options[choice_num - 1]
            else:
                print_error(f"请输入 0-{len(valid_options)} 之间的数字")
        else:
            # Direct custom input
            return choice if choice else valid_options[0]


def process_movie(resource_url, video_path):
    """Process a movie with the one-key workflow."""
    total_steps = 6

    # Collect all user choices FIRST before any API calls
    print(f"\n{Colors.BOLD}请完成以下选择 / Please make your selections:{Colors.END}\n")

    # Get Source and Team selections upfront
    source = select_from_combo_box("来源 Source", "source")
    team = select_from_combo_box("制作组 Team", "team")

    print(f"\n{Colors.GREEN}✓ 所有选择已完成，开始自动处理...{Colors.END}\n")

    # Step 1: Get PT-Gen description
    print_step(1, total_steps, "获取 PT-Gen 信息...")
    pt_gen_api_url = get_settings('pt_gen_api_url')

    success, response = get_pt_gen_description(pt_gen_api_url, resource_url)
    if not success:
        print_warning(f"主接口失败: {response}")

        # Try backup API
        pt_gen_api_url_backup = get_settings('pt_gen_api_url_backup')
        if pt_gen_api_url_backup and pt_gen_api_url_backup != pt_gen_api_url:
            print(f"  尝试备用接口: {pt_gen_api_url_backup}")
            success, response = get_pt_gen_description(
                pt_gen_api_url_backup, resource_url)
            if not success:
                print_error(f"备用接口也失败: {response}")
                return False
            print_success("备用接口获取成功")
        else:
            print_error("未配置备用接口或备用接口与主接口相同")
            return False

    # Response is a tuple (description_text, response_dict)
    # Extract just the description text for parsing
    if isinstance(response, tuple):
        description = response[0]  # First element is the formatted description
        pt_gen_data = response[1]  # Second element is the full API response
    else:
        description = response
        pt_gen_data = {}

    print_success("PT-Gen 信息获取成功")

    # Process poster in description (download and re-upload if enabled)
    description = process_poster_in_description(description)

    # Step 2: Parse PT-Gen info
    print_step(2, total_steps, "解析 PT-Gen 信息...")
    try:
        original_title, english_title, year, other_names, categories, actors, episodes, season = get_pt_gen_info(
            description, raw_data=pt_gen_data)
    except Exception as e:
        print_error(f"解析 PT-Gen 失败: {e}")
        return False



    if not year:
        print_error("未能获取年份信息")
        return False

    print_success(f"标题: {original_title or english_title} ({year})")

    # Handle missing English title
    if not english_title and original_title:
        print_warning("未找到英文名称，尝试生成拼音...")
        english_title = chinese_name_to_pinyin(original_title)
        if english_title:
            print_success(f"拼音名称: {english_title}")

    # Step 3: Get video info
    print_step(3, total_steps, "获取视频信息...")
    is_video_path, video_file = check_path_and_find_video(video_path)
    if is_video_path not in [1, 2]:
        print_error(f"视频路径无效: {video_file}")
        return False

    success, video_info = get_video_info(video_file)
    if not success:
        print_error(f"获取视频信息失败: {video_info}")
        return False

    video_format, video_codec, bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num = video_info[
        :8]
    print_success(f"视频格式: {video_format} {video_codec}")

    # Step 4: Generate file name
    print_step(4, total_steps, "生成文件名...")

    # Use source and team from initial selections
    other_titles_str = ' / '.join(other_names) if other_names else ''
    actors_str = ' / '.join(actors) if actors else ''

    file_name = get_name_from_template(
        english_title, original_title, '', '', year,
        video_format, source, video_codec, bit_depth, hdr_format,
        frame_rate, audio_codec, channels, audio_num, team,
        other_titles_str, '', '', '', categories, actors_str,
        'file_name_movie'
    )

    main_title = get_name_from_template(
        english_title, original_title, '', '', year,
        video_format, source, video_codec, bit_depth, hdr_format,
        frame_rate, audio_codec, channels, audio_num, team,
        other_titles_str, '', '', '', categories, actors_str,
        'main_title_movie'
    )

    print_success(f"主标题: {main_title}")
    print_success(f"文件名: {file_name}")

    # Step 5: Summary
    print_step(5, total_steps, "生成摘要...")

    print(f"\n{Colors.CYAN}{'='*50}{Colors.END}")
    print(f"{Colors.BOLD}处理结果 / Results:{Colors.END}")
    print(f"  标题: {original_title}")
    print(f"  英文: {english_title}")
    print(f"  年份: {year}")
    print(f"  类别: {categories}")
    print(f"  格式: {video_format} {video_codec} {hdr_format}")
    print(f"  文件名: {file_name}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}")

    # Execute additional operations automatically (no interruption)
    print(f"\n{Colors.BOLD}执行后续操作...{Colors.END}")

    # Rename (matching GUI logic exactly)
    do_rename = get_settings('rename_file') == 'True'
    make_dir = get_settings('make_dir') == 'True'
    create_hardlink = get_settings('create_hard_link') == 'True'

    if do_rename:
        print("正在重命名...")
        if is_video_path == 1:  # Single file
            # If make_dir is enabled, move file into a folder first
            if make_dir:
                print("  创建目录并移动文件...")
                move_success, new_file_path = move_file_to_folder(
                    video_file, file_name)
                if move_success:
                    print_success(f"  文件已移动到目录: {new_file_path}")
                    video_file = new_file_path
                    video_path = os.path.dirname(new_file_path)
                    # Now rename the directory (same as GUI logic)
                    print("  对文件夹重新命名...")
                    rename_directory_success, response = rename_folder(
                        video_path, file_name)
                    if rename_directory_success:
                        video_path = response
                        print_success(f"  视频文件夹成功重新命名为：{video_path}")
                        # Re-check and find video file in renamed directory
                        is_video_path, response = check_path_and_find_video(
                            video_path)
                        if is_video_path == 2:
                            video_file = response
                            print_success(f"  成功读取到视频文件：{video_file}")
                        else:
                            print_error(f"  读取视频文件失败：{response}")
                            return False
                    else:
                        print_error(f"  重命名失败：{response}")
                        return False
                else:
                    print_error(f"  移动文件失败: {new_file_path}")
                    return False

                # After folder rename, also rename the file inside (GUI does both)
                print("  开始对文件重新命名...")
                rename_file_success, response = rename_file(
                    video_file, file_name)
                if rename_file_success:
                    video_file = response
                    print_success(f"  视频文件成功重新命名为：{video_file}")
                else:
                    print_error(f"  重命名失败：{response}")
                    return False
            else:
                # Just rename the file without making directory
                success, new_path = rename_file(video_file, file_name)
                if success:
                    new_path = os.path.normpath(new_path)
                    print_success(f"重命名成功: {new_path}")
                    video_file = new_path
                    video_path = os.path.dirname(new_path)
                else:
                    print_error(f"重命名失败: {new_path}")
                    return False

        else:  # Directory (is_video_path == 2)
            # First rename the folder
            print("  对文件夹重新命名...")
            rename_directory_success, response = rename_folder(
                video_path, file_name)
            if rename_directory_success:
                video_path = response
                print_success(f"  视频文件夹成功重新命名为：{video_path}")
                # Re-check and find video file in renamed directory
                is_video_path, response = check_path_and_find_video(video_path)
                if is_video_path == 2:
                    video_file = response
                    print_success(f"  成功读取到视频文件：{video_file}")
                else:
                    print_error(f"  读取视频文件失败：{response}")
                    return False
            else:
                print_error(f"  重命名失败：{response}")
                return False

            # Then rename the file inside the folder (GUI does both)
            print("  开始对文件重新命名...")
            rename_file_success, response = rename_file(video_file, file_name)
            if rename_file_success:
                video_file = response
                print_success(f"  视频文件成功重新命名为：{video_file}")
            else:
                print_error(f"  重命名失败：{response}")
                return False

        print_success("重命名全部成功")

    # Get MediaInfo after renaming (so Complete name shows renamed file)
    print("正在获取 MediaInfo...")
    success, media_info = get_media_info(video_file)
    if success:
        print_success("MediaInfo 获取成功")
    else:
        print_warning(f"MediaInfo 获取失败: {media_info}")
        media_info = ""

    # Create hard link if enabled
    if create_hardlink:
        print("正在创建硬链接...")
        hardlink_success, hardlink_path = create_hard_link(video_path)
        if hardlink_success:
            print_success(f"硬链接创建成功: {hardlink_path}")
        else:
            print_error(f"硬链接创建失败: {hardlink_path}")

    # Screenshots
    screenshot_storage = get_settings('screenshot_storage_path')
    screenshot_num = int(get_settings('screenshot_number') or 4)
    screenshot_threshold = float(get_settings('screenshot_threshold') or 30.0)
    screenshot_start_percentage = float(
        get_settings('screenshot_start_percentage') or 0.10)
    screenshot_end_percentage = float(
        get_settings('screenshot_end_percentage') or 0.90)
    do_get_thumbnail = get_settings('do_get_thumbnail') == 'True'
    thumbnail_rows = int(get_settings('thumbnail_rows') or 3)
    thumbnail_cols = int(get_settings('thumbnail_cols') or 3)
    auto_upload_screenshot = get_settings('auto_upload_screenshot') == 'True'
    delete_screenshot = get_settings('delete_screenshot') == 'True'

    print("正在生成截图...")
    pictures = []
    success, screenshots = get_screenshot(video_file, screenshot_storage, screenshot_num,
                                          screenshot_threshold, screenshot_start_percentage,
                                          screenshot_end_percentage, screenshot_min_interval=0.01)
    if success:
        print_success(f"截图生成成功: {len(screenshots)} 张")
        pictures = screenshots

        # Generate thumbnail if enabled
        if do_get_thumbnail:
            from src.core.screenshot import get_thumbnail
            print("正在生成缩略图...")
            thumbnail_success, thumbnail_path = get_thumbnail(
                video_file, screenshot_storage, thumbnail_rows, thumbnail_cols,
                screenshot_start_percentage, screenshot_end_percentage
            )
            if thumbnail_success:
                print_success(f"缩略图生成成功: {thumbnail_path}")
                # Add thumbnail at the beginning
                pictures.append(thumbnail_path)
            else:
                print_warning(f"缩略图生成失败: {thumbnail_path}")

        # Upload to picture bed if enabled
        if auto_upload_screenshot and pictures:
            picture_bed_api_url = get_settings('picture_bed_api_url')
            picture_bed_api_token = get_settings('picture_bed_api_token')

            print(f"正在上传 {len(pictures)} 张图片到图床...")
            uploaded_urls = []

            for idx, picture_path in enumerate(pictures, 1):
                print(f"  上传第 {idx}/{len(pictures)} 张...")
                upload_success, response = upload_picture(
                    picture_bed_api_url, picture_bed_api_token, picture_path)

                if upload_success:
                    uploaded_urls.append(response)
                    print_success(f"    上传成功")

                    # Delete local screenshot if setting enabled
                    if delete_screenshot:
                        try:
                            os.remove(picture_path)
                            print(f"    本地文件已删除: {picture_path}")
                        except Exception as e:
                            print_warning(f"    删除本地文件失败: {e}")
                else:
                    print_error(f"    上传失败: {response}")
                    # Keep local path if upload fails
                    uploaded_urls.append(picture_path)

            if uploaded_urls:
                print_success(f"图片链接 ({len(uploaded_urls)} 张):")
                for url in uploaded_urls:
                    print(f"  {url}")

                # Append uploaded picture URLs to description if setting enabled
                paste_screenshot_url = get_settings('paste_screenshot_url') == 'True'
                if paste_screenshot_url:
                    for url in uploaded_urls:
                        # Only append if it's a valid BBCode URL (not local path)
                        if url.startswith('[img]'):
                            description += '\n' + url
                    print_success("截图链接已添加到简介")
        else:
            if not auto_upload_screenshot:
                print_success(f"本地截图路径:")
                for pic in pictures:
                    print(f"  {pic}")
    else:
        print_error(f"截图失败: {screenshots}")

    # Torrent
    torrent_storage = get_settings('torrent_storage_path')
    print("正在制作种子...")
    success, torrent_result = make_torrent(video_path, torrent_storage)
    torrent_path = ""
    if success:
        print_success(f"种子制作成功: {torrent_result}")
        torrent_path = torrent_result
    else:
        print_error(f"种子制作失败: {torrent_result}")

    # Generate auto-feed link
    print("\n正在生成 Auto-Feed 链接...")
    category = '电影'
    torrent_url = ""  # Can be filled if torrent is uploaded somewhere

    get_auto_feed_link_success, response = get_auto_feed_link(
        main_title, f"{original_title} / {other_titles_str} | 类型：{categories} | 演员：{actors_str}",
        description, media_info, file_name, team, source, category, torrent_url
    )

    if get_auto_feed_link_success:
        auto_feed_link = response
        print_success("Auto-Feed 链接已生成")

        # Try to copy to clipboard
        clipboard_success = False
        try:
            import pyperclip
            pyperclip.copy(auto_feed_link)
            clipboard_success = True
            print_success("链接已自动复制到剪贴板")
        except Exception:
            # pyperclip not available or no clipboard mechanism (headless Linux)
            # Try platform-specific methods
            try:
                if sys.platform == 'win32':
                    # Windows: use built-in clip command
                    import subprocess
                    process = subprocess.Popen(
                        ['clip'], stdin=subprocess.PIPE, shell=True)
                    process.communicate(auto_feed_link.encode('utf-16le'))
                    clipboard_success = True
                    print_success("链接已自动复制到剪贴板")
                elif sys.platform == 'darwin':
                    # macOS: use pbcopy
                    import subprocess
                    process = subprocess.Popen(
                        ['pbcopy'], stdin=subprocess.PIPE)
                    process.communicate(auto_feed_link.encode('utf-8'))
                    clipboard_success = True
                    print_success("链接已自动复制到剪贴板")
            except Exception:
                pass

        # Save to file as backup in temp folder (avoid git tracking)
        try:
            # Get project root temp folder
            temp_dir = os.path.join(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            link_file = os.path.join(temp_dir, 'auto_feed_link.txt')
            with open(link_file, 'w', encoding='utf-8') as f:
                f.write(auto_feed_link)
            print_success(f"✓ 链接已保存到文件: {link_file}")
        except Exception as e:
            print_warning(f"保存链接文件失败: {e}")

        if not clipboard_success:
            print(f"\n{Colors.BOLD}Auto-Feed 链接:{Colors.END}")
            print(f"{Colors.CYAN}{auto_feed_link}{Colors.END}")
            print(
                f"\n{Colors.YELLOW}提示: 链接已保存到 temp/auto_feed_link.txt 文件{Colors.END}\n")
        else:
            print(f"\n{Colors.YELLOW}提示: 直接 Ctrl+V 粘贴到浏览器即可{Colors.END}\n")
    else:
        print_warning(f"Auto-Feed 链接生成失败: {response}")

    print(f"\n{Colors.GREEN}{'='*50}")
    print(f"  ✓ 处理完成! / Processing Complete!")
    print(f"{'='*50}{Colors.END}\n")

    return True


def process_tv(resource_url, video_path, season, episodes_start):
    """Process a TV series with the one-key workflow."""
    total_steps = 6

    # Collect all user choices FIRST before any API calls
    print(f"\n{Colors.BOLD}请完成以下选择 / Please make your selections:{Colors.END}\n")

    # Get Source and Team selections upfront
    source = select_from_combo_box("来源 Source", "source")
    team = select_from_combo_box("制作组 Team", "team")

    print(f"\n{Colors.GREEN}✓ 所有选择已完成，开始自动处理...{Colors.END}\n")

    # Step 1: Get PT-Gen description
    print_step(1, total_steps, "获取 PT-Gen 信息...")
    pt_gen_api_url = get_settings('pt_gen_api_url')

    success, response = get_pt_gen_description(pt_gen_api_url, resource_url)
    if not success:
        print_warning(f"主接口失败: {response}")

        # Try backup API
        pt_gen_api_url_backup = get_settings('pt_gen_api_url_backup')
        if pt_gen_api_url_backup and pt_gen_api_url_backup != pt_gen_api_url:
            print(f"  尝试备用接口: {pt_gen_api_url_backup}")
            success, response = get_pt_gen_description(
                pt_gen_api_url_backup, resource_url)
            if not success:
                print_error(f"备用接口也失败: {response}")
                return False
            print_success("备用接口获取成功")
        else:
            print_error("未配置备用接口或备用接口与主接口相同")
            return False

    # Response is a tuple (description_text, response_dict)
    if isinstance(response, tuple):
        description = response[0]  # First element is the formatted description
        pt_gen_data = response[1]  # Second element is the full API response
    else:
        description = response
        pt_gen_data = {}

    print_success("PT-Gen 信息获取成功")

    # Process poster in description (download and re-upload if enabled)
    description = process_poster_in_description(description)

    # Step 2: Parse PT-Gen info
    print_step(2, total_steps, "解析 PT-Gen 信息...")
    try:
        original_title, english_title, year, other_names, categories, actors, episodes, pt_gen_season = get_pt_gen_info(
            description, raw_data=pt_gen_data)
    except Exception as e:
        print_error(f"解析 PT-Gen 失败: {e}")
        return False



    if not year:
        print_error("未能获取年份信息")
        return False

    # Validate season
    if pt_gen_season and str(pt_gen_season) != str(season):
        print_warning(f"PT-Gen季数 ({pt_gen_season}) 与输入季数 ({season}) 不符")
        print_warning(f"将使用输入的季数: {season}")

    print_success(
        f"标题: {original_title or english_title} ({year}) S{season:02d}")

    # Handle missing English title
    if not english_title and original_title:
        print_warning("未找到英文名称，尝试生成拼音...")
        english_title = chinese_name_to_pinyin(original_title)
        if english_title:
            print_success(f"拼音名称: {english_title}")

    # Step 3: Get video info and count episodes
    print_step(3, total_steps, "获取视频信息...")
    is_video_path, video_file = check_path_and_find_video(video_path)
    if is_video_path not in [1, 2]:
        print_error(f"视频路径无效: {video_file}")
        return False

    # Count episodes
    episodes_num = 1
    if is_video_path == 2:  # Folder with multiple files
        get_video_files_success, response = get_video_files(video_path)
        if get_video_files_success:
            video_files = response
            episodes_num = len(video_files)
            print_success(f"检测到 {episodes_num} 个视频文件")
        else:
            print_error(f"获取视频文件失败: {response}")
            return False

    # Calculate total episodes info
    if episodes_start == 1:
        total_episodes = f'全{episodes_num}集'
    else:
        if episodes_num == 1:
            total_episodes = f'第{episodes_start}集'
        else:
            total_episodes = f'第{episodes_start}-{episodes_start + episodes_num - 1}集'

    print_success(f"集数信息: {total_episodes}")

    success, video_info = get_video_info(video_file)
    if not success:
        print_error(f"获取视频信息失败: {video_info}")
        return False

    video_format, video_codec, bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num = video_info[
        :8]
    print_success(f"视频格式: {video_format} {video_codec}")

    # Step 4: Generate file name
    print_step(4, total_steps, "生成文件名...")

    # Format season number (pad with zero if needed)
    season_str = f"{season:02d}" if season < 10 else str(season)
    season_number = str(season)  # For template (no padding)

    # Remove season number from english_title (like GUI does)
    english_title = delete_season_number(english_title, season_number)

    # Use source and team from initial selections
    other_titles_str = ' / '.join(other_names) if other_names else ''
    actors_str = ' / '.join(actors) if actors else ''

    file_name = get_name_from_template(
        english_title, original_title, season_str, '{集数}', year,
        video_format, source, video_codec, bit_depth, hdr_format,
        frame_rate, audio_codec, channels, audio_num, team,
        other_titles_str, season_number, total_episodes, '',
        categories, actors_str,
        'file_name_tv'
    )

    main_title = get_name_from_template(
        english_title, original_title, season_str, '', year,
        video_format, source, video_codec, bit_depth, hdr_format,
        frame_rate, audio_codec, channels, audio_num, team,
        other_titles_str, season_number, total_episodes, '',
        categories, actors_str,
        'main_title_tv'
    )

    print_success(f"主标题: {main_title}")
    print_success(f"文件名: {file_name}")

    # Step 5: Summary
    print_step(5, total_steps, "生成摘要...")

    print(f"\n{Colors.CYAN}{'='*50}{Colors.END}")
    print(f"{Colors.BOLD}处理结果 / Results:{Colors.END}")
    print(f"  标题: {original_title}")
    print(f"  英文: {english_title}")
    print(f"  年份: {year}")
    print(f"  季: {season_number} | {total_episodes}")
    print(f"  类别: {categories}")
    print(f"  格式: {video_format} {video_codec} {hdr_format}")
    print(f"  文件名: {file_name}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}")

    # Execute additional operations automatically (no interruption)
    print(f"\n{Colors.BOLD}执行后续操作...{Colors.END}")

    # Rename (matching GUI logic exactly)
    do_rename = get_settings('rename_file') == 'True'
    make_dir = get_settings('make_dir') == 'True'
    create_hardlink = get_settings('create_hard_link') == 'True'

    if do_rename:
        print("正在重命名...")
        if is_video_path == 1:  # Single file
            # If make_dir is enabled, move file into a folder first
            if make_dir:
                print("  创建目录并移动文件...")
                # For folder name, remove episode placeholder
                folder_name = file_name.replace('E{集数}', '').replace('{集数}', '')
                move_success, new_file_path = move_file_to_folder(
                    video_file, folder_name)
                if move_success:
                    print_success(f"  文件已移动到目录: {new_file_path}")
                    video_file = new_file_path
                    video_path = os.path.dirname(new_file_path)
                    # Now rename the directory
                    print("  对文件夹重新命名...")
                    rename_directory_success, response = rename_folder(
                        video_path, folder_name)
                    if rename_directory_success:
                        video_path = response
                        print_success(f"  视频文件夹成功重新命名为：{video_path}")
                        # Re-check and find video file in renamed directory
                        is_video_path, response = check_path_and_find_video(
                            video_path)
                        if is_video_path == 2:
                            video_file = response
                            print_success(f"  成功读取到视频文件：{video_file}")
                        else:
                            print_error(f"  读取视频文件失败：{response}")
                            return False
                    else:
                        print_error(f"  重命名失败：{response}")
                        return False
                else:
                    print_error(f"  移动文件失败: {new_file_path}")
                    return False

                # After folder rename, also rename the file inside
                print("  开始对文件重新命名...")
                # For single file, replace {集数} with starting episode number
                e = str(episodes_start)
                if len(e) == 1:
                    e = f'0{e}'
                single_file_name = file_name.replace('{集数}', e)
                rename_file_success, response = rename_file(
                    video_file, single_file_name)
                if rename_file_success:
                    video_file = response
                    print_success(f"  视频文件成功重新命名为：{video_file}")
                else:
                    print_error(f"  重命名失败：{response}")
                    return False
            else:
                # Just rename the file without making directory
                # For single file, replace {集数} with starting episode number
                e = str(episodes_start)
                if len(e) == 1:
                    e = f'0{e}'
                single_file_name = file_name.replace('{集数}', e)
                success, new_path = rename_file(video_file, single_file_name)
                if success:
                    new_path = os.path.normpath(new_path)
                    print_success(f"重命名成功: {new_path}")
                    video_file = new_path
                    video_path = os.path.dirname(new_path)
                else:
                    print_error(f"重命名失败: {new_path}")
                    return False

        else:  # Directory (is_video_path == 2)
            # Get all video files in the folder
            get_video_files_success, video_files_response = get_video_files(video_path)
            if not get_video_files_success:
                print_error(f"  获取视频文件列表失败：{video_files_response}")
                return False

            video_files_list = video_files_response
            episodes_num = len(video_files_list)
            print(f"  文件夹内检测到 {episodes_num} 个视频文件")

            # First rename all video files with episode numbers (like GUI)
            print("  开始对文件重新命名...")
            i = episodes_start
            for vf in video_files_list:
                # Pad episode number (like GUI logic)
                e = str(i)
                # Pad to match the width of the maximum episode number
                max_ep = episodes_start + episodes_num - 1
                while len(e) < len(str(max_ep)):
                    e = f'0{e}'
                # Ensure at least 2 digits
                if len(e) == 1:
                    e = f'0{e}'

                # Replace {集数} with padded episode number
                episode_file_name = file_name.replace('{集数}', e)
                rename_file_success, response = rename_file(vf, episode_file_name)
                if rename_file_success:
                    print_success(f"    E{e}: {os.path.basename(response)}")
                else:
                    print_error(f"    重命名失败：{response}")
                    return False
                i += 1

            # Then rename the folder (remove episode placeholder from name)
            print("  对文件夹重新命名...")
            folder_name = file_name.replace('E{集数}', '').replace('{集数}', '')
            rename_directory_success, response = rename_folder(video_path, folder_name)
            if rename_directory_success:
                video_path = response
                print_success(f"  视频文件夹成功重新命名为：{video_path}")
                # Re-check and find video file in renamed directory
                is_video_path, response = check_path_and_find_video(video_path)
                if is_video_path == 2:
                    video_file = response
                else:
                    print_error(f"  读取视频文件失败：{response}")
                    return False
            else:
                print_error(f"  重命名失败：{response}")
                return False

        print_success("重命名全部成功")

    # Get MediaInfo after renaming (so Complete name shows renamed file)
    print("正在获取 MediaInfo...")
    success, media_info = get_media_info(video_file)
    if success:
        print_success("MediaInfo 获取成功")
    else:
        print_warning(f"MediaInfo 获取失败: {media_info}")
        media_info = ""

    # Create hard link if enabled
    if create_hardlink:
        print("正在创建硬链接...")
        hardlink_success, hardlink_path = create_hard_link(video_path)
        if hardlink_success:
            print_success(f"硬链接创建成功: {hardlink_path}")
        else:
            print_error(f"硬链接创建失败: {hardlink_path}")

    # Screenshots
    screenshot_storage = get_settings('screenshot_storage_path')
    screenshot_num = int(get_settings('screenshot_number') or 4)
    screenshot_threshold = float(get_settings('screenshot_threshold') or 30.0)
    screenshot_start_percentage = float(
        get_settings('screenshot_start_percentage') or 0.10)
    screenshot_end_percentage = float(
        get_settings('screenshot_end_percentage') or 0.90)
    do_get_thumbnail = get_settings('do_get_thumbnail') == 'True'
    thumbnail_rows = int(get_settings('thumbnail_rows') or 3)
    thumbnail_cols = int(get_settings('thumbnail_cols') or 3)
    auto_upload_screenshot = get_settings('auto_upload_screenshot') == 'True'
    delete_screenshot = get_settings('delete_screenshot') == 'True'

    print("正在生成截图...")
    pictures = []
    success, screenshots = get_screenshot(video_file, screenshot_storage, screenshot_num,
                                          screenshot_threshold, screenshot_start_percentage,
                                          screenshot_end_percentage, screenshot_min_interval=0.01)
    if success:
        print_success(f"截图生成成功: {len(screenshots)} 张")
        pictures = screenshots

        # Generate thumbnail if enabled
        if do_get_thumbnail:
            print("正在生成缩略图...")
            thumbnail_success, thumbnail_path = get_thumbnail(
                video_file, screenshot_storage, thumbnail_rows, thumbnail_cols,
                screenshot_start_percentage, screenshot_end_percentage
            )
            if thumbnail_success:
                print_success(f"缩略图生成成功: {thumbnail_path}")
                pictures.append(thumbnail_path)
            else:
                print_warning(f"缩略图生成失败: {thumbnail_path}")

        # Upload to picture bed if enabled
        if auto_upload_screenshot and pictures:
            picture_bed_api_url = get_settings('picture_bed_api_url')
            picture_bed_api_token = get_settings('picture_bed_api_token')

            print(f"正在上传 {len(pictures)} 张图片到图床...")
            uploaded_urls = []

            for idx, picture_path in enumerate(pictures, 1):
                print(f"  上传第 {idx}/{len(pictures)} 张...")
                upload_success, response = upload_picture(
                    picture_bed_api_url, picture_bed_api_token, picture_path)

                if upload_success:
                    uploaded_urls.append(response)
                    print_success(f"    上传成功")

                    if delete_screenshot:
                        try:
                            os.remove(picture_path)
                            print(f"    本地文件已删除: {picture_path}")
                        except Exception as e:
                            print_warning(f"    删除本地文件失败: {e}")
                else:
                    print_error(f"    上传失败: {response}")
                    uploaded_urls.append(picture_path)

            if uploaded_urls:
                print_success(f"图片链接 ({len(uploaded_urls)} 张):")
                for url in uploaded_urls:
                    print(f"  {url}")

                # Append uploaded picture URLs to description if setting enabled
                paste_screenshot_url = get_settings('paste_screenshot_url') == 'True'
                if paste_screenshot_url:
                    for url in uploaded_urls:
                        # Only append if it's a valid BBCode URL (not local path)
                        if url.startswith('[img]'):
                            description += '\n' + url
                    print_success("截图链接已添加到简介")
        else:
            if not auto_upload_screenshot:
                print_success(f"本地截图路径:")
                for pic in pictures:
                    print(f"  {pic}")
    else:
        print_error(f"截图失败: {screenshots}")

    # Torrent
    torrent_storage = get_settings('torrent_storage_path')
    print("正在制作种子...")
    success, torrent_result = make_torrent(video_path, torrent_storage)
    torrent_path = ""
    if success:
        print_success(f"种子制作成功: {torrent_result}")
        torrent_path = torrent_result
    else:
        print_error(f"种子制作失败: {torrent_result}")

    # Generate auto-feed link
    print("\n正在生成 Auto-Feed 链接...")
    category = '剧集'
    torrent_url = ""  # Can be filled if torrent is uploaded somewhere

    get_auto_feed_link_success, response = get_auto_feed_link(
        main_title, f"{original_title} / {other_titles_str} | 类型：{categories} | 演员：{actors_str}",
        description, media_info, file_name, team, source, category, torrent_url
    )

    if get_auto_feed_link_success:
        auto_feed_link = response
        print_success("Auto-Feed 链接已生成")

        # Try to copy to clipboard
        clipboard_success = False
        try:
            import pyperclip
            pyperclip.copy(auto_feed_link)
            clipboard_success = True
            print_success("链接已自动复制到剪贴板")
        except Exception:
            # pyperclip not available or no clipboard mechanism (headless Linux)
            try:
                if sys.platform == 'win32':
                    import subprocess
                    process = subprocess.Popen(
                        ['clip'], stdin=subprocess.PIPE, shell=True)
                    process.communicate(auto_feed_link.encode('utf-16le'))
                    clipboard_success = True
                    print_success("链接已自动复制到剪贴板")
                elif sys.platform == 'darwin':
                    import subprocess
                    process = subprocess.Popen(
                        ['pbcopy'], stdin=subprocess.PIPE)
                    process.communicate(auto_feed_link.encode('utf-8'))
                    clipboard_success = True
                    print_success("链接已自动复制到剪贴板")
            except Exception:
                pass

        # Save to file as backup
        try:
            temp_dir = os.path.join(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            link_file = os.path.join(temp_dir, 'auto_feed_link.txt')
            with open(link_file, 'w', encoding='utf-8') as f:
                f.write(auto_feed_link)
            print_success(f"链接已保存到文件: {link_file}")
        except Exception as e:
            print_warning(f"保存链接文件失败: {e}")

        if not clipboard_success:
            print(f"\n{Colors.BOLD}Auto-Feed 链接:{Colors.END}")
            print(f"{Colors.CYAN}{auto_feed_link}{Colors.END}")
            print(
                f"\n{Colors.YELLOW}提示: 链接已保存到 temp/auto_feed_link.txt 文件{Colors.END}\n")
        else:
            print(f"\n{Colors.YELLOW}提示: 直接 Ctrl+V 粘贴到浏览器即可{Colors.END}\n")
    else:
        print_warning(f"Auto-Feed 链接生成失败: {response}")

    print(f"\n{Colors.GREEN}{'='*50}")
    print(f"  ✓ 处理完成! / Processing Complete!")
    print(f"{'='*50}{Colors.END}\n")

    return True


def process_playlet(original_title, year, area, categories, language, playlet_source, video_path, season, episodes_start):
    """Process a playlet (short drama) with the one-key workflow."""
    total_steps = 6

    # Collect all user choices FIRST before any processing
    print(f"\n{Colors.BOLD}请完成以下选择 / Please make your selections:{Colors.END}\n")

    # Get Source and Team selections upfront
    source = select_from_combo_box("来源 Source", "source")
    team = select_from_combo_box("制作组 Team", "team")

    print(f"\n{Colors.GREEN}✓ 所有选择已完成，开始自动处理...{Colors.END}\n")

    # Step 1: Generate description (no PT-Gen API for playlets)
    print_step(1, total_steps, "生成简介...")
    description = get_playlet_description(
        original_title, year, area, categories, language, season)
    print_success("简介生成成功")

    # For playlets, we don't have PT-Gen data, so we use manual inputs
    english_title = ""  # Will try to generate from original title
    other_names = []
    actors = []

    # Handle missing English title
    if not english_title and original_title:
        print_warning("生成拼音英文名称...")
        english_title = chinese_name_to_pinyin(original_title)
        if english_title:
            print_success(f"拼音名称: {english_title}")

    print_success(f"标题: {original_title} ({year}) S{season:02d}")

    # Step 2: Get video info and count episodes
    print_step(2, total_steps, "获取视频信息...")
    is_video_path, video_file = check_path_and_find_video(video_path)
    if is_video_path not in [1, 2]:
        print_error(f"视频路径无效: {video_file}")
        return False

    # Count episodes
    episodes_num = 1
    if is_video_path == 2:  # Folder with multiple files
        get_video_files_success, response = get_video_files(video_path)
        if get_video_files_success:
            video_files = response
            episodes_num = len(video_files)
            print_success(f"检测到 {episodes_num} 个视频文件")
        else:
            print_error(f"获取视频文件失败: {response}")
            return False

    # Calculate total episodes info
    if episodes_start == 1:
        total_episodes = f'全{episodes_num}集'
    else:
        if episodes_num == 1:
            total_episodes = f'第{episodes_start}集'
        else:
            total_episodes = f'第{episodes_start}-{episodes_start + episodes_num - 1}集'

    print_success(f"集数信息: {total_episodes}")

    success, video_info = get_video_info(video_file)
    if not success:
        print_error(f"获取视频信息失败: {video_info}")
        return False

    video_format, video_codec, bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num = video_info[
        :8]
    print_success(f"视频格式: {video_format} {video_codec}")

    # Step 3: Generate file name
    print_step(3, total_steps, "生成文件名...")

    # Format season number (pad with zero if needed)
    season_str = f"{season:02d}" if season < 10 else str(season)
    season_number = str(season)  # For template (no padding)

    # Use source and team from initial selections
    other_titles_str = ' / '.join(other_names) if other_names else ''
    actors_str = ' / '.join(actors) if actors else ''

    file_name = get_name_from_template(
        english_title, original_title, season_str, '{集数}', year,
        video_format, source, video_codec, bit_depth, hdr_format,
        frame_rate, audio_codec, channels, audio_num, team,
        other_titles_str, season_number, total_episodes, playlet_source,
        categories, actors_str,
        'file_name_playlet'
    )

    main_title = get_name_from_template(
        english_title, original_title, season_str, '', year,
        video_format, source, video_codec, bit_depth, hdr_format,
        frame_rate, audio_codec, channels, audio_num, team,
        other_titles_str, season_number, total_episodes, playlet_source,
        categories, actors_str,
        'main_title_playlet'
    )

    second_title = get_name_from_template(
        english_title, original_title, season_str, '', year,
        video_format, source, video_codec, bit_depth, hdr_format,
        frame_rate, audio_codec, channels, audio_num, team,
        other_titles_str, season_number, total_episodes, playlet_source,
        categories, actors_str,
        'second_title_playlet'
    )

    print_success(f"主标题: {main_title}")
    print_success(f"副标题: {second_title}")
    print_success(f"文件名: {file_name}")

    # Step 4: Summary
    print_step(4, total_steps, "生成摘要...")

    print(f"\n{Colors.CYAN}{'='*50}{Colors.END}")
    print(f"{Colors.BOLD}处理结果 / Results:{Colors.END}")
    print(f"  标题: {original_title}")
    print(f"  英文: {english_title}")
    print(f"  年份: {year}")
    print(f"  季: {season_number} | {total_episodes}")
    print(f"  产地: {area}")
    print(f"  类别: {categories}")
    print(f"  来源: {playlet_source}")
    print(f"  格式: {video_format} {video_codec} {hdr_format}")
    print(f"  文件名: {file_name}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}")

    # Execute additional operations automatically (no interruption)
    print(f"\n{Colors.BOLD}执行后续操作...{Colors.END}")

    # Step 6: Rename, screenshots, torrent, etc.
    print_step(6, total_steps, "重命名和后续处理...")

    # Rename (matching GUI logic exactly)
    do_rename = get_settings('rename_file') == 'True'
    make_dir = get_settings('make_dir') == 'True'
    create_hardlink = get_settings('create_hard_link') == 'True'

    if do_rename:
        print("正在重命名...")
        if is_video_path == 1:  # Single file
            # If make_dir is enabled, move file into a folder first
            if make_dir:
                print("  创建目录并移动文件...")
                move_success, new_file_path = move_file_to_folder(
                    video_file, file_name)
                if move_success:
                    print_success(f"  文件已移动到目录: {new_file_path}")
                    video_file = new_file_path
                    video_path = os.path.dirname(new_file_path)
                    # Now rename the directory
                    print("  对文件夹重新命名...")
                    rename_directory_success, response = rename_folder(
                        video_path, file_name)
                    if rename_directory_success:
                        video_path = response
                        print_success(f"  视频文件夹成功重新命名为：{video_path}")
                        # Re-check and find video file in renamed directory
                        is_video_path, response = check_path_and_find_video(
                            video_path)
                        if is_video_path == 2:
                            video_file = response
                            print_success(f"  成功读取到视频文件：{video_file}")
                        else:
                            print_error(f"  读取视频文件失败：{response}")
                            return False
                    else:
                        print_error(f"  重命名失败：{response}")
                        return False
                else:
                    print_error(f"  移动文件失败: {new_file_path}")
                    return False

                # After folder rename, also rename the file inside
                print("  开始对文件重新命名...")
                rename_file_success, response = rename_file(
                    video_file, file_name)
                if rename_file_success:
                    video_file = response
                    print_success(f"  视频文件成功重新命名为：{video_file}")
                else:
                    print_error(f"  重命名失败：{response}")
                    return False
            else:
                # Just rename the file without making directory
                success, new_path = rename_file(video_file, file_name)
                if success:
                    new_path = os.path.normpath(new_path)
                    print_success(f"重命名成功: {new_path}")
                    video_file = new_path
                    video_path = os.path.dirname(new_path)
                else:
                    print_error(f"重命名失败: {new_path}")
                    return False

        else:  # Directory (is_video_path == 2)
            # First rename the folder
            print("  对文件夹重新命名...")
            rename_directory_success, response = rename_folder(
                video_path, file_name)
            if rename_directory_success:
                video_path = response
                print_success(f"  视频文件夹成功重新命名为：{video_path}")
                # Re-check and find video file in renamed directory
                is_video_path, response = check_path_and_find_video(video_path)
                if is_video_path == 2:
                    video_file = response
                    print_success(f"  成功读取到视频文件：{video_file}")
                else:
                    print_error(f"  读取视频文件失败：{response}")
                    return False
            else:
                print_error(f"  重命名失败：{response}")
                return False

            # Then rename the file inside the folder
            print("  开始对文件重新命名...")
            rename_file_success, response = rename_file(video_file, file_name)
            if rename_file_success:
                video_file = response
                print_success(f"  视频文件成功重新命名为：{video_file}")
            else:
                print_error(f"  重命名失败：{response}")
                return False

        print_success("重命名全部成功")

    # Get MediaInfo after renaming (so Complete name shows renamed file)
    print("正在获取 MediaInfo...")
    success, media_info = get_media_info(video_file)
    if success:
        print_success("MediaInfo 获取成功")
    else:
        print_warning(f"MediaInfo 获取失败: {media_info}")
        media_info = ""

    # Create hard link if enabled
    if create_hardlink:
        print("正在创建硬链接...")
        hardlink_success, hardlink_path = create_hard_link(video_path)
        if hardlink_success:
            print_success(f"硬链接创建成功: {hardlink_path}")
        else:
            print_error(f"硬链接创建失败: {hardlink_path}")

    # Screenshots
    screenshot_storage = get_settings('screenshot_storage_path')
    screenshot_num = int(get_settings('screenshot_number') or 4)
    screenshot_threshold = float(get_settings('screenshot_threshold') or 30.0)
    screenshot_start_percentage = float(
        get_settings('screenshot_start_percentage') or 0.10)
    screenshot_end_percentage = float(
        get_settings('screenshot_end_percentage') or 0.90)
    do_get_thumbnail = get_settings('do_get_thumbnail') == 'True'
    thumbnail_rows = int(get_settings('thumbnail_rows') or 3)
    thumbnail_cols = int(get_settings('thumbnail_cols') or 3)
    auto_upload_screenshot = get_settings('auto_upload_screenshot') == 'True'
    delete_screenshot = get_settings('delete_screenshot') == 'True'

    print("正在生成截图...")
    pictures = []
    success, screenshots = get_screenshot(video_file, screenshot_storage, screenshot_num,
                                          screenshot_threshold, screenshot_start_percentage,
                                          screenshot_end_percentage, screenshot_min_interval=0.01)
    if success:
        print_success(f"截图生成成功: {len(screenshots)} 张")
        pictures = screenshots

        # Generate thumbnail if enabled
        if do_get_thumbnail:
            print("正在生成缩略图...")
            thumbnail_success, thumbnail_path = get_thumbnail(
                video_file, screenshot_storage, thumbnail_rows, thumbnail_cols,
                screenshot_start_percentage, screenshot_end_percentage
            )
            if thumbnail_success:
                print_success(f"缩略图生成成功: {thumbnail_path}")
                pictures.append(thumbnail_path)
            else:
                print_warning(f"缩略图生成失败: {thumbnail_path}")

        # Upload to picture bed if enabled
        if auto_upload_screenshot and pictures:
            picture_bed_api_url = get_settings('picture_bed_api_url')
            picture_bed_api_token = get_settings('picture_bed_api_token')

            print(f"正在上传 {len(pictures)} 张图片到图床...")
            uploaded_urls = []

            for idx, picture_path in enumerate(pictures, 1):
                print(f"  上传第 {idx}/{len(pictures)} 张...")
                upload_success, response = upload_picture(
                    picture_bed_api_url, picture_bed_api_token, picture_path)

                if upload_success:
                    uploaded_urls.append(response)
                    print_success(f"    上传成功")

                    if delete_screenshot:
                        try:
                            os.remove(picture_path)
                            print(f"    本地文件已删除: {picture_path}")
                        except Exception as e:
                            print_warning(f"    删除本地文件失败: {e}")
                else:
                    print_error(f"    上传失败: {response}")
                    uploaded_urls.append(picture_path)

            if uploaded_urls:
                print_success(f"图片链接 ({len(uploaded_urls)} 张):")
                for url in uploaded_urls:
                    print(f"  {url}")

                # Append uploaded picture URLs to description if setting enabled
                paste_screenshot_url = get_settings('paste_screenshot_url') == 'True'
                if paste_screenshot_url:
                    for url in uploaded_urls:
                        # Only append if it's a valid BBCode URL (not local path)
                        if url.startswith('[img]'):
                            description += '\n' + url
                    print_success("截图链接已添加到简介")
        else:
            if not auto_upload_screenshot:
                print_success(f"本地截图路径:")
                for pic in pictures:
                    print(f"  {pic}")
    else:
        print_error(f"截图失败: {screenshots}")

    # Torrent
    torrent_storage = get_settings('torrent_storage_path')
    print("正在制作种子...")
    success, torrent_result = make_torrent(video_path, torrent_storage)
    torrent_path = ""
    if success:
        print_success(f"种子制作成功: {torrent_result}")
        torrent_path = torrent_result
    else:
        print_error(f"种子制作失败: {torrent_result}")

    # Generate auto-feed link
    print("\n正在生成 Auto-Feed 链接...")
    category = '短剧'
    torrent_url = ""  # Can be filled if torrent is uploaded somewhere

    get_auto_feed_link_success, response = get_auto_feed_link(
        main_title, second_title,
        description, media_info, file_name, team, source, category, torrent_url
    )

    if get_auto_feed_link_success:
        auto_feed_link = response
        print_success("Auto-Feed 链接已生成")

        # Try to copy to clipboard
        clipboard_success = False
        try:
            import pyperclip
            pyperclip.copy(auto_feed_link)
            clipboard_success = True
            print_success("链接已自动复制到剪贴板")
        except Exception:
            # pyperclip not available or no clipboard mechanism (headless Linux)
            try:
                if sys.platform == 'win32':
                    import subprocess
                    process = subprocess.Popen(
                        ['clip'], stdin=subprocess.PIPE, shell=True)
                    process.communicate(auto_feed_link.encode('utf-16le'))
                    clipboard_success = True
                    print_success("链接已自动复制到剪贴板")
                elif sys.platform == 'darwin':
                    import subprocess
                    process = subprocess.Popen(
                        ['pbcopy'], stdin=subprocess.PIPE)
                    process.communicate(auto_feed_link.encode('utf-8'))
                    clipboard_success = True
                    print_success("链接已自动复制到剪贴板")
            except Exception:
                pass

        # Save to file as backup
        try:
            temp_dir = os.path.join(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            link_file = os.path.join(temp_dir, 'auto_feed_link.txt')
            with open(link_file, 'w', encoding='utf-8') as f:
                f.write(auto_feed_link)
            print_success(f"链接已保存到文件: {link_file}")
        except Exception as e:
            print_warning(f"保存链接文件失败: {e}")

        if not clipboard_success:
            print(f"\n{Colors.BOLD}Auto-Feed 链接:{Colors.END}")
            print(f"{Colors.CYAN}{auto_feed_link}{Colors.END}")
            print(
                f"\n{Colors.YELLOW}提示: 链接已保存到 temp/auto_feed_link.txt 文件{Colors.END}\n")
        else:
            print(f"\n{Colors.YELLOW}提示: 直接 Ctrl+V 粘贴到浏览器即可{Colors.END}\n")
    else:
        print_warning(f"Auto-Feed 链接生成失败: {response}")

    print(f"\n{Colors.GREEN}{'='*50}")
    print(f"  ✓ 处理完成! / Processing Complete!")
    print(f"{'='*50}{Colors.END}\n")

    return True


def main():
    """Main entry point for interactive CLI."""
    print_header()
    print_settings_summary()

    # Select content type
    content_type = prompt_media_type()
    if content_type is None:
        print("\n再见 / Goodbye!")
        return 0
    print()

    # Initialize variables
    resource_url = ""
    season = 1
    episodes_start = 1
    # Playlet-specific variables
    original_title = ""
    year = ""
    area = ""
    categories = ""
    language = ""
    playlet_source = ""

    # Get inputs based on content type
    if content_type == 'playlet':
        # Playlet doesn't use PT-Gen API, requires manual inputs
        print(f"{Colors.BOLD}短剧信息输入 / Playlet Information:{Colors.END}")

        original_title = prompt("资源名称 / Title")
        if not original_title:
            print_error("资源名称不能为空")
            return 1

        year = prompt("年份 / Year")
        if not year:
            print_error("年份不能为空")
            return 1

        print("\n产地 / Area:")
        print("  1. 大陆 / Mainland")
        print("  2. 港台 / Hong Kong/Taiwan")
        print("  3. 欧美 / Western")
        print("  4. 日本 / Japan")
        print("  5. 韩国 / Korea")
        area_choice = prompt("选择 / Choice", "1")
        area_map = {'1': '大陆', '2': '港台', '3': '欧美', '4': '日本', '5': '韩国'}
        area = area_map.get(area_choice, '大陆')

        categories = prompt("类别 / Category (如: 爱情 喜剧)", "短剧")

        print("\n语言 / Language:")
        print("  1. 国语 / Mandarin")
        print("  2. 粤语 / Cantonese")
        print("  3. 英语 / English")
        print("  4. 日语 / Japanese")
        print("  5. 韩语 / Korean")
        language_choice = prompt("选择 / Choice", "1")
        language_map = {'1': '国语', '2': '粤语', '3': '英语', '4': '日语', '5': '韩语'}
        language = language_map.get(language_choice, '国语')

        print("\n收费类型 / Playlet Source:")
        print("  1. 网络收费短剧")
        print("  2. 网络免费短剧")
        print("  3. 其他")
        playlet_source_choice = prompt("选择 / Choice", "1")
        playlet_source_map = {'1': '网络收费短剧', '2': '网络免费短剧', '3': ''}
        playlet_source = playlet_source_map.get(
            playlet_source_choice, '网络收费短剧')

        season_input = prompt("季数 / Season", "1")
        try:
            season = int(season_input)
            if season < 0:
                print_error("季数不能为负数")
                return 1
        except ValueError:
            print_error("季数必须是数字")
            return 1

        episodes_start_input = prompt("开始集数 / Start Episode", "1")
        try:
            episodes_start = int(episodes_start_input)
            if episodes_start < 1:
                print_error("开始集数必须大于0")
                return 1
        except ValueError:
            print_error("开始集数必须是数字")
            return 1
        print()
    else:
        # Movie and TV use PT-Gen API
        resource_url = prompt("请输入资源链接 (豆瓣/IMDB URL)")
        if not resource_url:
            print_error("资源链接不能为空")
            return 1
        print()

        # Get TV-specific inputs if TV series selected
        if content_type == 'tv':
            season_input = prompt("请输入季数 / Season", "1")
            try:
                season = int(season_input)
                if season < 0:
                    print_error("季数不能为负数")
                    return 1
            except ValueError:
                print_error("季数必须是数字")
                return 1

            episodes_start_input = prompt("开始集数 / Start Episode", "1")
            try:
                episodes_start = int(episodes_start_input)
                if episodes_start < 1:
                    print_error("开始集数必须大于0")
                    return 1
            except ValueError:
                print_error("开始集数必须是数字")
                return 1
            print()

    # Get video path
    video_path = prompt_path("请输入视频文件或文件夹路径")
    if not video_path:
        print_error("视频路径不能为空")
        return 1

    # Strip surrounding quotes (common when pasting paths on Windows)
    video_path = video_path.strip('"\'')

    # Expand user path (~) to full home directory path
    video_path = os.path.expanduser(video_path)

    # Normalize path separators
    video_path = os.path.normpath(video_path)

    # Check if the original path (potentially with short names) exists first
    original_path = video_path
    path_exists = os.path.exists(original_path)

    # Only attempt expansion if the original path doesn't exist
    # This preserves working short paths and only expands when needed
    if not path_exists:
        # Try to expand short (8.3) paths - realpath() does this on Windows
        # Note: realpath() only works on paths that exist, so this may not help
        try:
            expanded_path = os.path.realpath(video_path)
            if os.path.exists(expanded_path):
                video_path = expanded_path
                path_exists = True
                if '~' in original_path:
                    print(f"  展开路径为: {video_path}")
        except (OSError, ValueError) as e:
            pass  # Keep original path

    # On POSIX systems, dragging a file into the terminal produces shell-escaped
    # paths (e.g. "\ " for spaces, "\," for commas). prompt_toolkit reads those
    # backslashes literally, so the string won't match the real file on disk.
    if not path_exists and sys.platform != 'win32' and '\\' in video_path:
        try:
            unescaped_parts = shlex.split(video_path, posix=True)
            if len(unescaped_parts) == 1:
                unescaped = os.path.normpath(unescaped_parts[0])
                if os.path.exists(unescaped):
                    video_path = unescaped
                    path_exists = True
        except ValueError:
            pass  # Unbalanced quotes etc. — keep original path

    if not path_exists:
        print_error(f"路径不存在: {video_path}")

        # If the original had short names, show that we tried to expand
        if original_path != video_path and '~' in original_path:
            print_warning(f"  原始短路径: {original_path}")
            print_warning(f"  尝试展开后: {video_path}")
            print_warning("  两者都不存在")

        print_warning("\n建议获取正确路径的方法:")
        print_warning("  1. 在文件资源管理器中，按住 Shift 键，右键点击文件")
        print_warning("  2. 选择 '复制为路径' / 'Copy as path'")
        print_warning("  3. 或直接拖拽文件到此终端窗口")

        # Check if this looks like a nested duplicate path issue
        if os.sep in video_path:
            path_parts = video_path.split(os.sep)
            # Look for duplicate folder names
            seen = {}
            for i, part in enumerate(path_parts):
                if part and not part.endswith(':'):
                    # Check if folder name appears multiple times
                    base_name = part.split('.')[0]  # Get name before first dot
                    if base_name in seen:
                        print_warning(f"\n⚠ 检测到重复的文件夹名称: '{base_name}'")
                        print_warning("  这可能是复制路径时出错，请检查实际的文件夹结构")
                        break
                    seen[base_name] = i

        # Show which part of the path doesn't exist (debugging aid)
        parts = video_path.split(os.sep)
        if parts:
            # Handle Windows drive letter properly (e.g., "C:")
            if sys.platform == 'win32' and parts[0].endswith(':'):
                test_path = parts[0] + os.sep
            else:
                test_path = parts[0] if parts[0] else os.sep

            if not os.path.exists(test_path):
                print_warning(f"\n  驱动器或根目录不存在: {test_path}")
            else:
                for part in parts[1:]:
                    if not part:  # Skip empty parts
                        continue
                    test_path = os.path.join(test_path, part)
                    if not os.path.exists(test_path):
                        print_warning(f"\n  第一个不存在的路径段: {test_path}")
                        break
        return 1
    print()

    # Process based on content type
    print(f"{Colors.BOLD}开始处理 / Starting...{Colors.END}\n")

    if content_type == 'movie':
        success = process_movie(resource_url, video_path)
    elif content_type == 'tv':
        success = process_tv(resource_url, video_path, season, episodes_start)
    elif content_type == 'playlet':
        success = process_playlet(original_title, year, area, categories, language,
                                  playlet_source, video_path, season, episodes_start)
    else:
        print_error("未知的内容类型")
        success = False

    return 0 if success else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}操作已取消{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
