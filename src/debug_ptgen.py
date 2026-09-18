"""
Debug tool for PT-Gen API.
Usage: python -m src.debug_ptgen

Enter a Douban/IMDb URL and see:
  1. Raw API response JSON
  2. Generated description text
  3. Parsed metadata (area, category, etc.)
"""
import json
import re
import sys

import pyperclip

from src.core.ptgen import get_pt_gen_description
from src.core.tool import get_settings, get_data_from_pt_gen_description


def separator(title: str = "") -> None:
    width = 80
    if title:
        print(f"\n{'=' * width}")
        print(f"  {title}")
        print(f"{'=' * width}")
    else:
        print(f"\n{'-' * width}")


def main():
    pt_gen_api_url = get_settings("pt_gen_api_url")
    print(f"PT-Gen API URL: {pt_gen_api_url}")
    if not pt_gen_api_url:
        print("Error: pt_gen_api_url is not configured in static/settings.json")
        sys.exit(1)

    while True:
        separator()
        url = input("Enter Douban/IMDb URL (or 'q' to quit): ").strip()
        if url.lower() in ('q', 'quit', 'exit'):
            print("Bye!")
            break
        if not url:
            continue

        print(f"\nFetching data for: {url}")
        print("Please wait...")

        success, result = get_pt_gen_description(pt_gen_api_url, url)

        if not success:
            separator("ERROR")
            print(result)
            continue

        format_data, raw_data = result

        # ── Section 1: Raw API Response ──
        separator("1. RAW API RESPONSE (JSON)")
        pretty_json = json.dumps(raw_data, indent=2, ensure_ascii=False)
        print(pretty_json)

        # ── Section 2: Generated Description ──
        separator("2. GENERATED DESCRIPTION (format_data)")
        print(format_data)

        # ── Section 3: Parsed Metadata ──
        separator("3. PARSED METADATA")
        (imdb_url, douban_url, category, area,
         video_format, audio_codec, video_codec, medium) = \
            get_data_from_pt_gen_description(
                main_title="",  # no file title in debug mode
                description=format_data,
                media_info="",
                source="",
                category=""
            )
        metadata = {
            "IMDb URL": imdb_url,
            "Douban URL": douban_url,
            "Category (类型)": category,
            "Area (地区)": area,
            "Video Format": video_format,
            "Audio Codec": audio_codec,
            "Video Codec": video_codec,
            "Medium": medium,
        }
        for k, v in metadata.items():
            print(f"  {k:20s}: {v or '(empty)'}")

        # ── Section 4: Key fields from raw data ──
        separator("4. KEY FIELDS FROM RAW DATA")
        key_fields = [
            "chinese_title", "foreign_title", "year", "category",
            "region", "genre", "language", "director", "writer",
            "cast", "episodes", "duration", "imdb_rating", "imdb_id",
            "douban_rating", "douban_id", "poster", "introduction",
        ]
        for field in key_fields:
            val = raw_data.get(field)
            if val is not None:
                # Truncate long lists/strings for readability
                val_str = json.dumps(val, ensure_ascii=False) if isinstance(val, (list, dict)) else str(val)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                print(f"  {field:20s}: {val_str}")

        # ── Section 5: get_pt_gen_info comparison ──
        separator("5. GET_PT_GEN_INFO RESULTS (with raw_data)")
        from src.core.rename import get_pt_gen_info  # noqa: E402
        original_title, english_title, year, other_titles, categories, actors, episodes, season = \
            get_pt_gen_info(format_data, raw_data=raw_data)
        info_results = {
            "Original Title (中文)": original_title,
            "English Title (外文)": english_title,
            "Year": year,
            "Other Titles": ' / '.join(other_titles) if isinstance(other_titles, list) else other_titles,
            "Categories": categories,
            "Actors": ' / '.join(actors) if isinstance(actors, list) else actors,
            "Episodes": episodes,
            "Season": season,
        }
        for k, v in info_results.items():
            print(f"  {k:25s}: {v or '(empty)'}")

        separator()
        print("\nCompare with regex-only (no raw_data):")
        orig2, eng2, year2, other2, cat2, act2, ep2, s2 = get_pt_gen_info(format_data)
        if orig2 != original_title:
            print(f"  Original Title DIFFERS: regex='{orig2}' vs raw='{original_title}'")
        if eng2 != english_title:
            print(f"  English Title DIFFERS:  regex='{eng2}' vs raw='{english_title}'")
        if year2 != year:
            print(f"  Year DIFFERS:           regex='{year2}' vs raw='{year}'")
        if cat2 != categories:
            print(f"  Categories DIFFERS:     regex='{cat2}' vs raw='{categories}'")
        if act2 != actors:
            print(f"  Actors DIFFERS:         regex='{act2}' vs raw='{actors}'")
        print("  (No differences shown = both methods agree)")

        # ── Section 6: Torrent file name and template names ──
        separator("6. TORRENT FILE NAME (种子名称)")
        from src.core.rename import get_name_from_template  # noqa: E402

        # Prepare template arguments from parsed info
        # NOTE: Mirror the production rename pipeline (src/api/startapi.py and
        # src/main_cli.py): pass `season` as a zero-padded number string (no
        # 'S' prefix — the template literal already contains 'S{season}'),
        # and pass `episode` as a number string or '{集数}' placeholder
        # (the template literal already contains 'E{episode}').
        other_titles_str = ' / '.join(other_titles) if isinstance(other_titles, list) else (other_titles or '')
        actors_str = ' / '.join(actors) if isinstance(actors, list) else (actors or '')
        # Default to season 1 if PT-Gen didn't provide one (matches production
        # CLI default and the GUI's season input default).
        season_int = season if season else 1
        season_str = str(season_int).zfill(2)
        season_number = str(season_int)
        episodes_str = str(episodes) if episodes else ''

        def make_name(template_key, episode_val=''):
            template_value = get_settings(template_key)
            if not template_value:
                return None
            return get_name_from_template(
                english_title=english_title or '',
                original_title=original_title or '',
                season=season_str,
                episode=episode_val,
                year=str(year) if year else '',
                video_format='',
                source='',
                video_codec='',
                bit_depth='',
                hdr_format='',
                frame_rate='',
                audio_codec='',
                channels='',
                audio_num='',
                team='',
                other_titles=other_titles_str,
                season_number=season_number,
                total_episodes=f'全{episodes_str}集' if episodes_str else '',
                playlet_source='',
                categories=categories or '',
                actors=actors_str,
                template=template_key,
            )

        # ── Torrent file name (种子名称) ──
        movie_file_name = make_name('file_name_movie')
        tv_file_name = make_name('file_name_tv', '01')
        print()
        if movie_file_name:
            torrent_name_movie = movie_file_name + '.torrent'
            print(f"  🎬 Movie torrent:  {torrent_name_movie}")
        if tv_file_name:
            torrent_name_tv = tv_file_name + '.torrent'
            print(f"  📺 TV torrent:     {torrent_name_tv}")
        print()

        # ── All template names ──
        separator("7. ALL TEMPLATE NAMES")
        templates = [
            ("main_title_movie",    "Movie Main Title"),
            ("second_title_movie",  "Movie Second Title"),
            ("file_name_movie",     "Movie File Name"),
            ("main_title_tv",       "TV Main Title"),
            ("second_title_tv",     "TV Second Title"),
            ("file_name_tv",        "TV File Name"),
        ]

        for template_key, label in templates:
            try:
                name = make_name(template_key, '01')
                if name is None:
                    continue
                print(f"  {label:25s}: {name}")
            except Exception as e:
                print(f"  {label:25s}: (error: {e})")

        # ── Copy description to clipboard ──
        separator()
        try:
            pyperclip.copy(format_data)
            print("✅ Description copied to clipboard!")
        except Exception:
            print("(Could not copy to clipboard)")


if __name__ == "__main__":
    main()
