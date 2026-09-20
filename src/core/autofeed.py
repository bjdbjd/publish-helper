# 感谢明日大佬、N佬做出的贡献！！！ID：tomorrow505、Exception
from urllib.parse import quote

from src.core.ptgen import get_data_from_pt_gen_description
from src.core.settings_tool import get_settings
from src.core.text import base64encoding


def get_auto_feed_link(main_title, second_title, description, media_info, file_name, team, source, category,
                       torrent_url):
    auto_feed_link = str(get_settings('auto_feed_link'))
    torrent_name = f'{file_name}.torrent'  # 种子名称
    print('变量初始化完成')
    name = main_title
    small_descr = second_title
    descr = description
    url, dburl, category, source_sel, standard_sel, audiocodec_sel, codec_sel, medium_sel = get_data_from_pt_gen_description(
        main_title, description, media_info, source, category)

    # auto_feed_link = auto_feed_link.replace('{主标题}', name)                # 旧版本的auto_feed可以直接使用原名称
    # auto_feed_link = auto_feed_link.replace('{副标题}', small_descr)
    # auto_feed_link = auto_feed_link.replace('{IMDB}', url)
    # auto_feed_link = auto_feed_link.replace('{豆瓣}', dburl)
    # auto_feed_link = auto_feed_link.replace('{简介}', descr)
    # auto_feed_link = auto_feed_link.replace('{MediaInfo}', media_info)
    # auto_feed_link = auto_feed_link.replace('{种子名称}', torrent_name)
    # auto_feed_link = auto_feed_link.replace('{类型}', category)
    # auto_feed_link = auto_feed_link.replace('{地区}', source_sel)
    # auto_feed_link = auto_feed_link.replace('{分辨率}', standard_sel)
    # auto_feed_link = auto_feed_link.replace('{音频编码}', audiocodec_sel)
    # auto_feed_link = auto_feed_link.replace('{视频编码}', codec_sel)
    # auto_feed_link = auto_feed_link.replace('{媒介}', medium_sel)
    # auto_feed_link = auto_feed_link.replace('{小组}', team)
    # auto_feed_link = auto_feed_link.replace('{种子链接}', torrent_url)
    # auto_feed_link = auto_feed_link.replace('%', '%25')
    # auto_feed_link = auto_feed_link.replace('　', '%E3%80%80')
    # auto_feed_link = auto_feed_link.replace(' ', '%20')
    # auto_feed_link = auto_feed_link.replace('\n', '%0A')
    auto_feed_link = auto_feed_link.replace('{主标题}', quote(name))  # 新版本的auto_feed需要转为base64
    auto_feed_link = auto_feed_link.replace('{副标题}', quote(small_descr))
    auto_feed_link = auto_feed_link.replace('{IMDB}', quote(url))
    auto_feed_link = auto_feed_link.replace('{豆瓣}', quote(dburl))
    auto_feed_link = auto_feed_link.replace('{简介}', quote(descr))
    auto_feed_link = auto_feed_link.replace('{MediaInfo}', quote(media_info))
    auto_feed_link = auto_feed_link.replace('{种子名称}', quote(torrent_name))
    auto_feed_link = auto_feed_link.replace('{类型}', quote(category))
    auto_feed_link = auto_feed_link.replace('{地区}', quote(source_sel))
    auto_feed_link = auto_feed_link.replace('{分辨率}', quote(standard_sel))
    auto_feed_link = auto_feed_link.replace('{音频编码}', quote(audiocodec_sel))
    auto_feed_link = auto_feed_link.replace('{视频编码}', quote(codec_sel))
    auto_feed_link = auto_feed_link.replace('{媒介}', quote(medium_sel))
    auto_feed_link = auto_feed_link.replace('{小组}', quote(team))
    auto_feed_link = auto_feed_link.replace('{种子链接}', quote(torrent_url))
    # auto_feed_link = auto_feed_link.replace('%', '%25')
    # auto_feed_link = auto_feed_link.replace('　', '%E3%80%80')
    # auto_feed_link = auto_feed_link.replace(' ', '%20')
    # auto_feed_link = auto_feed_link.replace('\n', '%0A')

    # 解决auto_feed的历史遗留问题
    auto_feed_link.replace('#seperator#', '#separator#')

    if '#separator#' in auto_feed_link:
        string_to_encode = auto_feed_link.split('#separator#')[-1]
        string_encoded = base64encoding(string_to_encode)
        auto_feed_link = auto_feed_link.replace(string_to_encode, '') + string_encoded
        print('获取到auto_feed_link：' + auto_feed_link)
        return True, auto_feed_link
    else:
        return False, '您设置的auto_feed_link不符合规则'

# 'https://example.com/upload.php#seperator#name#linkstr#{主标题}#linkstr#small_descr#linkstr#{副标题}#linkstr#url
# #linkstr#{IMDB}#linkstr#dburl#linkstr{豆瓣}#linkstr#descr#linkstr#{简介}[quote]{MediaInfo}[/quote]#linkstr#log_info
# #linkstr##linkstr#tracklist#linkstr##linkstr#music_type#linkstr##linkstr#music_media#linkstr##linkstr#edition_info
# #linkstr##linkstr#music_name#linkstr##linkstr#music_author#linkstr##linkstr#animate_info#linkstr##linkstr#anidb
# #linkstr##linkstr#torrentName#linkstr##linkstr#images#linkstr##linkstr#torrent_name#linkstr#{种子名称}#linkstr#torrent_url
# #linkstr##linkstr#type#linkstr#{类型}#linkstr#source_sel#linkstr#{地区}#linkstr#standard_sel#linkstr#{分辨率}#linkstr
# #audiocodec_sel#linkstr#{音频编码}#linkstr#codec_sel#linkstr#{视频编码}#linkstr#medium_sel#linkstr#{媒介}#linkstr
# #origin_site#linkstr#{小组}#linkstr#origin_url#linkstr##linkstr#golden_torrent#linkstr#false#linkstr#mediainfo_cmct#linkstr#
# #linkstr#imgs_cmct#linkstr##linkstr#full_mediainfo#linkstr##linkstr#subtitles#linkstr##linkstr#youtube_url#linkstr#
# #linkstr#ptp_poster#linkstr##linkstr#comparisons#linkstr##linkstr#version_info#linkstr##linkstr#multi_mediainfo
# #linkstr##linkstr#labels#linkstr#100'
