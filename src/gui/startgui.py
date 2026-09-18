import os
import re
import sys
import tempfile
import time
import webbrowser

import pyperclip
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QApplication, QDialog, QInputDialog, QMessageBox, QWidget, QLineEdit

from src.api.startapi import start_api
from src.core.autofeed import get_auto_feed_link
from src.core.mediainfo import get_media_info
from src.core.picturebed import upload_picture
from src.core.ptgen import get_pt_gen_description
from src.core.rename import get_pt_gen_info, get_video_info, get_name_from_template, rename_file, rename_folder, \
    move_file_to_folder, create_hard_link
from src.core.screenshot import get_screenshot, get_thumbnail
from src.core.tool import update_settings, get_settings, check_path_and_find_video, make_torrent, \
    chinese_name_to_pinyin, \
    get_video_files, is_filename_too_long, get_playlet_description, delete_season_number, \
    get_combo_box_data, validate_and_convert_to_int
from src.gui.ui.mainwindow import Ui_Mainwindow
from src.gui.ui.settings import Ui_Settings
from src.gui.ui.toast import show_toast
from src.gui.ui_tools import get_video_file_path, get_folder_path, get_picture_file_path

get_name_movie_success = False
get_name_movie_failure_number = 0
get_name_tv_success = False
get_name_tv_failure_number = 0


def start_gui():
    gui = QApplication(sys.argv)
    my_mainwindow = mainwindow()
    my_ico = QIcon('static/ph-bjd.ico')
    my_mainwindow.setWindowIcon(my_ico)
    my_mainwindow.show()
    sys.exit(gui.exec())


def git_clicked():
    webbrowser.open('https://github.com/bjdbjd/publish-helper')


