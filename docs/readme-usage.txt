使用前务必请先看设置！！！

具体的软件功能、界面和使用方法请见Wiki：https://github.com/bjdbjd/publish-helper/wiki/Publish-Helper-Wiki

目前支持的免费公共图床：freeimage(https://freeimage.host/) imgbb(https://imgbb.com/) imagehub(https://www.imagehub.cc/) pixhost(https://pixhost.to/)

目前支持的商业公共图床：薄荷图床(bohe)(https://zixiaoyun.com/)

目前支持的开源图床架构：兰空图床(lsky-pro)(https://github.com/lsky-org/lsky-pro) chevereto(https://github.com/rodber/chevereto-free)

图床的API地址和令牌请去图床主页获取，其他图床如需要单独适配请提Issues，前提是图床支持API上传！

如果您发现自动命名时视频、音频的编码格式没有正确识别，请参考格式修改static/abbreviation.json：

    {
        "min_widths": {
            "9600": "8640p",
            "4608": "4320p",
            "3200": "2160p",
            "2240": "1440p",
            "1600": "1080p",
            "900": "720p",
            "533": "480p"
        },

        "SMPTE ST 2094 App 4, Version 1, HDR10+ Profile B compatible" : "HDR10+",
        "SMPTE ST 2086, HDR10 compatible": "HDR10",

        "Dolby Digital Plus with Dolby Atmos": "Atmos DDP",
        "Dolby TrueHD with Dolby Atmos": "Atmos TrueHD",
        "DTS-HD Master Audio": "DTS-HD MA",

        "L R C LFE Ls Rs Lb Rb": "7.1",
        "L R C LFE Ls Rs": "5.1",
        "L R": "2.0"

        "1 920 pixels": "1080p",
        "1 280 pixels": "720p",
        "640 pixels": "480p",

        "HEVC": "HEVC",
        "AVC": "AVC",
        "AV1": "AV1",

        "没有正确识别所产生的信息": "你想要的缩略信息",
        "无需识别的信息": ""（留空）
    }

如需修改资源来源、小组名称或短剧来源默认值，请修改static/combo-box-data.json：

{
    "team": [
        "AGSVWEB",
        "AGSVMUS",
        "AGSVPT",
        "GodDramas",
        "CatEDU",
        "Pack",
        ""
    ],
    "source": [
        "WEB-DL",
        "Remux",
        "Blu-ray",
        "UHD Blu-ray",
        "Blu-ray Remux",
        "UHD Blu-ray Remux",
        "HDTV",
        "DVD",
        ""
    ],
    "playlet-source": [
        "网络收费短剧",
        "网络免费短剧",
        "抖音短剧",
        "快手短剧",
        "腾讯短剧",
        ""
    ]
}

软件获取地址：

https://github.com/bjdbjd/publish-helper/releases

https://gitee.com/bjdbjd/publish-helper/releases

更新时只需要保留static文件夹即可将配置完美迁移。

如果出现错误，可能是配置文件结构有变化，请使用最新的static文件。

如有帮助到您，请给项目点亮Star，并推广给有需要的朋友，十分感谢！

Powered by Python 3.10

Created by BJD