from qfluentwidgets import QConfig,ConfigItem,BoolValidator,FolderValidator,RangeConfigItem,RangeValidator,Theme,qconfig
from .utils import Utils

class AppConfig(QConfig):
    micaEnabled = ConfigItem("global", "MicaEnabled", Utils.isWin11(), BoolValidator())

    player_play_single_loop = ConfigItem("player", "play_single_loop", False, BoolValidator())
    player_play_single_track = ConfigItem("player", "play_single_track", False, BoolValidator())
    midi_folder = ConfigItem("player", "midi_folder", str(Utils.app_path("resources/midi")), FolderValidator())
    player_play_delay_time = RangeConfigItem("player", "delay_time", 0, RangeValidator(0, 40))
    player_play_press_delay = RangeConfigItem("player", "press_delay", 2, RangeValidator(0, 50))
    player_play_disable_note_fitting = ConfigItem("player", "play_disable_note_fitting", False, BoolValidator())

cfg = AppConfig()
cfg.themeMode.value = Theme.AUTO
qconfig.load(str(Utils.app_path("resources/app_config.json")), cfg)