class mainwindow(QMainWindow, Ui_Mainwindow):
    def __init__(self):
        super().__init__()

        self.my_settings = None
        self.setupUi(self)  # 设置界面

        # 全局变量
        self.get_pt_gen_success = False
        self.path_movie = ""
        self.path_tv = ""

        # 初始化线程
        self.get_pt_gen_thread = None
        self.get_pt_gen_backup_thread = None
        self.get_pt_gen_for_name_thread = None
        self.get_pt_gen_for_name_backup_thread = None
        self.upload_picture_thread0 = None
        self.upload_picture_thread1 = None
        self.upload_picture_thread2 = None
        self.upload_picture_thread3 = None
        self.upload_picture_thread4 = None
        self.upload_picture_thread5 = None
        self.upload_cover_thread = None
        self.make_torrent_thread = None
        self.api_thread = None
        self.wait_for_rename_thread = None

        # 初始化
        self.videoPathMovie.setDragEnabled(True)
        self.descriptionBrowserMovie.setText('')
        self.pictureUrlBrowserMovie.setText('')
        self.mediainfoBrowserMovie.setText('')
        self.debugBrowserMovie.setText('')
        self.initialize_team_combobox()
        self.initialize_source_combobox()
        self.initialize_playlet_source_combobox()
        self.initialize_season_box()
        self.torrent_url = ''

        # 绑定点击信号和槽函数
        # Movie
        self.actionsettings.triggered.connect(self.settings_clicked)
        self.actiongit.triggered.connect(git_clicked)
        self.getPtGenButtonMovie.clicked.connect(self.get_pt_gen_button_movie_clicked)
        self.getPictureButtonMovie.clicked.connect(self.get_picture_button_movie_clicked)
        self.selectVideoButtonMovie.clicked.connect(self.select_video_button_movie_clicked)
        self.selectVideoFolderButtonMovie.clicked.connect(self.select_video_folder_button_movie_clicked)
        self.getMediaInfoButtonMovie.clicked.connect(self.get_media_info_button_movie_clicked)
        self.getNameButtonMovie.clicked.connect(self.get_name_button_movie_clicked)
        self.makeTorrentButtonMovie.clicked.connect(self.make_torrent_button_movie_clicked)
        self.startButtonMovie.clicked.connect(self.start_button_movie_clicked)
        self.autoFeedButtonMovie.clicked.connect(self.auto_feed_button_movie_clicked)

        # TV
        self.actionsettings.triggered.connect(self.settings_clicked)
        self.getPtGenButtonTV.clicked.connect(self.get_pt_gen_button_tv_clicked)
        self.getPictureButtonTV.clicked.connect(self.get_picture_button_tv_clicked)
        self.selectVideoFolderButtonTV.clicked.connect(self.select_video_folder_button_tv_clicked)
        self.getMediaInfoButtonTV.clicked.connect(self.get_media_info_button_tv_clicked)
        self.getNameButtonTV.clicked.connect(self.get_name_button_tv_clicked)
        self.makeTorrentButtonTV.clicked.connect(self.make_torrent_button_tv_clicked)
        self.startButtonTV.clicked.connect(self.start_button_tv_clicked)
        self.autoFeedButtonTV.clicked.connect(self.auto_feed_button_tv_clicked)

        # Playlet
        self.getDescriptionButtonPlaylet.clicked.connect(self.get_description_playlet_clicked)
        self.getPictureButtonPlaylet.clicked.connect(self.get_picture_button_playlet_clicked)
        self.uploadCoverButtonPlaylet.clicked.connect(self.upload_cover_button_playlet_clicked)
        self.selectVideoFolderButtonPlaylet.clicked.connect(self.select_video_folder_button_playlet_clicked)
        self.selectCoverFolderButtonPlaylet.clicked.connect(self.select_cover_folder_button_playlet_clicked)
        self.getMediaInfoButtonPlaylet.clicked.connect(self.get_media_info_button_playlet_clicked)
        self.getNameButtonPlaylet.clicked.connect(self.get_name_button_playlet_clicked)
        self.makeTorrentButtonPlaylet.clicked.connect(self.make_torrent_button_playlet_clicked)
        self.startButtonPlaylet.clicked.connect(self.start_button_playlet_clicked)
        self.autoFeedButtonPlaylet.clicked.connect(self.auto_feed_button_playlet_clicked)

        # 初始化成功
        self.debugBrowserMovie.append(
            '程序初始化成功，使用前请查看设置中的说明！制作不易，如有帮助请帮忙点亮仓库的Star！\n作者：BJD 仓库地址：https://github.com/bjdbjd/publish-helper')

        if get_settings('enable_api'):
            self.run_api_thread()

    def initialize_team_combobox(self):
        get_data_success, data = get_combo_box_data('team')
        if get_data_success:
            for name in data:
                self.teamMovie.addItem(name)
                self.teamTV.addItem(name)
                self.teamPlaylet.addItem(name)
        else:
            self.debugBrowserMovie.append(f'获取制作组信息出错：{data[0]}')
            self.debugBrowserTV.append(f'获取制作组信息出错：{data[0]}')
            self.debugBrowserPlaylet.append(f'获取制作组信息出错：{data[0]}')

    def initialize_source_combobox(self):
        get_data_success, data = get_combo_box_data('source')
        if get_data_success:
            for name in data:
                self.sourceMovie.addItem(name)
                self.sourceTV.addItem(name)
                self.sourcePlaylet.addItem(name)
        else:
            self.debugBrowserMovie.append(f'获取资源来源信息出错：{data[0]}')
            self.debugBrowserTV.append(f'获取资源来源信息出错：{data[0]}')
            self.debugBrowserPlaylet.append(f'获取资源来源信息出错：{data[0]}')

    def initialize_playlet_source_combobox(self):
        get_data_success, data = get_combo_box_data('playlet-source')
        if get_data_success:
            for name in data:
                self.playletSource.addItem(name)
        else:
            self.debugBrowserPlaylet.append(f'获取短剧来源信息出错：{data[0]}')

    def initialize_season_box(self):
        self.seasonBoxTV.setValue(1)
        self.seasonBoxPlaylet.setValue(1)

    def settings_clicked(self):  # click对应的槽函数
        self.my_settings = settings()
        self.my_settings.getSettings()
        my_ico = QIcon('static/ph-bjd.ico')
        self.my_settings.setWindowIcon(my_ico)
        self.my_settings.show()  # 加上self避免页面一闪而过

    def run_api_thread(self):
        self.debugBrowserMovie.append('您选择启用API功能，正在尝试启动api_thread')
        self.api_thread = apiThread()
        self.api_thread.result_signal.connect(self.handle_run_api_result)  # 连接信号
        self.api_thread.start()  # 启动线程
        self.debugBrowserMovie.append(f'api_thread启动成功，监听端口：{str(get_settings("api_port"))}')

    def handle_run_api_result(self, response):
        self.debugBrowserMovie.append(response)

    # 以下是Movie页面的代码

    def start_button_movie_clicked(self):
        self.get_name_button_movie_clicked()

        print(f'重命名启动成功')
        self.wait_for_rename_thread = WaitForRenameThread(True)
        self.wait_for_rename_thread.result_signal.connect(self.handle_process_after_rename_movie)  # 连接信号
        self.wait_for_rename_thread.start()  # 启动线程
        print('重命名启动成功，等待重命名完成后将自动进行其他操作...')
        self.debugBrowserMovie.append('重命名启动成功，等待重命名完成后将自动进行其他操作...')

    def handle_process_after_rename_movie(self, rename_success):
        if rename_success:
            print('重命名成功，开始进行后续操作')
            self.debugBrowserMovie.append('重命名成功，开始进行后续操作')

            self.videoPathMovie.setText(self.path_movie)
            QApplication.processEvents()  # 处理所有挂起的事件，更新页面
            self.get_media_info_button_movie_clicked()
            QApplication.processEvents()  # 处理事件
            self.get_picture_button_movie_clicked()
            QApplication.processEvents()  # 处理事件
            self.make_torrent_button_movie_clicked()
            QApplication.processEvents()  # 处理事件
        else:
            print('重命名失败，一键启动已终止')
            self.debugBrowserMovie.append('重命名失败，一键启动已终止')
            show_toast(self, '重命名失败，一键启动已终止', 'error', 6000)

    def auto_feed_button_movie_clicked(self):
        main_title, second_title, description, media_info, file_name, team, source = '', '', '', '', '', '', ''
        main_title += self.mainTitleBrowserMovie.toPlainText()
        second_title += self.secondTitleBrowserMovie.toPlainText()
        description += self.descriptionBrowserMovie.toPlainText()
        media_info += self.mediainfoBrowserMovie.toPlainText()
        file_name += self.fileNameBrowserMovie.toPlainText()
        team += self.teamMovie.currentText()
        source += self.sourceMovie.currentText()
        category = '电影'
        print('获取到文本框的数据')
        get_auto_feed_link_success, response = get_auto_feed_link(main_title, second_title, description, media_info,
                                                                  file_name, team, source, category, self.torrent_url)
        if get_auto_feed_link_success:
            auto_feed_link = response
            self.debugBrowserMovie.append(f'auto_feed_link: {auto_feed_link}')
            pyperclip.copy(auto_feed_link)
            self.debugBrowserMovie.append('auto_feed链接已经复制到剪切板，请粘贴到浏览器访问')
            try:
                if get_settings('open_auto_feed_link'):
                    # 创建临时HTML文件
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w') as temp:
                        temp.write(
                            f'<html><body><a href="{auto_feed_link}" id="link">Link</a><script>document.getElementById("link").click();</script></body></html>')
                        temp_html_path = temp.name

                    # 打开临时HTML文件
                    webbrowser.open(f'file://{temp_html_path}')
            except Exception as e:
                self.debugBrowserMovie.append(f'自动打开链接失败，请手动粘贴到浏览器访问：{e}')
        else:
            self.debugBrowserMovie.append(f'创建auto_feed_link失败：{response}')

    def get_pt_gen_button_movie_clicked(self):
        self.get_pt_gen_success = False
        self.descriptionBrowserMovie.setText('')
        pt_gen_api_url = get_settings('pt_gen_api_url')
        pt_gen_api_url_backup = get_settings('pt_gen_api_url_backup')
        resource_url = self.resourceUrlMovie.text()

        if resource_url == '':
            self.debugBrowserMovie.append('请输入输入豆瓣号、Imdb号、豆瓣、IMDb等资源链接')
            return
        if pt_gen_api_url == '':
            self.debugBrowserMovie.append('请在设置中输入PT-Gen链接')
            return
        print(f'尝试启动pt_gen_thread，您选择的PT-Gen接口是：{pt_gen_api_url}')
        self.debugBrowserMovie.append(f'尝试启动pt_gen_thread，您选择的PT-Gen接口是：{pt_gen_api_url}')
        self.get_pt_gen_thread = GetPtGenThread(pt_gen_api_url, resource_url)
        self.get_pt_gen_thread.result_signal.connect(self.handle_get_pt_gen_movie_result)  # 连接信号
        self.get_pt_gen_thread.start()  # 启动线程
        print('启动pt_gen_thread成功，请耐心等待Api返回结果并分析...')
        self.debugBrowserMovie.append('启动pt_gen_thread成功，请耐心等待Api返回结果并分析...')

        print(f'尝试启动备用pt_gen_thread，您选择的备用PT-Gen接口是：{pt_gen_api_url_backup}')
        self.debugBrowserMovie.append(f'尝试启动备用pt_gen_thread，您选择的备用PT-Gen接口是：{pt_gen_api_url_backup}')
        self.get_pt_gen_backup_thread = GetPtGenThread(pt_gen_api_url_backup, resource_url)
        self.get_pt_gen_backup_thread.result_signal.connect(self.handle_get_pt_gen_movie_result)  # 连接信号
        self.get_pt_gen_backup_thread.start()  # 启动线程
        print('启动备用pt_gen_thread成功，请耐心等待Api返回结果并分析...')
        self.debugBrowserMovie.append('启动备用pt_gen_thread成功，请耐心等待Api返回结果并分析...')

    def handle_get_pt_gen_movie_result(self, get_success, response, raw_data_json=''):
        if self.get_pt_gen_success:
            print("主线程已经成功获取到简介，备用线程关闭")
            return
        if get_success:
            description = response
            if description:
                print(description)
                self.get_pt_gen_success = True
                
                # Process poster if auto download and upload is enabled
                description = self._process_poster_in_description(description)
                
                self.descriptionBrowserMovie.setText(description)
                self.debugBrowserMovie.append('成功获取PT-Gen信息')
            else:
                self.debugBrowserMovie.append('获取PT-Gen信息失败，返回的结果为空')
        else:
            self.debugBrowserMovie.append(f'未成功获取到任何PT-Gen信息{response}')

    def _process_poster_in_description(self, description):
        """Process poster URLs in description if auto download/upload is enabled."""
        try:
            auto_download_upload_poster = bool(get_settings('auto_download_upload_poster'))
            if not auto_download_upload_poster:
                return description
            
            # Extract poster URL from [img]...[/img] tag
            import re
            img_pattern = r'\[img\](https?://[^\]]+)\[/img\]'
            match = re.search(img_pattern, description)
            
            if not match:
                print('No [img] tag found in description')
                return description
            
            original_poster_url = match.group(1)
            print(f'Found poster URL in description: {original_poster_url}')
            self.debugBrowserMovie.append(f'检测到海报链接：{original_poster_url}')
            
            # Import poster processing function
            from src.core.poster import process_poster
            
            picture_bed_api_url = get_settings('picture_bed_api_url')
            picture_bed_api_token = get_settings('picture_bed_api_token')
            screenshot_storage_path = get_settings('screenshot_storage_path')
            
            self.debugBrowserMovie.append('开始下载并上传海报...')
            
            # Process the poster
            success, result = process_poster(
                original_poster_url,
                picture_bed_api_url,
                picture_bed_api_token,
                screenshot_storage_path
            )
            
            if success:
                uploaded_url = result
                print(f'Poster uploaded successfully: {uploaded_url}')
                self.debugBrowserMovie.append(f'海报上传成功：{uploaded_url}')
                
                # Replace the original URL with uploaded URL
                description = description.replace(
                    f'[img]{original_poster_url}[/img]',
                    f'[img]{uploaded_url}[/img]'
                )
                self.debugBrowserMovie.append('已替换简介中的海报链接')
            else:
                print(f'Poster upload failed: {result}')
                self.debugBrowserMovie.append(f'海报上传失败：{result}')
                
        except Exception as e:
            print(f'Error processing poster: {e}')
            self.debugBrowserMovie.append(f'处理海报时出错：{e}')
        
        return description


    def get_picture_button_movie_clicked(self):
        self.pictureUrlBrowserMovie.setText('')
        is_video_path, response = check_path_and_find_video(
            self.videoPathMovie.text().replace('file:///', ''))  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            self.debugBrowserMovie.append(f'获取视频{video_path}的截图')
            screenshot_storage_path = get_settings('screenshot_storage_path')  # 截图储存路径
            screenshot_number = int(get_settings('screenshot_number'))
            screenshot_threshold = float(get_settings('screenshot_threshold'))
            screenshot_start_percentage = float(get_settings('screenshot_start_percentage'))
            screenshot_end_percentage = float(get_settings('screenshot_end_percentage'))
            do_get_thumbnail = bool(get_settings('do_get_thumbnail'))
            thumbnail_rows = int(get_settings('thumbnail_rows'))
            thumbnail_cols = int(get_settings('thumbnail_cols'))
            auto_upload_screenshot = bool(get_settings('auto_upload_screenshot'))
            self.debugBrowserMovie.append('参数获取成功，开始执行截图函数，需要较长时间，程序会暂时无响应，请稍候...')
            print('参数获取成功，开始执行截图函数')
            pictures = []
            screenshot_success, response = get_screenshot(video_path, screenshot_storage_path, screenshot_number,
                                                          screenshot_threshold, screenshot_start_percentage,
                                                          screenshot_end_percentage, screenshot_min_interval=0.01)
            print('成功获取截图函数的返回值')
            self.debugBrowserMovie.append('成功获取截图函数的返回值')
            if do_get_thumbnail:
                get_thumbnail_success, thumbnail_path = get_thumbnail(video_path, screenshot_storage_path,
                                                                      thumbnail_rows,
                                                                      thumbnail_cols,
                                                                      screenshot_start_percentage,
                                                                      screenshot_end_percentage)
                if get_thumbnail_success:
                    pictures.append(thumbnail_path)
            if screenshot_success:
                pictures = response + pictures
                self.debugBrowserMovie.append(f'成功获取截图：{str(pictures)}')
                # 判断是否需要上传图床
                if auto_upload_screenshot and len(pictures) > 0:
                    picture_bed_path = get_settings('picture_bed_api_url')  # 图床地址
                    picture_bed_token = get_settings('picture_bed_api_token')  # 图床Token
                    print(f'图床参数获取成功，图床地址是：{picture_bed_path}，开始自动上传截图到图床。')
                    self.debugBrowserMovie.append(
                        f'图床参数获取成功，图床地址是：{picture_bed_path}，开始自动上传截图到图床')
                    self.pictureUrlBrowserMovie.setText('')
                    if len(pictures) > 0:
                        if do_get_thumbnail and len(pictures) == 1:
                            self.upload_picture_thread0 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[0], False, True)
                        else:
                            self.upload_picture_thread0 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[0], False, False)
                        self.upload_picture_thread0.result_signal.connect(
                            self.handle_upload_picture_movie_result)  # 连接信号
                        self.upload_picture_thread0.start()  # 启动线程
                        print('启动线程0')
                    if len(pictures) > 1:
                        if do_get_thumbnail and len(pictures) == 2:
                            self.upload_picture_thread1 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[1], False, True)
                        else:
                            self.upload_picture_thread1 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[1], False, False)
                        self.upload_picture_thread1.result_signal.connect(
                            self.handle_upload_picture_movie_result)  # 连接信号
                        self.upload_picture_thread1.start()  # 启动线程
                        print('启动线程1')
                    if len(pictures) > 2:
                        if do_get_thumbnail and len(pictures) == 3:
                            self.upload_picture_thread2 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[2], False, True)
                        else:
                            self.upload_picture_thread2 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[2], False, False)
                        self.upload_picture_thread2.result_signal.connect(
                            self.handle_upload_picture_movie_result)  # 连接信号
                        self.upload_picture_thread2.start()  # 启动线程
                        print('启动线程2')
                    if len(pictures) > 3:
                        if do_get_thumbnail and len(pictures) == 4:
                            self.upload_picture_thread3 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[3], False, True)
                        else:
                            self.upload_picture_thread3 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[3], False, False)
                        self.upload_picture_thread3.result_signal.connect(
                            self.handle_upload_picture_movie_result)  # 连接信号
                        self.upload_picture_thread3.start()  # 启动线程
                        print('启动线程3')
                    if len(pictures) > 4:
                        if do_get_thumbnail and len(pictures) == 5:
                            self.upload_picture_thread4 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[4], False, True)
                        else:
                            self.upload_picture_thread4 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[4], False, False)
                        self.upload_picture_thread4.result_signal.connect(
                            self.handle_upload_picture_movie_result)  # 连接信号
                        self.upload_picture_thread4.start()  # 启动线程
                        print('启动线程4')
                    if len(pictures) > 5:
                        if do_get_thumbnail and len(pictures) == 6:
                            self.upload_picture_thread5 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[5], False, True)
                        else:
                            self.upload_picture_thread5 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[5], False, False)
                        self.upload_picture_thread5.result_signal.connect(
                            self.handle_upload_picture_movie_result)  # 连接信号
                        self.upload_picture_thread5.start()  # 启动线程
                        print('启动线程5')
                    print('上传图床线程全部启动')
                    self.debugBrowserMovie.append('上传图床线程启动，请耐心等待图床Api的响应...')
                else:
                    self.debugBrowserMovie.append('未选择自动上传图床功能，图片已储存在本地')
                    output = ''
                    for picture in pictures:
                        output += picture
                        output += '\n'
                    self.pictureUrlBrowserMovie.setText(output)
            else:
                self.debugBrowserMovie.append(f'截图失败：{response[0]}')
        else:
            self.debugBrowserMovie.append(f'您的视频文件路径有误：{response}')

    def handle_upload_picture_movie_result(self, upload_success, api_response, screenshot_path, is_cover, is_thumbnail):
        # 这个函数用于处理上传的结果，它将在主线程中被调用
        # 更新UI，显示上传结果等
        print('接受到上传图床线程请求的结果')
        self.debugBrowserMovie.append('接受到上传图床线程请求的结果')
        if upload_success:
            picture_url = api_response
            self.pictureUrlBrowserMovie.append(picture_url)
            paste_screenshot_url = bool(get_settings('paste_screenshot_url'))
            delete_screenshot = bool(get_settings('delete_screenshot'))
            if paste_screenshot_url:
                self.descriptionBrowserMovie.append(picture_url)
                self.debugBrowserMovie.append('成功将图片链接粘贴到简介后')
            if delete_screenshot:
                if os.path.exists(screenshot_path):
                    # 删除文件
                    os.remove(screenshot_path)
                    print(f'文件"{screenshot_path}"已被删除')
                    self.debugBrowserMovie.append(f'文件"{screenshot_path}"已被删除')
                else:
                    print(f'文件"{screenshot_path}"不存在。')
                    self.debugBrowserMovie.append(f'文件"{screenshot_path}"不存在')
        else:
            self.debugBrowserMovie.append(f'图床响应无效：{api_response}')

    def select_video_button_movie_clicked(self):
        path = get_video_file_path()
        self.videoPathMovie.setText(path)

    def select_video_folder_button_movie_clicked(self):
        path = get_folder_path()
        self.videoPathMovie.setText(path)

    def get_media_info_button_movie_clicked(self):
        self.mediainfoBrowserMovie.setText('')
        is_video_path, response = check_path_and_find_video(
            self.videoPathMovie.text().replace('file:///', ''))  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            get_media_info_success, response = get_media_info(video_path)
            if get_media_info_success:
                media_info = response
                self.mediainfoBrowserMovie.setText(media_info)
                self.mediainfoBrowserMovie.append('\n')
                self.debugBrowserMovie.append(f'成功获取到MediaInfo：{media_info}')
            else:
                self.debugBrowserMovie.append(f'获取MediaInfo失败：{response}')
        else:
            self.debugBrowserMovie.append(f'您的视频文件路径有误：{response}')

    def get_name_button_movie_clicked(self):
        global get_name_movie_success, get_name_movie_failure_number  # 声明全局变量
        get_name_movie_success = False
        get_name_movie_failure_number = 0
        self.path_movie = ''
        self.get_pt_gen_success = False
        try:
            self.descriptionBrowserMovie.setText('')
            pt_gen_api_url = get_settings('pt_gen_api_url')
            pt_gen_api_url_backup = get_settings('pt_gen_api_url_backup')
            resource_url = self.resourceUrlMovie.text()
            if resource_url == '':
                self.debugBrowserMovie.append('请输入输入豆瓣号、Imdb号、豆瓣、IMDb等资源链接')
                get_name_movie_failure_number += 1
                return
            if pt_gen_api_url == '':
                self.debugBrowserMovie.append('请在设置中输入PT-Gen链接')
                get_name_movie_failure_number += 1
                return
            print(f'尝试启动pt_gen_thread，您选择的PT-Gen接口是：{pt_gen_api_url}')
            self.debugBrowserMovie.append(f'尝试启动pt_gen_thread，您选择的PT-Gen接口是：{pt_gen_api_url}')
            self.get_pt_gen_for_name_thread = GetPtGenThread(pt_gen_api_url, resource_url)
            self.get_pt_gen_for_name_thread.result_signal.connect(self.handle_get_pt_gen_for_name_movie_result)  # 连接信号
            self.get_pt_gen_for_name_thread.start()  # 启动线程
            print('启动pt_gen_thread成功，请耐心等待Api返回结果并分析...')
            self.debugBrowserMovie.append('启动pt_gen_thread成功，请耐心等待Api返回结果并分析...')

            print(f'尝试启动备用pt_gen_thread，您选择的备用PT-Gen接口是：{pt_gen_api_url_backup}')
            self.debugBrowserMovie.append(f'尝试启动备用pt_gen_thread，您选择的备用PT-Gen接口是：{pt_gen_api_url_backup}')
            self.get_pt_gen_for_name_backup_thread = GetPtGenThread(pt_gen_api_url_backup, resource_url)
            self.get_pt_gen_for_name_backup_thread.result_signal.connect(
                self.handle_get_pt_gen_for_name_movie_result)  # 连接信号
            self.get_pt_gen_for_name_backup_thread.start()  # 启动线程
            print('启动备用pt_gen_thread成功，请耐心等待Api返回结果并分析...')
            self.debugBrowserMovie.append('启动备用pt_gen_thread成功，请耐心等待Api返回结果并分析...')
        except Exception as e:
            print(f'启动PtGen线程出错：{e}')
            get_name_movie_failure_number += 1
            return False, [f'启动PtGen线程出错：{e}']

    def handle_get_pt_gen_for_name_movie_result(self, get_success, response, raw_data_json=''):
        global get_name_movie_success, get_name_movie_failure_number  # 声明全局变量
        try:
            if self.get_pt_gen_success:
                print("主线程已经成功获取到简介，备用线程关闭")
                get_name_movie_failure_number += 1
                return
            if get_success:
                description = response
                if description:
                    if description == '':
                        self.debugBrowserMovie.append('获取PT-Gen信息失败，响应为空')
                        get_name_movie_failure_number += 1
                        return
                    else:
                        print(f'获得的PT-Gen Api响应：{description}')
                        
                        # Process poster if auto download and upload is enabled
                        description = self._process_poster_in_description(description)
                        
                        self.descriptionBrowserMovie.setText(description)
                else:
                    self.debugBrowserMovie.append('获取PT-Gen信息失败，响应为空')
                    get_name_movie_failure_number += 1
                    return
                self.get_pt_gen_success = True
                video_format, video_codec, bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num, other_titles, actors = (
                    '', '', '', '', '', '', '', '', '', '')
                make_dir = get_settings('make_dir')
                path = self.videoPathMovie.text().replace('file:///', '')

                do_rename_file = get_settings('rename_file')
                second_confirm_file_name = get_settings('second_confirm_file_name')
                do_create_hard_link = get_settings('create_hard_link')

                is_video_path, response = check_path_and_find_video(path)
                if is_video_path == 1 or is_video_path == 2:
                    video_path = response
                    print('重命名初始化完成')
                    self.debugBrowserMovie.append('重命名初始化完成')
                    print('开始获取PT-Gen关键信息')
                    self.debugBrowserMovie.append('开始获取PT-Gen关键信息')
                    try:
                        # 解析raw_data JSON以传递给get_pt_gen_info
                        pt_gen_raw_data = None
                        if raw_data_json:
                            try:
                                import json as _json
                                pt_gen_raw_data = _json.loads(raw_data_json)
                            except Exception:
                                pass
                        original_title, english_title, year, other_names_sorted, categories, actors_list, episodes, season = get_pt_gen_info(
                            description, raw_data=pt_gen_raw_data)
                    except Exception as e:
                        self.debugBrowserMovie.append(
                            f'获取到了PT-Gen Api的响应，但是对于响应的分析有错误：{e}\n获取到的响应是{str(description)}\n请重试！')
                        print(
                            f'获取到了PT-Gen Api的响应，但是对于响应的分析有错误：{e}\n获取到的响应是{str(description)}\n请重试！')
                        get_name_movie_failure_number += 1
                        return
                    print(f'分析后的结果为：original_title: {original_title} english_title: {english_title} '
                          f'year: {year} other_names_sorted: {str(other_names_sorted)} categories: {categories} '
                          f'actors_list: {str(actors_list)}')
                    self.debugBrowserMovie.append(
                        f'分析后的结果为：original_title: {original_title} english_title: {english_title} '
                        f'year: {year} other_names_sorted: {str(other_names_sorted)} categories: {categories} '
                        f'actors_list: {str(actors_list)}')

                    if year == '' or year is None:
                        print('PT-Gen分析结果不包含年份，存在错误')
                        self.debugBrowserMovie.append('PT-Gen分析结果不包含年份，存在错误')
                        get_name_movie_failure_number += 1
                        return
                    print('获取PT-Gen关键信息成功')
                    self.debugBrowserMovie.append('获取PT-Gen关键信息成功')

                    is_first = True
                    for data in actors_list:  # 把演员名转化成str
                        if is_first:
                            actors += data
                            is_first = False
                        else:
                            actors += ' / '
                            actors += data

                    for data in other_names_sorted:  # 把别名转化为str
                        other_titles += data
                        other_titles += ' / '
                    other_titles = other_titles[: -3]

                    english_pattern = r'^[A-Za-z\-\—\:\s\(\)\'\'\@\#\$\%\^\&\*\!\?\,\.\;\[\]\{\}\|\<\>\`\~\d\u2160-\u2188]+$'
                    widget = QWidget(self)
                    if original_title != '':
                        if second_confirm_file_name:
                            if english_title == '':
                                ok = QMessageBox.information(self, 'PT-Gen未获取到英文名称',
                                                             f'资源的名称是：{original_title}\n是否使用汉语拼音作为英文名称？（仅限中文）',
                                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                if ok == QMessageBox.StandardButton.Yes:
                                    english_title = chinese_name_to_pinyin(original_title)
                                if not re.match(english_pattern, english_title):
                                    print('first_english_name does not match the english_pattern.')
                                    if ok == QMessageBox.StandardButton.Yes:
                                        QMessageBox.warning(widget, '警告', '资源名称不是汉语，无法使用汉语拼音')
                                    text, ok = QInputDialog.getText(self, '输入资源的英文名称',
                                                                    'PT-Gen未检测到英文名称，请注意使用英文标点符号')
                                    if ok:
                                        print(f'您输入的数据为：{text}')
                                        self.debugBrowserMovie.append(f'您输入的数据为：{text}')
                                        english_title = text.replace('.', ' ')
                                        invalid_characters = ''
                                        for char in english_title:
                                            if not re.match(english_pattern, char):
                                                invalid_characters += char
                                        print('不匹配的字符：', invalid_characters)
                                        if invalid_characters != '':
                                            QMessageBox.warning(widget, '警告',
                                                                f'您输入的英文名称包含非英文字符或符号\n有以下这些：'
                                                                f'{"|".join(invalid_characters)}\n请重新核对后再生成标准命名')
                                            get_name_movie_failure_number += 1
                                            return

                                    else:
                                        print('未输入任何数据')
                                        self.debugBrowserMovie.append('未输入任何数据')
                                        english_title = ''
                        else:
                            if english_title == '':
                                english_title = chinese_name_to_pinyin(original_title)
                                if not re.match(english_pattern, english_title):
                                    self.debugBrowserMovie.append('缺少英文名称，并且无法生成汉语拼音，请手动获取名称')
                                    get_name_movie_failure_number += 1
                                    return

                    get_video_info_success, response = get_video_info(video_path)
                    if get_video_info_success:
                        video_info = response
                        print(f'获取到关键参数：{str(video_info)}')
                        self.debugBrowserMovie.append(f'获取到关键参数：{str(video_info)}')
                        video_format += video_info[0]
                        video_codec += video_info[1]
                        bit_depth += video_info[2]
                        hdr_format += video_info[3]
                        frame_rate += video_info[4]
                        audio_codec += video_info[5]
                        channels += video_info[6]
                        audio_num += video_info[7]
                    source = self.sourceMovie.currentText()
                    team = self.teamMovie.currentText()
                    print('关键参数赋值成功，开始获取标准命名')
                    self.debugBrowserMovie.append('关键参数赋值成功，开始获取标准命名')
                    main_title = get_name_from_template(english_title, original_title, '', '', year,
                                                        video_format, source, video_codec, bit_depth, hdr_format,
                                                        frame_rate, audio_codec, channels, audio_num, team,
                                                        other_titles, '', '', '',
                                                        categories, actors, 'main_title_movie')
                    print(f'main_title: {main_title}')
                    second_title = get_name_from_template(english_title, original_title, '', '', year,
                                                          video_format, source, video_codec, bit_depth, hdr_format,
                                                          frame_rate, audio_codec, channels, audio_num, team,
                                                          other_titles, '', '', '',
                                                          categories, actors, 'second_title_movie')
                    print(f'second_title: {second_title}')
                    file_name = get_name_from_template(english_title, original_title, '', '', year,
                                                       video_format, source, video_codec, bit_depth, hdr_format,
                                                       frame_rate, audio_codec, channels, audio_num, team, other_titles,
                                                       '', '', '', categories,
                                                       actors, 'file_name_movie')
                    print(f'file_name: {file_name}')
                    if second_confirm_file_name:
                        text, ok = QInputDialog.getText(self, '确认', '请确认文件名称，如有问题请修改',
                                                        QLineEdit.EchoMode.Normal, file_name)
                        if ok:
                            print(f'您确认文件名为：{text}')
                            self.debugBrowserMovie.append(f'您确认文件名为：{text}')
                            file_name = text
                        else:
                            print('您点了取消确认，重命名已取消')
                            self.debugBrowserMovie.append('您点了取消确认，重命名已取消')
                            get_name_movie_failure_number += 1
                            return
                    if is_filename_too_long(file_name):
                        text, ok = QInputDialog.getText(self, '警告', '文件名过长，请修改文件名称！',
                                                        QLineEdit.EchoMode.Normal, file_name)
                        if ok:
                            print(f'您修改文件名为：{text}')
                            self.debugBrowserMovie.append(f'您修改文件名为：{text}')
                            file_name = text
                        else:
                            print('您点了取消确认，重命名已取消')
                            self.debugBrowserMovie.append('您点了取消确认，重命名已取消')
                            get_name_movie_failure_number += 1
                            return
                        if is_filename_too_long(file_name):
                            QMessageBox.warning(widget, '警告',
                                                '您输入的文件名过长，请重新核对后再生成标准命名！')
                            self.debugBrowserMovie.append('您输入的文件名过长，请重新核对后再生成标准命名！')
                            get_name_movie_failure_number += 1
                            return
                    print(f'最终确认文件名是：{file_name}')
                    self.mainTitleBrowserMovie.setText(main_title)
                    self.secondTitleBrowserMovie.setText(second_title)
                    self.fileNameBrowserMovie.setText(file_name)

                    if do_create_hard_link:
                        print('开始创建硬链接')
                        create_hard_link_success, response = create_hard_link(path)
                        if create_hard_link_success:
                            path = response
                            self.path_movie = path  # 更新全局变量
                            self.videoPathMovie.setText(path)
                            self.debugBrowserMovie.append(f'创建硬链接成功：{path}')
                            is_video_path, response = check_path_and_find_video(path)
                            if is_video_path == 1:
                                video_path = response
                        else:
                            self.debugBrowserMovie.append(f'您选择创建硬链接，但是创建失败了：{response}')
                            get_name_movie_failure_number += 1
                            return

                    if make_dir and is_video_path == 1:
                        print('开始创建文件夹并移动视频')
                        self.debugBrowserMovie.append('开始创建文件夹并移动视频')
                        move_file_to_folder_success, response = move_file_to_folder(path, file_name)
                        if move_file_to_folder_success:
                            path = os.path.dirname(response)
                            video_path = response
                            self.path_movie = path  # 更新全局变量
                            self.videoPathMovie.setText(path)
                            self.debugBrowserMovie.append(f'视频文件成功移动到：{path}')
                        else:
                            self.debugBrowserMovie.append(f'创建文件夹失败：{response}')
                            get_name_movie_failure_number += 1
                            return

                    if do_rename_file:
                        if is_video_path == 2:
                            print('对文件夹重新命名')
                            self.debugBrowserMovie.append('开始对文件夹重新命名')
                            rename_directory_success, response = rename_folder(path, file_name)
                            if rename_directory_success:
                                path = response
                                self.path_movie = path  # 更新全局变量
                                self.videoPathMovie.setText(path)
                                self.debugBrowserMovie.append(f'视频文件夹成功重新命名为：{path}')
                                is_video_path, response = check_path_and_find_video(path)
                                if is_video_path == 2:
                                    video_path = response
                                    self.debugBrowserMovie.append(f'成功读取到视频文件：{video_path}')
                                else:
                                    self.debugBrowserMovie.append(f'读取视频文件失败：{response}')
                                    get_name_movie_failure_number += 1
                                    return
                            else:
                                self.debugBrowserMovie.append(f'重命名失败：{response}')
                                get_name_movie_failure_number += 1
                                return

                        print('开始对文件重新命名')
                        self.debugBrowserMovie.append('开始对文件重新命名')
                        rename_file_success, response = rename_file(video_path, file_name)
                        if rename_file_success:
                            video_path = response
                            if is_video_path == 1:
                                self.path_movie = path  # 更新全局变量
                                self.videoPathMovie.setText(video_path)
                                self.debugBrowserMovie.append(f'视频资源路径更新为：{video_path}')
                            if is_video_path == 2:
                                self.path_movie = path  # 更新全局变量
                                self.videoPathMovie.setText(path)
                                self.debugBrowserMovie.append(f'视视频资源路径更新为：{path}')
                        else:
                            self.debugBrowserMovie.append(f'重命名失败：{response}')
                            get_name_movie_failure_number += 1
                            return

                else:
                    self.debugBrowserMovie.append(f'您的视频文件路径有误{response}')
                    get_name_movie_failure_number += 1
                    return
            else:
                self.debugBrowserMovie.append(f'未成功获取到任何PT-Gen信息：{response}')
                get_name_movie_failure_number += 1
                return
            print("重命名全部成功")
            get_name_movie_success = True
        except Exception as e:
            self.debugBrowserMovie.append(f'启动PtGen线程成功，但是重命名出错：{e}')
            print(f'启动PtGen线程成功，但是重命名出错：{e}')
            get_name_movie_failure_number += 1
            return False, [f'启动PtGen线程成功，但是重命名出错：{e}']

    def make_torrent_button_movie_clicked(self):
        self.torrent_url = ''
        path = self.videoPathMovie.text().replace('file:///', '')
        is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            torrent_storage_path = str(get_settings('torrent_storage_path'))
            self.debugBrowserMovie.append(f'开始将"{path}"制作种子，储存在"{torrent_storage_path}"')
            self.make_torrent_thread = MakeTorrentThread(path, torrent_storage_path)
            self.make_torrent_thread.result_signal.connect(self.handle_make_torrent_movie_result)  # 连接信号
            self.make_torrent_thread.start()  # 启动线程
            self.debugBrowserMovie.append('制作种子线程启动成功，正在后台制作种子，请耐心等待种子制作完毕...')
        else:
            self.debugBrowserMovie.append(f'制作种子失败：{response}')

    def handle_make_torrent_movie_result(self, get_success, response):
        if get_success:
            torrent_path = response
            self.torrent_url = f'http://127.0.0.1:{get_settings("api_port")}/api/getFile?filePath={torrent_path}'
            self.debugBrowserMovie.append(f'成功制作种子：{torrent_path}')
        else:
            self.debugBrowserMovie.append(f'制作种子失败：{response}')

    # 以上是Movie页面的代码

    # 以下是TV页面的代码
    def start_button_tv_clicked(self):
        self.get_name_button_tv_clicked()

        print(f'重命名启动成功')
        self.wait_for_rename_thread = WaitForRenameThread(False)
        self.wait_for_rename_thread.result_signal.connect(self.handle_process_after_rename_tv)  # 连接信号
        self.wait_for_rename_thread.start()  # 启动线程
        self.debugBrowserTV.append('重命名启动成功，等待重命名完成后将自动进行其他操作...')

    def handle_process_after_rename_tv(self, rename_success):
        if rename_success:
            print('重命名成功，开始进行后续操作')
            self.debugBrowserTV.append('重命名成功，开始进行后续操作')

            self.videoPathTV.setText(self.path_tv)
            print('当前的视频地址' + self.path_tv)
            QApplication.processEvents()  # 处理所有挂起的事件，更新页面
            self.get_media_info_button_tv_clicked()
            QApplication.processEvents()  # 处理事件
            self.get_picture_button_tv_clicked()
            QApplication.processEvents()  # 处理事件
            self.make_torrent_button_tv_clicked()
            QApplication.processEvents()  # 处理事件
        else:
            print('重命名失败，一键启动已终止')
            self.debugBrowserTV.append('重命名失败，一键启动已终止')
            show_toast(self, '重命名失败，一键启动已终止', 'error', 6000)

    def auto_feed_button_tv_clicked(self):
        main_title, second_title, description, media_info, file_name, team, source = '', '', '', '', '', '', ''
        main_title += self.mainTitleBrowserTV.toPlainText()
        second_title += self.secondTitleBrowserTV.toPlainText()
        description += self.descriptionBrowserTV.toPlainText()
        media_info += self.mediainfoBrowserTV.toPlainText()
        file_name += self.fileNameBrowserTV.toPlainText()
        team += self.teamTV.currentText()
        source += self.sourceTV.currentText()
        category = '剧集'
        get_auto_feed_link_success, response = get_auto_feed_link(main_title, second_title, description, media_info,
                                                                  file_name, team, source, category, self.torrent_url)
        if get_auto_feed_link_success:
            self.debugBrowserTV.append(f'auto_feed_link: {response}')
            pyperclip.copy(response)
            self.debugBrowserTV.append('auto_feed链接已经复制到剪切板，请粘贴到浏览器访问')
            try:
                if get_settings('open_auto_feed_link'):
                    # 创建临时HTML文件
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w') as temp:
                        temp.write(
                            f'<html><body><a href="{response}" id="link">Link</a><script>document.getElementById("link").click();</script></body></html>')
                        temp_html_path = temp.name

                    # 打开临时HTML文件
                    webbrowser.open(f'file://{temp_html_path}')
            except Exception as e:
                self.debugBrowserTV.append(f'自动打开链接失败，请手动粘贴到浏览器访问：{e}')
        else:
            self.debugBrowserTV.append(f'创建auto_feed_link失败：{response}')

    def get_pt_gen_button_tv_clicked(self):
        self.get_pt_gen_success = False
        self.descriptionBrowserTV.setText('')
        pt_gen_api_url = get_settings('pt_gen_api_url')
        pt_gen_api_url_backup = get_settings('pt_gen_api_url_backup')
        resource_url = self.resourceUrlTV.text()

        if resource_url == '':
            self.debugBrowserTV.append('请输入输入豆瓣号、Imdb号、豆瓣、IMDb等资源链接')
            return
        if pt_gen_api_url == '':
            self.debugBrowserTV.append('请在设置中输入PT-Gen链接')
            return
        print(f'尝试启动pt_gen_thread，您选择的PT-Gen接口是：{pt_gen_api_url}')
        self.debugBrowserTV.append(f'尝试启动pt_gen_thread，您选择的PT-Gen接口是：{pt_gen_api_url}')
        self.get_pt_gen_thread = GetPtGenThread(pt_gen_api_url, resource_url)
        self.get_pt_gen_thread.result_signal.connect(self.handle_get_pt_gen_tv_result)  # 连接信号
        self.get_pt_gen_thread.start()  # 启动线程
        print('启动pt_gen_thread成功，请耐心等待Api返回结果并分析...')
        self.debugBrowserTV.append('启动pt_gen_thread成功，请耐心等待Api返回结果并分析...')

        print(f'尝试启动备用pt_gen_thread，您选择的PT-Gen接口是：{pt_gen_api_url_backup}')
        self.debugBrowserTV.append(f'尝试启动备用pt_gen_thread，您选择的PT-Gen接口是：{pt_gen_api_url_backup}')
        self.get_pt_gen_backup_thread = GetPtGenThread(pt_gen_api_url_backup, resource_url)
        self.get_pt_gen_backup_thread.result_signal.connect(self.handle_get_pt_gen_tv_result)  # 连接信号
        self.get_pt_gen_backup_thread.start()  # 启动线程
        print('启动备用pt_gen_thread成功，请耐心等待Api返回结果并分析...')
        self.debugBrowserTV.append('启动备用pt_gen_thread成功，请耐心等待Api返回结果并分析...')

    def handle_get_pt_gen_tv_result(self, get_success, response, raw_data_json=''):
        if self.get_pt_gen_success:
            print("主线程已经成功获取到简介，备用线程关闭")
            return
        if get_success:
            if response:
                print(response)
                self.get_pt_gen_success = True
                
                # Process poster if auto download and upload is enabled (TV tab)
                response = self._process_poster_in_description_tv(response)
                
                self.descriptionBrowserTV.setText(response)
                self.debugBrowserTV.append('成功获取PT-Gen信息')
            else:
                self.debugBrowserTV.append('获取PT-Gen信息失败')
        else:
            self.debugBrowserTV.append(f'未成功获取到任何PT-Gen信息{response}')

    def _process_poster_in_description_tv(self, description):
        """Process poster URLs in description for TV tab."""
        try:
            auto_download_upload_poster = bool(get_settings('auto_download_upload_poster'))
            if not auto_download_upload_poster:
                return description
            
            # Extract poster URL from [img]...[/img] tag
            import re
            img_pattern = r'\[img\](https?://[^\]]+)\[/img\]'
            match = re.search(img_pattern, description)
            
            if not match:
                print('No [img] tag found in description')
                return description
            
            original_poster_url = match.group(1)
            print(f'Found poster URL in description: {original_poster_url}')
            self.debugBrowserTV.append(f'检测到海报链接：{original_poster_url}')
            
            # Import poster processing function
            from src.core.poster import process_poster
            
            picture_bed_api_url = get_settings('picture_bed_api_url')
            picture_bed_api_token = get_settings('picture_bed_api_token')
            screenshot_storage_path = get_settings('screenshot_storage_path')
            
            self.debugBrowserTV.append('开始下载并上传海报...')
            
            # Process the poster
            success, result = process_poster(
                original_poster_url,
                picture_bed_api_url,
                picture_bed_api_token,
                screenshot_storage_path
            )
            
            if success:
                uploaded_url = result
                print(f'Poster uploaded successfully: {uploaded_url}')
                self.debugBrowserTV.append(f'海报上传成功：{uploaded_url}')
                
                # Replace the original URL with uploaded URL
                description = description.replace(
                    f'[img]{original_poster_url}[/img]',
                    f'[img]{uploaded_url}[/img]'
                )
                self.debugBrowserTV.append('已替换简介中的海报链接')
            else:
                print(f'Poster upload failed: {result}')
                self.debugBrowserTV.append(f'海报上传失败：{result}')
                
        except Exception as e:
            print(f'Error processing poster: {e}')
            self.debugBrowserTV.append(f'处理海报时出错：{e}')
        
        return description


    def get_picture_button_tv_clicked(self):
        self.pictureUrlBrowserTV.setText('')
        is_video_path, video_path = check_path_and_find_video(
            self.videoPathTV.text().replace('file:///', ''))  # 视频资源的路径

        if is_video_path == 1 or is_video_path == 2:
            self.debugBrowserTV.append(f'获取视频{video_path}的截图')
            screenshot_storage_path = get_settings('screenshot_storage_path')  # 截图储存路径
            screenshot_number = int(get_settings('screenshot_number'))
            screenshot_threshold = float(get_settings('screenshot_threshold'))
            screenshot_start_percentage = float(get_settings('screenshot_start_percentage'))
            screenshot_end_percentage = float(get_settings('screenshot_end_percentage'))
            do_get_thumbnail = bool(get_settings('do_get_thumbnail'))
            thumbnail_rows = int(get_settings('thumbnail_rows'))
            thumbnail_cols = int(get_settings('thumbnail_cols'))
            auto_upload_screenshot = bool(get_settings('auto_upload_screenshot'))
            self.debugBrowserTV.append('参数获取成功，开始执行截图函数，需要较长时间，程序会暂时无响应，请稍候...')
            print('参数获取成功，开始执行截图函数')
            pictures = []
            screenshot_success, response = get_screenshot(video_path, screenshot_storage_path, screenshot_number,
                                                          screenshot_threshold, screenshot_start_percentage,
                                                          screenshot_end_percentage, screenshot_min_interval=0.01)
            print('成功获取截图函数的返回值')
            self.debugBrowserTV.append('成功获取截图函数的返回值')
            if do_get_thumbnail:
                get_thumbnail_success, thumbnail_path = get_thumbnail(video_path, screenshot_storage_path,
                                                                      thumbnail_rows,
                                                                      thumbnail_cols,
                                                                      screenshot_start_percentage,
                                                                      screenshot_end_percentage)
                if get_thumbnail_success:
                    pictures.append(thumbnail_path)
            if screenshot_success:
                pictures = response + pictures
                self.debugBrowserTV.append(f'成功获取截图：{str(pictures)}')
                # 判断是否需要上传图床
                if auto_upload_screenshot and len(pictures) > 0:
                    picture_bed_path = get_settings('picture_bed_api_url')  # 图床地址
                    picture_bed_token = get_settings('picture_bed_api_token')  # 图床Token
                    print(f'图床参数获取成功，图床地址是：{picture_bed_path}，开始自动上传截图到图床。')
                    self.debugBrowserTV.append(
                        f'图床参数获取成功，图床地址是：{picture_bed_path}，开始自动上传截图到图床。')
                    self.pictureUrlBrowserTV.setText('')
                    if len(pictures) > 0:
                        if do_get_thumbnail and len(pictures) == 1:
                            self.upload_picture_thread0 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[0], False, True)
                        else:
                            self.upload_picture_thread0 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[0], False, False)
                        self.upload_picture_thread0.result_signal.connect(self.handle_upload_picture_tv_result)  # 连接信号
                        self.upload_picture_thread0.start()  # 启动线程
                        print('启动线程0')
                    if len(pictures) > 1:
                        if do_get_thumbnail and len(pictures) == 2:
                            self.upload_picture_thread1 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[1], False, True)
                        else:
                            self.upload_picture_thread1 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[1], False, False)
                        self.upload_picture_thread1.result_signal.connect(self.handle_upload_picture_tv_result)  # 连接信号
                        self.upload_picture_thread1.start()  # 启动线程
                        print('启动线程1')
                    if len(pictures) > 2:
                        if do_get_thumbnail and len(pictures) == 3:
                            self.upload_picture_thread2 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[2], False, True)
                        else:
                            self.upload_picture_thread2 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[2], False, False)
                        self.upload_picture_thread2.result_signal.connect(self.handle_upload_picture_tv_result)  # 连接信号
                        self.upload_picture_thread2.start()  # 启动线程
                        print('启动线程2')
                    if len(pictures) > 3:
                        if do_get_thumbnail and len(pictures) == 4:
                            self.upload_picture_thread3 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[3], False, True)
                        else:
                            self.upload_picture_thread3 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[3], False, False)
                        self.upload_picture_thread3.result_signal.connect(self.handle_upload_picture_tv_result)  # 连接信号
                        self.upload_picture_thread3.start()  # 启动线程
                        print('启动线程3')
                    if len(pictures) > 4:
                        if do_get_thumbnail and len(pictures) == 5:
                            self.upload_picture_thread4 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[4], False, True)
                        else:
                            self.upload_picture_thread4 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[4], False, False)
                        self.upload_picture_thread4.result_signal.connect(self.handle_upload_picture_tv_result)  # 连接信号
                        self.upload_picture_thread4.start()  # 启动线程
                        print('启动线程4')
                    if len(pictures) > 5:
                        if do_get_thumbnail and len(pictures) == 6:
                            self.upload_picture_thread5 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[5], False, True)
                        else:
                            self.upload_picture_thread5 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[5], False, False)
                        self.upload_picture_thread5.result_signal.connect(self.handle_upload_picture_tv_result)  # 连接信号
                        self.upload_picture_thread5.start()  # 启动线程
                        print('启动线程5')
                    print('上传图床线程全部启动')
                    self.debugBrowserTV.append('上传图床线程启动，请耐心等待图床Api的响应...')
                else:
                    self.debugBrowserTV.append('未选择自动上传图床功能，图片已储存在本地')
                    output = ''
                    for picture in pictures:
                        output += picture
                        output += '\n'
                    self.pictureUrlBrowserTV.setText(output)
            else:
                self.debugBrowserTV.append(f'截图失败{response[0]}')
        else:
            self.debugBrowserTV.append('您的视频文件路径有误')

    def handle_upload_picture_tv_result(self, upload_success, api_response, screenshot_path, is_cover, is_thumbnail):
        # 这个函数用于处理上传的结果，它将在主线程中被调用
        # 更新UI，显示上传结果等
        print('接受到上传图床线程请求的结果')
        self.debugBrowserTV.append('接受到上传图床线程请求的结果')
        if upload_success:
            self.pictureUrlBrowserTV.append(api_response)
            paste_screenshot_url = bool(get_settings('paste_screenshot_url'))
            delete_screenshot = bool(get_settings('delete_screenshot'))
            if paste_screenshot_url:
                self.descriptionBrowserTV.append(api_response)
                self.debugBrowserTV.append('成功将图片链接粘贴到简介后')
            if delete_screenshot:
                if os.path.exists(screenshot_path):
                    # 删除文件
                    os.remove(screenshot_path)
                    print(f'文件"{screenshot_path}"已被删除')
                    self.debugBrowserTV.append(f'文件"{screenshot_path}"已被删除')
                else:
                    print(f'文件"{screenshot_path}"不存在。')
                    self.debugBrowserTV.append(f'文件"{screenshot_path}"不存在')
        else:
            self.debugBrowserTV.append(f'图床响应无效：{api_response}')

    def select_video_folder_button_tv_clicked(self):
        path = get_folder_path()
        self.videoPathTV.setText(path)

    def get_media_info_button_tv_clicked(self):
        self.mediainfoBrowserTV.setText('')
        is_video_path, response = check_path_and_find_video(
            self.videoPathTV.text().replace('file:///', ''))  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            get_media_info_success, response = get_media_info(video_path)
            if get_media_info_success:
                media_info = response
                self.mediainfoBrowserTV.setText(media_info)
                self.mediainfoBrowserTV.append('\n')
                self.debugBrowserTV.append(f'成功获取到MediaInfo：{media_info}')
            else:
                self.debugBrowserTV.append(f'获取MediaInfo失败：{response}')
        else:
            self.debugBrowserTV.append(f'您的视频文件路径有误：{response}')

    def get_name_button_tv_clicked(self):
        global get_name_tv_success, get_name_tv_failure_number
        get_name_tv_success = False
        get_name_tv_failure_number = 0
        self.path_tv = ''
        self.get_pt_gen_success = False
        try:
            self.descriptionBrowserTV.setText('')
            pt_gen_api_url = get_settings('pt_gen_api_url')
            pt_gen_api_url_backup = get_settings('pt_gen_api_url_backup')
            resource_url = self.resourceUrlTV.text()

            if resource_url == '':
                self.debugBrowserTV.append('请输入输入豆瓣号、Imdb号、豆瓣、IMDb等资源链接')
                get_name_tv_failure_number += 1
                return
            if pt_gen_api_url == '':
                self.debugBrowserTV.append('请在设置中输入PT-Gen链接')
                get_name_tv_failure_number += 1
                return
            print('尝试启动pt_gen_thread')
            self.debugBrowserTV.append(f'尝试启动pt_gen_thread，您选择的PT-Gen接口是：{pt_gen_api_url}')
            self.get_pt_gen_for_name_thread = GetPtGenThread(pt_gen_api_url, resource_url)
            self.get_pt_gen_for_name_thread.result_signal.connect(self.handle_get_pt_gen_for_name_tv_result)  # 连接信号
            self.get_pt_gen_for_name_thread.start()  # 启动线程
            print('启动pt_gen_thread成功，请耐心等待Api返回结果并分析...')
            self.debugBrowserTV.append('启动pt_gen_thread成功，请耐心等待Api返回结果并分析...')

            print('尝试启动备用pt_gen_thread')
            self.debugBrowserTV.append(f'尝试启动pt_gen_thread，您选择的备用PT-Gen接口是：{pt_gen_api_url_backup}')
            self.get_pt_gen_for_name_backup_thread = GetPtGenThread(pt_gen_api_url_backup, resource_url)
            self.get_pt_gen_for_name_backup_thread.result_signal.connect(
                self.handle_get_pt_gen_for_name_tv_result)  # 连接信号
            self.get_pt_gen_for_name_backup_thread.start()  # 启动线程
            print('启动备用pt_gen_thread成功，请耐心等待Api返回结果并分析...')
            self.debugBrowserTV.append('启动备用pt_gen_thread成功，请耐心等待Api返回结果并分析...')
        except Exception as e:
            print(f'启动PT-Gen线程出错：{e}')
            get_name_tv_failure_number += 1
            return False, [f'启动PT-Gen线程出错：{e}']

    def handle_get_pt_gen_for_name_tv_result(self, get_success, response, raw_data_json=''):
        global get_name_tv_success, get_name_tv_failure_number
        try:
            if self.get_pt_gen_success:
                print("主线程已经成功获取到简介，备用线程关闭")
                get_name_tv_failure_number += 1
                return
            if get_success:
                description = response
                if description:
                    print(f'获得的PT-Gen Api响应：{description}')
                    if description == '':
                        self.debugBrowserTV.append('获取PT-Gen信息失败，响应为空')
                        get_name_tv_failure_number += 1
                        return
                    
                    # Process poster if auto download and upload is enabled
                    description = self._process_poster_in_description(description)
                    
                    self.descriptionBrowserTV.setText(description)
                else:
                    self.debugBrowserTV.append('获取PT-Gen信息失败，响应为空')
                    get_name_tv_failure_number += 1
                    return
                self.get_pt_gen_success = True
                season_box = self.seasonBoxTV.text()
                episodes_start_number = validate_and_convert_to_int(self.episodesStartBoxTV.text(),
                                                                    'episodes_start_number')

                video_format, video_codec, bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num, other_titles, actors = (
                    '', '', '', '', '', '', '', '', '', '')
                path = self.videoPathTV.text().replace('file:///', '')

                do_rename_file = get_settings('rename_file')
                second_confirm_file_name = get_settings('second_confirm_file_name')
                do_create_hard_link = get_settings('create_hard_link')

                is_video_path, response = check_path_and_find_video(path)
                english_pattern = r'^[A-Za-z\-\—\:\s\(\)\'\'\@\#\$\%\^\&\*\!\?\,\.\;\[\]\{\}\|\<\>\`\~\d\u2160-\u2188]+$'
                widget = QWidget(self)
                if is_video_path == 2:  # 视频路径是文件夹
                    video_path = response
                    get_video_files_success, response = get_video_files(path)  # 获取文件夹内部的所有文件
                    if get_video_files_success:
                        video_files = response
                        print(f'文件夹内检测到以下文件：{str(video_files)}')
                        self.debugBrowserTV.append(f'文件夹内检测到以下文件：{str(video_files)}')
                        episodes_num = len(video_files)  # 获取视频文件的总数
                    else:
                        print(f'文件夹内获取视频文件失败：{response}')
                        self.debugBrowserTV.append(f'文件夹内获取视频文件失败：{response}')
                        get_name_tv_failure_number += 1
                        return

                    print('重命名初始化完成')
                    self.debugBrowserTV.append('重命名初始化完成')
                    print('开始获取PT-Gen关键信息')
                    self.debugBrowserTV.append('开始获取PT-Gen关键信息')
                    try:
                        # 解析raw_data JSON以传递给get_pt_gen_info
                        pt_gen_raw_data = None
                        if raw_data_json:
                            try:
                                import json as _json
                                pt_gen_raw_data = _json.loads(raw_data_json)
                            except Exception:
                                pass
                        original_title, english_title, year, other_names_sorted, categories, actors_list, episodes, season = get_pt_gen_info(
                            description, raw_data=pt_gen_raw_data)
                    except Exception as e:
                        self.debugBrowserTV.append(
                            f'获取到了PT-Gen Api的响应，但是对于响应的分析有错误：{e}\n获取到的响应是{str(description)}\n请重试！')
                        print(
                            f'获取到了PT-Gen Api的响应，但是对于响应的分析有错误：{e}\n获取到的响应是{str(description)}\n请重试！')
                        get_name_tv_failure_number += 1
                        return
                    print(original_title, english_title, year, other_names_sorted, categories, actors_list)
                    self.debugBrowserTV.append(
                        f'分析后的结果为：original_title: {original_title} english_title: {english_title} '
                        f'year: {year} other_names_sorted: {str(other_names_sorted)} categories: {categories} '
                        f'actors_list: {str(actors_list)}')

                    if season is not None and season_box != str(season):
                        season = str(season)
                        ok = QMessageBox.information(self, '您选择的季数信息与PT-Gen获取的不符',
                                                     f'您选择的季数：{season_box}，PT-Gen获取的季数：{season}\n是否坚持使用您选择的季数？',
                                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                        if ok == QMessageBox.StandardButton.Yes:
                            season = season_box
                        elif ok == QMessageBox.StandardButton.Cancel:
                            print('您点了取消，重命名已取消')
                            self.debugBrowserTV.append('您点了取消，重命名已取消')
                            get_name_tv_failure_number += 1
                            return
                    else:
                        season = season_box
                    season_number = season
                    if len(season) < 2:
                        season = f'0{season}'

                    # 生成总集数信息
                    if episodes_start_number == 1 and episodes == episodes_num:
                        total_episodes = f'全{str(episodes_num)}集'
                    else:
                        if episodes_num == 1:
                            total_episodes = f'第{str(episodes_start_number)}集'
                        else:
                            total_episodes = f'第{str(episodes_start_number)}-{str(episodes_start_number + episodes_num - 1)}集'
                    print(f'总集数信息：{total_episodes}')

                    if year == '' or year is None:
                        print('PT-Gen分析结果不包含年份，存在错误')
                        self.debugBrowserTV.append('PT-Gen分析结果不包含年份，存在错误')
                        get_name_tv_failure_number += 1
                        return
                    if original_title != '':
                        if second_confirm_file_name:
                            if english_title == '':
                                ok = QMessageBox.information(self, 'PT-Gen未获取到英文名称',
                                                             f'资源的名称是：{original_title}\n是否使用汉语拼音作为英文名称？（仅限中文）',
                                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                if ok == QMessageBox.StandardButton.Yes:
                                    english_title = chinese_name_to_pinyin(original_title)
                                if not re.match(english_pattern, english_title):
                                    print('first_english_name does not match the english_pattern.')
                                    if ok == QMessageBox.StandardButton.Yes:
                                        QMessageBox.warning(widget, '警告', '资源名称不是汉语，无法使用汉语拼音')
                                    text, ok = QInputDialog.getText(self, '输入资源的英文名称',
                                                                    'PT-Gen未检测到英文名称，请注意使用英文标点符号')
                                    if ok:
                                        print(f'您输入的数据为：{text}')
                                        self.debugBrowserTV.append(f'您输入的数据为：{text}')
                                        english_title = text.replace('.', ' ')
                                        invalid_characters = ''
                                        for char in english_title:
                                            if not re.match(english_pattern, char):
                                                invalid_characters += char
                                        print('不匹配的字符：', invalid_characters)
                                        if invalid_characters != '':
                                            QMessageBox.warning(widget, '警告',
                                                                f'您输入的英文名称包含非英文字符或符号\n有以下这些：'
                                                                f'{"|".join(invalid_characters)}\n请重新核对后再生成标准命名')
                                            get_name_tv_failure_number += 1
                                            return

                                    else:
                                        print('未输入任何数据')
                                        self.debugBrowserTV.append('未输入任何数据')
                                        english_title = ''
                        else:
                            if english_title == '':
                                english_title = chinese_name_to_pinyin(original_title)
                                if not re.match(english_pattern, english_title):
                                    self.debugBrowserTV.append('缺少英文名称，并且无法生成汉语拼音，请手动获取名称')
                                    get_name_tv_failure_number += 1
                                    return
                    print(f'分析后的结果为：original_title: {original_title} english_title: {english_title} '
                          f'year: {year} other_names_sorted: {str(other_names_sorted)} categories: {categories} '
                          f'actors_list: {str(actors_list)}')
                    self.debugBrowserTV.append(
                        f'分析后的结果为：original_title: {original_title} english_title: {english_title} '
                        f'year: {year} other_names_sorted: {str(other_names_sorted)} categories: {categories} '
                        f'actors_list: {str(actors_list)}')
                    is_first = True
                    for data in actors_list:  # 把演员名转化成str
                        if is_first:
                            actors += data
                            is_first = False
                        else:
                            actors += ' / '
                            actors += data

                    for data in other_names_sorted:  # 把别名转化为str
                        other_titles += data
                        other_titles += ' / '
                    other_titles = other_titles[: -3]

                    get_video_info_success, response = get_video_info(video_path)
                    if get_video_info_success:
                        video_info = response
                        print(f'获取到关键参数：{str(video_info)}')
                        self.debugBrowserTV.append(f'获取到关键参数：{str(video_info)}')
                        video_format += video_info[0]
                        video_codec += video_info[1]
                        bit_depth += video_info[2]
                        hdr_format += video_info[3]
                        frame_rate += video_info[4]
                        audio_codec += video_info[5]
                        channels += video_info[6]
                        audio_num += video_info[7]
                    source = self.sourceTV.currentText()
                    team = self.teamTV.currentText()
                    print('关键参数赋值成功，开始获取标准命名')
                    self.debugBrowserTV.append('关键参数赋值成功，开始获取标准命名')
                    english_title = delete_season_number(english_title, season_number)
                    main_title = get_name_from_template(english_title, original_title, season, '', year,
                                                        video_format, source, video_codec, bit_depth, hdr_format,
                                                        frame_rate, audio_codec, channels, audio_num, team,
                                                        other_titles, season_number, total_episodes, '',
                                                        categories, actors, 'main_title_tv')
                    print(f'main_title: {main_title}')
                    second_title = get_name_from_template(english_title, original_title, season, '', year,
                                                          video_format, source, video_codec, bit_depth, hdr_format,
                                                          frame_rate, audio_codec, channels, audio_num, team,
                                                          other_titles, season_number, total_episodes, '',
                                                          categories, actors, 'second_title_tv')
                    print(f'second_title: {second_title}')
                    file_name = get_name_from_template(english_title, original_title, season, '{集数}', year,
                                                       video_format, source, video_codec, bit_depth, hdr_format,
                                                       frame_rate, audio_codec, channels, audio_num, team, other_titles,
                                                       season_number, total_episodes, '', categories,
                                                       actors, 'file_name_tv')
                    print(f'file_name: {file_name}')
                    if second_confirm_file_name:
                        text, ok = QInputDialog.getText(self, '确认',
                                                        '请确认文件名称，如有问题请修改（{集数}表示集数，请勿删除）',
                                                        QLineEdit.EchoMode.Normal, file_name)
                        if ok:
                            print(f'您确认文件名为：{text}')
                            self.debugBrowserTV.append(f'您确认文件名为：{text}')
                            file_name = text
                        else:
                            print('您点了取消确认，重命名已取消')
                            self.debugBrowserTV.append('您点了取消确认，重命名已取消')
                            get_name_tv_failure_number += 1
                            return
                    if is_filename_too_long(file_name):
                        text, ok = QInputDialog.getText(self, '警告', '文件名过长，请修改文件名称！',
                                                        QLineEdit.EchoMode.Normal, file_name)
                        if ok:
                            print(f'您修改文件名为：{text}')
                            self.debugBrowserTV.append(f'您修改文件名为：{text}')
                            file_name = text
                        else:
                            print('您点了取消确认，重命名已取消')
                            self.debugBrowserTV.append('您点了取消确认，重命名已取消')
                            get_name_tv_failure_number += 1
                            return
                        if is_filename_too_long(file_name):
                            QMessageBox.warning(widget, '警告', '您输入的文件名过长，请重新核对后再生成标准命名！')
                            self.debugBrowserTV.append('您输入的文件名过长，请重新核对后再生成标准命名！')
                            get_name_tv_failure_number += 1
                            return
                    print(f'最终确认文件名是：{file_name}')
                    self.mainTitleBrowserTV.setText(main_title)
                    self.secondTitleBrowserTV.setText(second_title)
                    self.fileNameBrowserTV.setText(file_name)

                    if do_create_hard_link:
                        print('开始创建硬链接')
                        create_hard_link_success, response = create_hard_link(path)
                        if create_hard_link_success:
                            path = response
                            self.path_tv = path
                            self.videoPathTV.setText(path)
                            self.debugBrowserTV.append(f'创建硬链接成功：{path}')
                            is_video_path, response = check_path_and_find_video(path)
                            if is_video_path == 2:
                                get_video_files_success, response = get_video_files(path)  # 获取文件夹内部的所有文件
                                if get_video_files_success:
                                    video_files = response
                                    print(f'文件夹内检测到以下文件：{str(video_files)}')
                                    self.debugBrowserTV.append(f'文件夹内检测到以下文件：{str(video_files)}')
                                else:
                                    print(f'文件夹内获取视频文件失败：{response}')
                                    self.debugBrowserTV.append(f'文件夹内获取视频文件失败：{response}')
                                    get_name_tv_failure_number += 1
                                    return
                        else:
                            self.debugBrowserTV.append(f'您选择创建硬链接，但是创建失败了：{path}')
                            get_name_tv_failure_number += 1
                            return

                    if do_rename_file:
                        print('对文件重新命名')
                        self.debugBrowserTV.append('开始对文件重新命名')
                        i = episodes_start_number
                        for video_file in video_files:
                            e = str(i)
                            while len(e) < len(str(episodes_start_number + episodes_num - 1)):
                                e = f'0{e}'
                            if len(e) == 1:
                                e = f'0{e}'
                            rename_file_success, response = rename_file(video_file, file_name.replace('{集数}', e))
                            if rename_file_success:
                                video_file = response
                                self.debugBrowserTV.append(f'视频成功重新命名为：{video_file}')
                            else:
                                self.debugBrowserTV.append(f'重命名失败：{response}')
                                get_name_tv_failure_number += 1
                                return
                            i += 1
                        print('对文件夹重新命名')
                        self.debugBrowserTV.append('开始对文件夹重新命名')
                        rename_directory_success, response = rename_folder(path, file_name.
                                                                           replace('E{集数}', '').
                                                                           replace('{集数}', ''))
                        if rename_directory_success:
                            path = response
                            self.path_tv = path
                            self.videoPathTV.setText(path)
                            self.debugBrowserTV.append(f'视频地址成功重新命名为：{path}')
                        else:
                            self.debugBrowserTV.append(f'重命名失败：{response}')
                            get_name_tv_failure_number += 1
                            return
                else:
                    self.debugBrowserTV.append(f'您的视频文件路径有误：{response}')
                    get_name_tv_failure_number += 1
                    return
            else:
                self.debugBrowserTV.append(f'未成功获取到任何PT-Gen信息：{response}')
                get_name_tv_failure_number += 1
                return
            get_name_tv_success = True
        except Exception as e:
            print(f'启动PtGen线程成功，但是重命名出错：{e}')
            self.debugBrowserTV.append(f'启动PtGen线程成功，但是重命名出错：{e}')
            get_name_tv_failure_number += 1
            return False, [f'启动PtGen线程成功，但是重命名出错：{e}']

    def make_torrent_button_tv_clicked(self):
        self.torrent_url = ''
        is_video_path, response = check_path_and_find_video(
            self.videoPathTV.text().replace('file:///', ''))  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            torrent_storage_path = str(get_settings('torrent_storage_path'))
            folder_path = os.path.dirname(video_path)
            self.debugBrowserTV.append(f'开始将"{folder_path}"制作种子，储存在"{torrent_storage_path}"')
            self.make_torrent_thread = MakeTorrentThread(folder_path, torrent_storage_path)
            self.make_torrent_thread.result_signal.connect(self.handle_make_torrent_tv_result)  # 连接信号
            self.make_torrent_thread.start()  # 启动线程
            self.debugBrowserTV.append('制作种子线程启动成功，正在后台制作种子，请耐心等待种子制作完毕...')
        else:
            self.debugBrowserTV.append(f'制作种子失败：{response}')

    def handle_make_torrent_tv_result(self, get_success, response):
        if get_success:
            torrent_path = response
            self.torrent_url = f'http://127.0.0.1:{get_settings("api_port")}/api/getFile?filePath={torrent_path}'
            self.debugBrowserTV.append(f'成功制作种子：{torrent_path}')
        else:
            self.debugBrowserTV.append(f'制作种子失败：{response}')

    # 以上是TV页面的代码

    # 以下是Playlet页面的代码
    def start_button_playlet_clicked(self):
        if get_settings('second_confirm_file_name'):
            self.debugBrowserMovie.append('如需一键启动，请到设置关闭二次确认文件名功能')
            return
        self.get_name_button_playlet_clicked()
        QApplication.processEvents()  # 处理所有挂起的事件，更新页面
        time.sleep(0)  # 等待 0 毫秒
        self.get_picture_button_playlet_clicked()
        QApplication.processEvents()  # 再次处理事件
        time.sleep(0)  # 等待 2000 毫秒
        self.upload_cover_button_playlet_clicked()
        QApplication.processEvents()  # 再次处理事件
        time.sleep(2)  # 等待 2000 毫秒
        self.get_media_info_button_playlet_clicked()
        QApplication.processEvents()  # 处理事件
        time.sleep(2)  # 等待 2000 毫秒
        self.make_torrent_button_playlet_clicked()
        QApplication.processEvents()  # 处理事件

    def auto_feed_button_playlet_clicked(self):
        main_title, second_title, description, media_info, file_name, team, source = '', '', '', '', '', '', ''
        main_title += self.mainTitleBrowserPlaylet.toPlainText()
        second_title += self.secondTitleBrowserPlaylet.toPlainText()
        description += self.descriptionBrowserPlaylet.toPlainText()
        media_info += self.mediainfoBrowserPlaylet.toPlainText()
        file_name += self.fileNameBrowserPlaylet.toPlainText()
        team = self.teamPlaylet.currentText()
        source = self.sourcePlaylet.currentText()
        category = '短剧'
        get_auto_feed_link_success, response = get_auto_feed_link(main_title, second_title, description, media_info,
                                                                  file_name, team, source, category, self.torrent_url)
        if get_auto_feed_link_success:
            self.debugBrowserPlaylet.append(f'auto_feed_link: {response}')
            pyperclip.copy(response)
            self.debugBrowserPlaylet.append('auto_feed链接已经复制到剪切板，请粘贴到浏览器访问')
            try:
                if get_settings('open_auto_feed_link'):
                    # 创建临时HTML文件
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w') as temp:
                        temp.write(
                            f'<html><body><a href="{response}" id="link">Link</a><script>document.getElementById("link").click();</script></body></html>')
                        temp_html_path = temp.name

                    # 打开临时HTML文件
                    webbrowser.open(f'file://{temp_html_path}')
            except Exception as e:
                self.debugBrowserPlaylet.append(f'自动打开链接失败，请手动粘贴到浏览器访问：{e}')
        else:
            self.debugBrowserPlaylet.append(f'创建auto_feed_link失败：{response}')

    def get_description_playlet_clicked(self):
        try:
            self.descriptionBrowserPlaylet.setText('')
            original_title = self.originalNameEditPlaylet.text()
            if original_title:
                year, area, categories, language = '', '', '', ''
                year += self.yearEditPlaylet.text()
                area += self.areaPlaylet.currentText()
                categories = self.get_categories()
                language += self.languagePlaylet.currentText()
                season_number = self.seasonBoxPlaylet.text()
                self.descriptionBrowserPlaylet.append(
                    get_playlet_description(original_title, year, area, categories, language, season_number))
            else:
                self.debugBrowserPlaylet.append('您没有填写资源名称！')
        except Exception as e:
            print(f'获取简介出错：{e}')
            return False, [f'获取简介出错：{e}']

    def upload_cover_button_playlet_clicked(self):
        cover_path = self.coverPathPlaylet.text()
        if cover_path and cover_path != '':
            self.debugBrowserPlaylet.append(f'上传封面：{cover_path}')
            picture_bed_path = get_settings('picture_bed_api_url')  # 图床地址
            picture_bed_token = get_settings('picture_bed_api_token')  # 图床Token
            self.debugBrowserPlaylet.append(f'图床参数获取成功，图床地址是：{picture_bed_path}，准备开始上传')
            self.upload_cover_thread = UploadPictureThread(picture_bed_path, picture_bed_token, cover_path, True, False)
            self.upload_cover_thread.result_signal.connect(self.handle_upload_picture_playlet_result)  # 连接信号
            self.upload_cover_thread.start()  # 启动线程
            print('上传图床线程启动')
            self.debugBrowserPlaylet.append('上传图床线程启动，请耐心等待图床Api的响应...')
        else:
            self.debugBrowserPlaylet.append('封面路径为空')

    def get_picture_button_playlet_clicked(self):
        self.pictureUrlBrowserPlaylet.setText('')
        is_video_path, response = check_path_and_find_video(
            self.videoPathPlaylet.text().replace('file:///', ''))  # 视频资源的路径

        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            self.debugBrowserPlaylet.append(f'获取视频{video_path}的截图')
            screenshot_storage_path = get_settings('screenshot_storage_path')  # 截图储存路径
            picture_bed_path = get_settings('picture_bed_api_url')  # 图床地址
            picture_bed_token = get_settings('picture_bed_api_token')  # 图床Token
            screenshot_number = int(get_settings('screenshot_number'))
            screenshot_threshold = float(get_settings('screenshot_threshold'))
            screenshot_start_percentage = float(get_settings('screenshot_start_percentage'))
            screenshot_end_percentage = float(get_settings('screenshot_end_percentage'))
            do_get_thumbnail = bool(get_settings('do_get_thumbnail'))
            thumbnail_rows = int(get_settings('thumbnail_rows'))
            thumbnail_cols = int(get_settings('thumbnail_cols'))
            auto_upload_screenshot = bool(get_settings('auto_upload_screenshot'))
            self.debugBrowserPlaylet.append('参数获取成功，开始执行截图函数，需要较长时间，程序会暂时无响应，请稍候...')
            print('参数获取成功，开始执行截图函数')
            pictures = []
            screenshot_success, response = get_screenshot(video_path, screenshot_storage_path, screenshot_number,
                                                          screenshot_threshold, screenshot_start_percentage,
                                                          screenshot_end_percentage, screenshot_min_interval=0.01)
            print('成功获取截图函数的返回值')
            self.debugBrowserPlaylet.append('成功获取截图函数的返回值')
            if do_get_thumbnail:
                get_thumbnail_success, thumbnail_path = get_thumbnail(video_path, screenshot_storage_path,
                                                                      thumbnail_rows,
                                                                      thumbnail_cols, screenshot_start_percentage,
                                                                      screenshot_end_percentage)
                if get_thumbnail_success:
                    pictures.append(thumbnail_path)
            if screenshot_success:
                pictures = response + pictures
                self.debugBrowserPlaylet.append(f'成功获取截图：{str(pictures)}')
                # 判断是否需要上传图床
                if auto_upload_screenshot and len(pictures) > 0:
                    print(f'图床参数获取成功，图床地址是：{picture_bed_path}，开始自动上传截图到图床。')
                    self.debugBrowserPlaylet.append(
                        f'图床参数获取成功，图床地址是：{picture_bed_path}，开始自动上传截图到图床。')
                    self.pictureUrlBrowserPlaylet.setText('')
                    if len(pictures) > 0:
                        if do_get_thumbnail and len(pictures) == 1:
                            self.upload_picture_thread0 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[0], False, True)
                        else:
                            self.upload_picture_thread0 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[0], False, False)
                        self.upload_picture_thread0.result_signal.connect(
                            self.handle_upload_picture_playlet_result)  # 连接信号
                        self.upload_picture_thread0.start()  # 启动线程
                        print('启动线程0')
                    if len(pictures) > 1:
                        if do_get_thumbnail and len(pictures) == 2:
                            self.upload_picture_thread1 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[1], False, True)
                        else:
                            self.upload_picture_thread1 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[1], False, False)
                        self.upload_picture_thread1.result_signal.connect(
                            self.handle_upload_picture_playlet_result)  # 连接信号
                        self.upload_picture_thread1.start()  # 启动线程
                        print('启动线程1')
                    if len(pictures) > 2:
                        if do_get_thumbnail and len(pictures) == 3:
                            self.upload_picture_thread2 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[2], False, True)
                        else:
                            self.upload_picture_thread2 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[2], False, False)
                        self.upload_picture_thread2.result_signal.connect(
                            self.handle_upload_picture_playlet_result)  # 连接信号
                        self.upload_picture_thread2.start()  # 启动线程
                        print('启动线程2')
                    if len(pictures) > 3:
                        if do_get_thumbnail and len(pictures) == 4:
                            self.upload_picture_thread3 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[3], False, True)
                        else:
                            self.upload_picture_thread3 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[3], False, False)
                        self.upload_picture_thread3.result_signal.connect(
                            self.handle_upload_picture_playlet_result)  # 连接信号
                        self.upload_picture_thread3.start()  # 启动线程
                        print('启动线程3')
                    if len(pictures) > 4:
                        if do_get_thumbnail and len(pictures) == 5:
                            self.upload_picture_thread4 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[4], False, True)
                        else:
                            self.upload_picture_thread4 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[4], False, False)
                        self.upload_picture_thread4.result_signal.connect(
                            self.handle_upload_picture_playlet_result)  # 连接信号
                        self.upload_picture_thread4.start()  # 启动线程
                        print('启动线程4')
                    if len(pictures) > 5:
                        if do_get_thumbnail and len(pictures) == 6:
                            self.upload_picture_thread5 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[5], False, True)
                        else:
                            self.upload_picture_thread5 = UploadPictureThread(picture_bed_path, picture_bed_token,
                                                                              pictures[5], False, False)
                        self.upload_picture_thread5.result_signal.connect(
                            self.handle_upload_picture_playlet_result)  # 连接信号
                        self.upload_picture_thread5.start()  # 启动线程
                        print('启动线程5')
                    print('上传图床线程全部启动')
                    self.debugBrowserPlaylet.append('上传图床线程启动，请耐心等待图床Api的响应...')

                else:
                    self.debugBrowserPlaylet.append('未选择自动上传图床功能，图片已储存在本地')
                    screenshot_path = ''
                    for r in pictures:
                        screenshot_path += r
                        screenshot_path += '\n'
                    self.pictureUrlBrowserMovie.setText(screenshot_path)
            else:
                self.debugBrowserPlaylet.append(f'截图失败{response[0]}')
        else:
            self.debugBrowserPlaylet.append(f'您的视频文件路径有误：{response}')

    def handle_upload_picture_playlet_result(self, upload_success, api_response, screenshot_path, is_cover, is_thumbnail):
        # 这个函数用于处理上传的结果，它将在主线程中被调用
        # 更新UI，显示上传结果等
        print(f'is_cover: {is_cover}')
        print('接受到上传图床线程请求的结果')
        self.debugBrowserPlaylet.append('接受到上传图床线程请求的结果')
        if upload_success:
            picture_url = api_response
            self.pictureUrlBrowserPlaylet.append(picture_url)
            paste_screenshot_url = bool(get_settings('paste_screenshot_url'))
            delete_screenshot = bool(get_settings('delete_screenshot'))
            if paste_screenshot_url:
                if is_cover:
                    temp = self.descriptionBrowserPlaylet.toPlainText()
                    temp = f'{picture_url}\n{temp}'
                    self.descriptionBrowserPlaylet.setText(temp)
                    self.debugBrowserPlaylet.append('成功将封面链接粘贴到简介前')
                else:
                    self.descriptionBrowserPlaylet.append(picture_url)
                    self.debugBrowserPlaylet.append('成功将图片链接粘贴到简介后')
            if delete_screenshot:
                if not is_cover:
                    if os.path.exists(screenshot_path):
                        # 删除文件
                        os.remove(screenshot_path)
                        print(f'文件"{screenshot_path}"已被删除')
                        self.debugBrowserPlaylet.append(f'文件"{screenshot_path}"已被删除')
                    else:
                        print(f'文件"{screenshot_path}"不存在')
                        self.debugBrowserPlaylet.append(f'文件"{screenshot_path}"不存在')
        else:
            self.debugBrowserPlaylet.append(f'图床响应无效：{api_response}')

    def select_cover_folder_button_playlet_clicked(self):
        path = get_picture_file_path()
        self.coverPathPlaylet.setText(path)

    def select_video_folder_button_playlet_clicked(self):
        path = get_folder_path()
        self.videoPathPlaylet.setText(path)

    def get_media_info_button_playlet_clicked(self):
        self.mediainfoBrowserPlaylet.setText('')
        is_video_path, response = check_path_and_find_video(
            self.videoPathPlaylet.text().replace('file:///', ''))  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            get_media_info_success, response = get_media_info(video_path)
            if get_media_info_success:
                media_info = response
                self.mediainfoBrowserPlaylet.setText(media_info)
                self.mediainfoBrowserPlaylet.append('\n')
                self.debugBrowserPlaylet.append(f'成功获取到MediaInfo：{media_info}')
            else:
                self.debugBrowserPlaylet.append(f'获取MediaInfo失败：{response}')
        else:
            self.debugBrowserPlaylet.append(f'您的视频文件路径有误：{response}')

    def get_name_button_playlet_clicked(self):
        try:
            do_rename_file = get_settings('rename_file')
            second_confirm_file_name = get_settings('second_confirm_file_name')
            do_create_hard_link = get_settings('create_hard_link')
            self.get_description_playlet_clicked()
            original_title = self.originalNameEditPlaylet.text()
            english_title = ''
            english_pattern = r'^[A-Za-z\-\—\:\s\(\)\'\'\@\#\$\%\^\&\*\!\?\,\.\;\[\]\{\}\|\<\>\`\~\d\u2160-\u2188]+$'
            widget = QWidget(self)
            if original_title != '':
                if second_confirm_file_name:
                    if not re.match(english_pattern, original_title):
                        ok = QMessageBox.information(self, '资源名称不是英文',
                                                     f'资源的名称是：{original_title}\n是否使用汉语拼音作为英文名称？（仅限中文）',
                                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        print(f'你的选择是：{ok}')
                        if ok == QMessageBox.StandardButton.Yes:
                            english_title = chinese_name_to_pinyin(original_title)
                        if not re.match(english_pattern, english_title):
                            print('first_english_name does not match the english_pattern.')
                            if ok == QMessageBox.StandardButton.Yes:
                                QMessageBox.warning(widget, '警告', '资源名称不是汉语，无法使用汉语拼音')
                            text, ok = QInputDialog.getText(self, '输入资源的英文名称',
                                                            'PT-Gen未检测到英文名称，请注意使用英文标点符号')
                            if ok:
                                print(f'您输入的数据为：{text}')
                                self.debugBrowserPlaylet.append(f'您输入的数据为：{text}')
                                english_title = text.replace('.', ' ')
                                invalid_characters = ''
                                for char in english_title:
                                    if not re.match(english_pattern, char):
                                        invalid_characters += char
                                print('不匹配的字符：', invalid_characters)
                                if invalid_characters != '':
                                    QMessageBox.warning(widget, '警告',
                                                        f'您输入的英文名称包含非英文字符或符号\n有以下这些：'
                                                        f'{"|".join(invalid_characters)}\n请重新核对后再生成标准命名')
                                    return
                            else:
                                print('未输入任何数据')
                                self.debugBrowserPlaylet.append('未输入任何数据')
                                english_title = ''
                else:
                    if not re.match(english_pattern, original_title):
                        english_title = chinese_name_to_pinyin(original_title)
                        if not re.match(english_pattern, english_title):
                            self.debugBrowserPlaylet.append('缺少英文名称，并且无法生成汉语拼音，请手动获取名称')
                            return
                year = self.yearEditPlaylet.text()
                season = self.seasonBoxPlaylet.text()
                episodes_start_number = validate_and_convert_to_int(self.episodesStartBoxTV.text(),
                                                                    'episodes_start_number')
                season_number = season
                if len(season) < 2:
                    season = f'0{season}'

                video_format, video_codec, bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num, playlet_source = (
                    '', '', '', '', '', '', '', '', '')
                path = self.videoPathPlaylet.text().replace('file:///', '')

                is_video_path, response = check_path_and_find_video(path)  # 获取视频的路径
                if is_video_path == 2:  # 视频路径是文件夹
                    video_path = response
                    get_video_files_success, response = get_video_files(path)  # 获取文件夹内部的所有文件
                    if get_video_files_success:
                        video_files = response
                        print(f'文件夹内检测到以下文件：{str(video_files)}')
                        self.debugBrowserPlaylet.append(f'文件夹内检测到以下文件：{str(video_files)}')
                        episodes_num = len(video_files)  # 获取视频文件的总数
                    else:
                        print(f'文件夹内获取视频文件失败：{response}')
                        self.debugBrowserPlaylet.append(f'文件夹内获取视频文件失败：{response}')
                        return

                    # 生成总集数信息
                    if episodes_start_number == 1 and episodes_num != 1:
                        total_episodes = f'全{str(episodes_num)}集'
                    else:
                        if episodes_num == 1:
                            total_episodes = f'第{str(episodes_start_number)}集'
                        else:
                            total_episodes = f'第{str(episodes_start_number)}-{str(episodes_start_number + episodes_num - 1)}集'
                    print(f'总集数信息：{total_episodes}')

                    get_video_info_success, response = get_video_info(video_path)  # 通过视频获取视频的MI参数
                    if get_video_info_success:
                        video_info = response
                        self.debugBrowserPlaylet.append(f'获取到关键参数：{str(video_info)}')
                        video_format += video_info[0]
                        video_codec += video_info[1]
                        bit_depth += video_info[2]
                        hdr_format += video_info[3]
                        frame_rate += video_info[4]
                        audio_codec += video_info[5]
                        channels += video_info[6]
                        audio_num += video_info[7]
                    source = self.sourcePlaylet.currentText()
                    team = self.teamPlaylet.currentText()
                    playlet_source += self.playletSource.currentText()
                    print('收费类型、来源和小组参数获取成功')
                    self.debugBrowserPlaylet.append('收费类型、来源和小组参数获取成功')
                    categories = self.get_categories()
                    print(f'类型为：{categories}')
                    self.debugBrowserPlaylet.append(f'类型为：{categories}')
                    print('关键参数赋值成功，开始获取标准命名')
                    self.debugBrowserPlaylet.append('关键参数赋值成功，开始获取标准命名')
                    main_title = get_name_from_template(english_title, original_title, season, '', year,
                                                        video_format, source, video_codec, bit_depth, hdr_format,
                                                        frame_rate, audio_codec, channels, audio_num, team, '',
                                                        season_number, total_episodes, playlet_source, categories,
                                                        '', 'main_title_playlet')
                    print(f'main_title: {main_title}')
                    second_title = get_name_from_template(english_title, original_title, season, '', year,
                                                          video_format, source, video_codec, bit_depth, hdr_format,
                                                          frame_rate, audio_codec, channels, audio_num, team,
                                                          '', season_number, total_episodes, playlet_source,
                                                          categories, '', 'second_title_playlet')
                    print(f'second_title: {second_title}')
                    # NPC我要跟你谈恋爱 | 全95集 | 2023年 | 网络收费短剧 | 类型：剧集 爱情
                    file_name = get_name_from_template(english_title, original_title, season, '{集数}', year,
                                                       video_format, source, video_codec, bit_depth, hdr_format,
                                                       frame_rate, audio_codec, channels, audio_num, team, '',
                                                       season_number, total_episodes, playlet_source, categories,
                                                       '', 'file_name_playlet')
                    print(f'file_name: {file_name}')
                    if second_confirm_file_name:
                        text, ok = QInputDialog.getText(self, '确认',
                                                        '请确认文件名称，如有问题请修改（{集数}表示集数，请勿删除）',
                                                        QLineEdit.EchoMode.Normal, file_name)
                        if ok:
                            print(f'您确认文件名为：{text}')
                            self.debugBrowserPlaylet.append(f'您确认文件名为：{text}')
                            file_name = text
                        else:
                            print('您点了取消确认，重命名已取消')
                            self.debugBrowserPlaylet.append('您点了取消确认，重命名已取消')
                            return
                    if is_filename_too_long(file_name):
                        text, ok = QInputDialog.getText(self, '警告', '文件名过长，请修改文件名称！',
                                                        QLineEdit.EchoMode.Normal, file_name)
                        if ok:
                            print(f'您修改文件名为：{text}')
                            self.debugBrowserPlaylet.append(f'您修改文件名为：{text}')
                            file_name = text
                        else:
                            print('您点了取消确认，重命名已取消')
                            self.debugBrowserPlaylet.append('您点了取消确认，重命名已取消')
                            return
                        if is_filename_too_long(file_name):
                            widget = QWidget(self)
                            QMessageBox.warning(widget, '警告', '您输入的文件名过长，请重新核对后再生成标准命名！')
                            self.debugBrowserPlaylet.append('您输入的文件名过长，请重新核对后再生成标准命名！')
                            return
                    print(f'最终确认文件名是：{file_name}')
                    self.mainTitleBrowserPlaylet.setText(main_title)
                    self.secondTitleBrowserPlaylet.setText(second_title)
                    self.fileNameBrowserPlaylet.setText(file_name)

                    if do_create_hard_link:
                        print('开始创建硬链接')
                        create_hard_link_success, response = create_hard_link(path)
                        if create_hard_link_success:
                            path = response
                            self.videoPathPlaylet.setText(path)
                            self.debugBrowserPlaylet.append(f'创建硬链接成功：{path}')
                            is_video_path, response = check_path_and_find_video(path)
                            if is_video_path == 2:
                                get_video_files_success, response = get_video_files(path)  # 获取文件夹内部的所有文件
                                if get_video_files_success:
                                    video_files = response
                                    print(f'文件夹内检测到以下文件：{str(video_files)}')
                                    self.debugBrowserPlaylet.append(f'文件夹内检测到以下文件：{str(video_files)}')
                                else:
                                    print(f'文件夹内获取视频文件失败：{response}')
                                    self.debugBrowserPlaylet.append(f'文件夹内获取视频文件失败：{response}')
                                    return
                        else:
                            self.debugBrowserPlaylet.append(f'您选择创建硬链接，但是创建失败了：{response}')
                            return

                    if do_rename_file:
                        print('对文件重新命名')
                        self.debugBrowserPlaylet.append('开始对文件重新命名')
                        i = episodes_start_number
                        for video_file in video_files:
                            e = str(i)
                            while len(e) < len(str(episodes_start_number + episodes_num - 1)):
                                e = f'0{e}'
                            if len(e) == 1:
                                e = f'0{e}'
                            rename_file_success, response = rename_file(video_file, file_name.replace('{集数}', e))

                            if rename_file_success:
                                video_file = response
                                self.debugBrowserPlaylet.append(f'视频成功重新命名为：{video_file}')
                            else:
                                self.debugBrowserPlaylet.append(f'重命名失败：{response}')
                            i += 1

                        print('对文件夹重新命名')
                        self.debugBrowserPlaylet.append('开始对文件夹重新命名')
                        rename_directory_success, response = rename_folder(path, file_name.
                                                                           replace('E{集数}', '').
                                                                           replace('{集数}', ''))
                        if rename_directory_success:
                            path = response
                            self.videoPathPlaylet.setText(path)
                            self.debugBrowserPlaylet.append(f'视频地址成功重新命名为：{path}')
                        else:
                            self.debugBrowserPlaylet.append(f'重命名失败：{response}')
                else:
                    self.debugBrowserPlaylet.append(f'您的视频文件路径有误：{response}')
            else:
                self.debugBrowserPlaylet.append('获取的中文名为空')
        except Exception as e:
            print(f'获取命名出错：{e}')
            return False, [f'获取命名出错：{e}']

    def make_torrent_button_playlet_clicked(self):
        self.torrent_url = ''
        is_video_path, response = check_path_and_find_video(
            self.videoPathPlaylet.text().replace('file:///', ''))  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            torrent_storage_path = str(get_settings('torrent_storage_path'))
            folder_path = os.path.dirname(video_path)
            self.debugBrowserPlaylet.append(f'开始将{folder_path}制作种子，储存在{torrent_storage_path}')
            self.make_torrent_thread = MakeTorrentThread(folder_path, torrent_storage_path)
            self.make_torrent_thread.result_signal.connect(self.handle_make_torrent_result_playlet)  # 连接信号
            self.make_torrent_thread.start()  # 启动线程
            self.debugBrowserPlaylet.append('制作种子线程启动成功，正在后台制作种子，请耐心等待种子制作完毕...')
        else:
            self.debugBrowserPlaylet.append(f'制作种子失败：{response}')

    def handle_make_torrent_result_playlet(self, get_success, response):
        if get_success:
            torrent_path = response
            self.torrent_url = f'http://127.0.0.1:{get_settings("api_port")}/api/getFile?filePath={torrent_path}'
            self.debugBrowserPlaylet.append(f'成功制作种子：{torrent_path}')
        else:
            self.debugBrowserPlaylet.append(f'制作种子失败：{response}')

    def get_categories(self):
        categories = ''
        if self.checkBox_0.isChecked():
            categories += '剧情 '
        if self.checkBox_1.isChecked():
            categories += '爱情 '
        if self.checkBox_2.isChecked():
            categories += '喜剧 '
        if self.checkBox_3.isChecked():
            categories += '甜虐 '
        if self.checkBox_4.isChecked():
            categories += '甜宠 '
        if self.checkBox_5.isChecked():
            categories += '恐怖 '
        if self.checkBox_6.isChecked():
            categories += '动作 '
        if self.checkBox_7.isChecked():
            categories += '穿越 '
        if self.checkBox_8.isChecked():
            categories += '重生 '
        if self.checkBox_9.isChecked():
            categories += '逆袭 '
        if self.checkBox_10.isChecked():
            categories += '科幻 '
        if self.checkBox_11.isChecked():
            categories += '武侠 '
        if self.checkBox_12.isChecked():
            categories += '都市 '
        if self.checkBox_13.isChecked():
            categories += '古装 '
        if self.checkBox_14.isChecked():
            categories += '神豪 '
        if self.checkBox_15.isChecked():
            categories += '霸总 '
        if categories != '':
            categories = categories[: -1]
            categories = categories.replace(' ', ' / ')
        return categories

    # 以上是Playlet页面的代码
    # 以下是Settings页面的代码


class settings(QDialog, Ui_Settings):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # 设置界面

        # 绑定点击信号和槽函数
        self.saveButton.clicked.connect(self.saveButtonClicked)
        self.cancelButton.clicked.connect(self.cancelButtonClicked)
        self.selectScreenshotPathButton.clicked.connect(self.selectScreenshotPathButtonClicked)
        self.selectTorrentPathButton.clicked.connect(self.selectTorrentPathButtonClicked)

    def saveButtonClicked(self):
        self.updateSettings()
        self.close()

    def cancelButtonClicked(self):
        self.close()

    def selectScreenshotPathButtonClicked(self):
        path = get_folder_path()
        if path != '':
            self.screenshotStoragePath.setText(path)

    def selectTorrentPathButtonClicked(self):
        path = get_folder_path()
        if path != '':
            self.torrentStoragePath.setText(path)

    def getSettings(self):
        self.screenshotStoragePath.setText(str(get_settings('screenshot_storage_path')))
        self.torrentStoragePath.setText(str(get_settings('torrent_storage_path')))
        self.ptGenApiUrl.setText(get_settings('pt_gen_api_url'))
        self.ptGenApiUrlBackup.setText(get_settings('pt_gen_api_url_backup'))
        self.personalizedSignature.setText(get_settings('personalized_signature'))
        self.pictureBedApiUrl.setText(get_settings('picture_bed_api_url'))
        self.pictureBedApiToken.setText(get_settings('picture_bed_api_token'))
        self.screenshotNumber.setValue(int(get_settings('screenshot_number')))
        self.screenshotThreshold.setValue(float(get_settings('screenshot_threshold')))
        self.screenshotStartPercentage.setValue(float(get_settings('screenshot_start_percentage')))
        self.screenshotEndPercentage.setValue(float(get_settings('screenshot_end_percentage')))
        self.doGetThumbnail.setChecked(bool(get_settings('do_get_thumbnail')))
        self.thumbnailRows.setValue(int(get_settings('thumbnail_rows')))
        self.thumbnailCols.setValue(int(get_settings('thumbnail_cols')))
        self.thumbnailDelay.setValue(float(get_settings('thumbnail_delay')))
        self.autoUploadScreenshot.setChecked(bool(get_settings('auto_upload_screenshot')))
        self.pasteScreenshotUrl.setChecked(bool(get_settings('paste_screenshot_url')))
        self.deleteScreenshot.setChecked(bool(get_settings('delete_screenshot')))
        self.autoDownloadUploadPoster.setChecked(bool(get_settings('auto_download_upload_poster')))
        self.mediaInfoSuffix.setChecked(bool(get_settings('media_info_suffix')))
        self.makeDir.setChecked(bool(get_settings('make_dir')))
        self.renameFile.setChecked(bool(get_settings('rename_file')))
        self.createHardLink.setChecked(bool(get_settings('create_hard_link')))
        self.secondConfirmFileName.setChecked(bool(get_settings('second_confirm_file_name')))
        self.enableApi.setChecked(bool(get_settings('enable_api')))
        self.apiPort.setValue(int(get_settings('api_port')))
        self.mainTitleMovie.setText(str(get_settings('main_title_movie')))
        self.secondTitleMovie.setText(str(get_settings('second_title_movie')))
        self.fileNameMovie.setText(str(get_settings('file_name_movie')))
        self.mainTitleTV.setText(str(get_settings('main_title_tv')))
        self.secondTitleTV.setText(str(get_settings('second_title_tv')))
        self.fileNameTV.setText(str(get_settings('file_name_tv')))
        self.mainTitlePlaylet.setText(str(get_settings('main_title_playlet')))
        self.secondTitlePlaylet.setText(str(get_settings('second_title_playlet')))
        self.fileNamePlaylet.setText(str(get_settings('file_name_playlet')))
        self.autoFeedLink.setText(str(get_settings('auto_feed_link')))
        self.openAutoFeedLink.setChecked(bool(get_settings('open_auto_feed_link')))

    def updateSettings(self):
        update_settings('screenshot_storage_path', self.screenshotStoragePath.text())
        update_settings('torrent_storage_path', self.torrentStoragePath.text())
        update_settings('pt_gen_api_url', self.ptGenApiUrl.text())
        update_settings('pt_gen_api_url_backup', self.ptGenApiUrlBackup.text())
        update_settings('personalized_signature', self.personalizedSignature.text())
        update_settings('picture_bed_api_url', self.pictureBedApiUrl.text())
        update_settings('picture_bed_api_token', self.pictureBedApiToken.text())
        update_settings('screenshot_number', str(self.screenshotNumber.text()))
        # Fix locale issue: QDoubleSpinBox may use comma on macOS, replace with dot for JSON
        update_settings('screenshot_threshold', str(self.screenshotThreshold.text()).replace(',', '.'))
        update_settings('screenshot_start_percentage', str(self.screenshotStartPercentage.text()).replace(',', '.'))
        update_settings('screenshot_end_percentage', str(self.screenshotEndPercentage.text()).replace(',', '.'))
        if self.doGetThumbnail.isChecked():
            update_settings('do_get_thumbnail', 'True')
        else:
            update_settings('do_get_thumbnail', '')
        update_settings('thumbnail_rows', str(self.thumbnailRows.text()))
        update_settings('thumbnail_cols', str(self.thumbnailCols.text()))
        # Fix locale issue: QDoubleSpinBox may use comma on macOS, replace with dot for JSON
        update_settings('thumbnail_delay', str(self.thumbnailDelay.text()).replace(',', '.'))
        if self.autoUploadScreenshot.isChecked():
            update_settings('auto_upload_screenshot', 'True')
        else:
            update_settings('auto_upload_screenshot', '')
        if self.pasteScreenshotUrl.isChecked():
            update_settings('paste_screenshot_url', 'True')
        else:
            update_settings('paste_screenshot_url', '')
        if self.deleteScreenshot.isChecked():
            update_settings('delete_screenshot', 'True')
        else:
            update_settings('delete_screenshot', '')
        if self.autoDownloadUploadPoster.isChecked():
            update_settings('auto_download_upload_poster', 'True')
        else:
            update_settings('auto_download_upload_poster', '')
        if self.mediaInfoSuffix.isChecked():
            update_settings('media_info_suffix', 'True')
        else:
            update_settings('media_info_suffix', '')
        if self.makeDir.isChecked():
            update_settings('make_dir', 'True')
        else:
            update_settings('make_dir', '')
        if self.renameFile.isChecked():
            update_settings('rename_file', 'True')
        else:
            update_settings('rename_file', '')
        if self.createHardLink.isChecked():
            update_settings('create_hard_link', 'True')
        else:
            update_settings('create_hard_link', '')
        if self.secondConfirmFileName.isChecked():
            update_settings('second_confirm_file_name', 'True')
        else:
            update_settings('second_confirm_file_name', '')
        if self.enableApi.isChecked():
            update_settings('enable_api', 'True')
        else:
            update_settings('enable_api', '')
        update_settings('api_port', self.apiPort.text())
        update_settings('main_title_movie', self.mainTitleMovie.text())
        update_settings('second_title_movie', self.secondTitleMovie.text())
        update_settings('file_name_movie', self.fileNameMovie.text())
        update_settings('main_title_tv', self.mainTitleTV.text())
        update_settings('second_title_tv', self.secondTitleTV.text())
        update_settings('file_name_tv', self.fileNameTV.text())
        update_settings('main_title_playlet', self.mainTitlePlaylet.text())
        update_settings('second_title_playlet', self.secondTitlePlaylet.text())
        update_settings('file_name_playlet', self.fileNamePlaylet.text())
        update_settings('auto_feed_link', self.autoFeedLink.toPlainText())
        if self.openAutoFeedLink.isChecked():
            update_settings('open_auto_feed_link', 'True')
        else:
            update_settings('open_auto_feed_link', '')

    # 以上是Settings页面的代码
    # 以下是多线程的代码


class GetPtGenThread(QThread):
    # 创建一个信号，用于在数据处理完毕后与主线程通信
    # 第三个参数为JSON序列化的原始API响应数据
    result_signal = pyqtSignal(bool, str, str)

    def __init__(self, api_url, resource_url):
        super().__init__()
        self.api_url = api_url
        self.resource_url = resource_url

    def run(self):
        try:
            import json as _json
            # 这里放置耗时的HTTP请求操作
            get_pt_gen_description_success, response = get_pt_gen_description(self.api_url, self.resource_url)

            # 发送信号，包括请求的结果
            print('PT-Gen请求成功，开始返回结果')
            if get_pt_gen_description_success:
                # response is now (format_data, full_data)
                format_data, full_data = response
                # 将原始数据序列化为JSON字符串通过信号传递
                try:
                    raw_data_json = _json.dumps(full_data, ensure_ascii=False)
                except Exception:
                    raw_data_json = ''
                self.result_signal.emit(get_pt_gen_description_success, format_data, raw_data_json)
            else:
                self.result_signal.emit(get_pt_gen_description_success, response, '')
            print('返回结果成功')
        except Exception as e:
            print(f'异常发生：{e}')
            # 这里可以发射一个包含错误信息的信号


class UploadPictureThread(QThread):
    # 创建一个信号，用于在数据处理完毕后与主线程通信
    result_signal = pyqtSignal(bool, str, str, bool, bool)

    def __init__(self, picture_bed_api_path, picture_bed_api_token, picture_path, is_cover, is_thumbnail):
        super().__init__()
        self.picture_bed_api_path = picture_bed_api_path
        self.picture_bed_api_token = picture_bed_api_token
        self.picture_path = picture_path
        self.is_cover = is_cover
        self.is_thumbnail = is_thumbnail
        print('上传图床初始化完成')

    def run(self):
        try:
            if self.is_thumbnail:
                time.sleep(float(get_settings('thumbnail_delay')))  # 等待
            # 这里放置耗时的HTTP请求操作
            upload_picture_success, response = upload_picture(self.picture_bed_api_path, self.picture_bed_api_token,
                                                              self.picture_path)

            # 发送信号，包括请求的结果
            print('上传图床成功，开始返回结果')
            self.result_signal.emit(upload_picture_success, response, self.picture_path, self.is_cover,
                                    self.is_thumbnail)
            print('返回结果成功')
        except Exception as e:
            print(f'异常发生：{e}')
            self.result_signal.emit(False, f'异常发生：{e}', self.picture_path, self.is_cover, self.is_thumbnail)
            # 这里可以发射一个包含错误信息的信号


class MakeTorrentThread(QThread):
    # 创建一个信号，用于在数据处理完毕后与主线程通信
    result_signal = pyqtSignal(bool, str)

    def __init__(self, path, torrent_storage_path):
        super().__init__()
        self.path = path
        self.torrent_storage_path = torrent_storage_path

    def run(self):
        try:
            # 这里放置耗时的制作torrent操作
            make_torrent_success, response = make_torrent(self.path, self.torrent_storage_path)

            # 发送信号
            print('Torrent请求成功，开始等待返回结果')
            self.result_signal.emit(make_torrent_success, response)
            print('返回结果成功')
        except Exception as e:
            print(f'异常发生：{e}')
            # 这里可以发射一个包含错误信息的信号


class WaitForRenameThread(QThread):
    # 创建一个信号，用于在数据处理完毕后与主线程通信
    result_signal = pyqtSignal(bool)

    def __init__(self, is_movie):
        super().__init__()
        self.is_movie = is_movie

    def run(self):
        try:
            if self.is_movie:
                # 这里放置耗时的等待操作
                global get_name_movie_success, get_name_movie_failure_number
                wait_time = 0  # 已经等待的时间
                while get_name_movie_success is False and get_name_movie_failure_number <= 1 and wait_time <= 60:
                    print('重命名尚未完成，等待0.5s')
                    time.sleep(0.5)
                    wait_time += 0.5

                # 发送信号
                print('等待重命名结束，开始返回结果')
                self.result_signal.emit(get_name_movie_success)
                print('返回结果成功')
            else:
                # 这里放置耗时的等待操作
                global get_name_tv_success, get_name_tv_failure_number
                wait_time = 0  # 已经等待的时间
                while get_name_tv_success is False and get_name_tv_failure_number <= 1 and wait_time <= 60:
                    print('重命名尚未完成，等待0.5s')
                    time.sleep(0.5)
                    wait_time += 0.5

                # 发送信号
                print('等待重命名结束，开始返回结果')
                self.result_signal.emit(get_name_tv_success)
                print('返回结果成功')

        except Exception as e:
            print(f'异常发生：{e}')
            # 这里可以发射一个包含错误信息的信号


class apiThread(QThread):
    # 创建一个信号，用于在数据处理完毕后与主线程通信
    result_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            print('尝试启动API')
            start_api()
            print('API线程终止')
            self.result_signal.emit('API线程终止')
        except Exception as e:
            print(f'异常发生：{e}')
            self.result_signal.emit(f'异常发生：{e}')
