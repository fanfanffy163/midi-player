# coding:utf-8
from qfluentwidgets import (SettingCardGroup, SwitchSettingCard, OptionsSettingCard, PushSettingCard,
                            ScrollArea,
                            ExpandLayout, CustomColorSettingCard,
                            setTheme, setThemeColor, RangeSettingCard)
from qfluentwidgets import FluentIcon as FIF
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QFileDialog
from ...utils.utils import Utils
from ...utils.config import cfg
from ...utils.style_sheet import StyleSheet
import pydirectinput

class SettingPage(ScrollArea):
    """ Setting interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setObjectName("SettingPage")
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)
        # setting label
        self.settingLabel = QLabel('设置', self)

        # personalization
        self.personalGroup = SettingCardGroup(
            "个性化", self.scrollWidget)
        # self.micaCard = SwitchSettingCard(
        #     FIF.TRANSPARENT,
        #     '云母效果',
        #     '在支持的Windows系统上启用云母效果',
        #     cfg.micaEnabled,
        #     self.personalGroup
        # )
        self.themeCard = OptionsSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            '应用主题',
            '调整你的应用的外观',
            texts=['浅色', '深色', '跟随系统设置'],
            parent=self.personalGroup
        )
        self.themeColorCard = CustomColorSettingCard(
            cfg.themeColor,
            FIF.PALETTE,
            '主题颜色',
            '调整你的应用的主题色',
            self.personalGroup
        )

        # app
        self.appGroup = SettingCardGroup(
            '应用设置', self.scrollWidget)
        self.singleLoopCard = SwitchSettingCard(
            FIF.SPEAKERS,
            '单曲循环',
            '循环播放当前曲目',
            cfg.player_play_single_loop,
            self.appGroup
        )
        self.singleTraceCard = SwitchSettingCard(
            FIF.TRAIN,
            '单轨播放',
            '只选取主音轨进行播放(已播放歌曲重新播放后生效)',
            cfg.player_play_single_track,
            self.appGroup
        )
        self.midiFolderCard = PushSettingCard(
            '选择文件夹',
            FIF.FOLDER,
            'MIDI文件路径，可以是多个midi目录的根路径',
            cfg.get(cfg.midi_folder),
            self.appGroup
        )
        self.playDelayCard = RangeSettingCard(
            cfg.player_play_delay_time,
            FIF.ALBUM,
            '播放延迟时间',
            '每首歌和下一首歌播放中间的延时，秒级单位',
            self.appGroup
        )
        self.pressDelayCard = RangeSettingCard(
            cfg.player_play_press_delay,
            FIF.AIRPLANE,
            '按键延迟时间',
            '两个按键之间的延迟，单位为毫秒',
            self.appGroup
        )
        self.disableNoteFittingCard = SwitchSettingCard(
            FIF.DICTIONARY,
            '原始音符播放',
            '开启配置后将不会自动升高或降低音高牺牲音质确保最高命中率，建议在预设信息比较完善时开启',
            cfg.player_play_disable_note_fitting,
            self.appGroup
        )
        self.__initWidget()

    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_PAGE.apply(self)
        #self.micaCard.setEnabled(Utils.isWin11())

        # initialize layout
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.settingLabel.move(36, 30)

        #self.personalGroup.addSettingCard(self.micaCard)
        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.themeColorCard)
        
        self.appGroup.addSettingCards([self.singleLoopCard,self.singleTraceCard,self.midiFolderCard,self.playDelayCard,self.pressDelayCard,self.disableNoteFittingCard])

        # add setting card group to layout
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.personalGroup)
        self.expandLayout.addWidget(self.appGroup)

    def __onMidiFolderCardClicked(self):
        """ download folder card clicked slot """
        folder = QFileDialog.getExistingDirectory(
            self, '选择文件夹', "./")
        if not folder or cfg.get(cfg.midi_folder) == folder:
            return

        cfg.set(cfg.midi_folder, folder)
        self.midiFolderCard.setContent(folder)

    def _on_press_delay_change(self,time):
        pydirectinput.PAUSE = time / 1000

    def __connectSignalToSlot(self):
        # personalization
        cfg.themeChanged.connect(setTheme)
        cfg.themeColorChanged.connect(setThemeColor)
        cfg.player_play_delay_time.valueChanged.connect(self._on_press_delay_change)

        #app
        self.midiFolderCard.clicked.connect(self.__onMidiFolderCardClicked)

