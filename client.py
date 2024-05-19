import atexit
import json
import os
import pathlib
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from sys import executable
from threading import Thread
from typing import Any, Coroutine
from xmlrpc.client import ServerProxy

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.events import Event, ScreenResume
from textual.screen import Screen
from textual.widgets import (Button, Checkbox, Footer, Header, Input, Label,
                             LoadingIndicator, Log, Markdown, Pretty, Rule,
                             Digits, Static)

from action import Action
from liqi import LiqiProto, MsgType
from majsoul2mjai import MajsoulBridge
from libriichi_helper import meta_to_recommend, state_to_tehai
from tileUnicode import (TILE_2_UNICODE_ART_RICH, TILE_2_UNICODE, HAI_VALUE,
                        VERTICAL_RULE, EMPTY_VERTICAL_RULE, TILE_LIST)

submission = 'players/bot.zip'
PORT_NUM = 28680
AUTOPLAY = False
OVERLAY = False
ENABLE_PLAYWRIGHT = False
with open("settings.json", "r") as f:
    settings = json.load(f)
    PORT_NUM = settings["Port"]["MJAI"]
    AUTOPLAY = settings["Autoplay"]
    OVERLAY = settings["Overlay"]
    ENABLE_PLAYWRIGHT = settings["Playwright"]["enable"]


class Recommandation(Horizontal):
    def __init__(self, recommand_idx: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.recommand_idx = recommand_idx

    def compose(self) -> ComposeResult:
        self.action = Button("Akagi", classes="action_none recommand_button", variant="default") # 10
        self.pai = Label(TILE_2_UNICODE_ART_RICH["?"])                          # 8
        self.vertical_rule = Label(EMPTY_VERTICAL_RULE)                         # 1
        self.consumes = [Label(TILE_2_UNICODE_ART_RICH["?"]) for _ in range(3)] # 8*3
        self.action_container = Horizontal(self.action, self.pai, self.vertical_rule, *self.consumes, classes="action_container")
        self.weight = Digits("0.0", classes="recommand_digit")

        yield self.action_container
        yield self.weight

    def update(self, mjai_msg, state):
        if len(mjai_msg['meta']) <= self.recommand_idx:
            self.action.label = "Akagi"
            self.action.add_class("action_none")
            self.pai.update(TILE_2_UNICODE_ART_RICH["?"])
            self.vertical_rule.update(EMPTY_VERTICAL_RULE)
            for i in range(3):
                self.consumes[i].update(TILE_2_UNICODE_ART_RICH["?"])
            self.weight.update("0.0")
            self.app.rpc_server.draw_top3([self.recommand_idx, "?", "?", "?", "?", 0.0])
            return
        recommand = mjai_msg['meta'][self.recommand_idx]
        for action_class in self.action.classes:
            if "action_" in action_class:
                self.action.remove_class(action_class)
        self.weight.update(f"{(recommand[1]*100):.2f}")
        weight_text = f"{(recommand[1]*100):.2f}%"
        if recommand[0] in TILE_LIST:
            self.action.label = recommand[0]
            self.action.add_class("action_"+recommand[0])
            self.pai.update(TILE_2_UNICODE_ART_RICH[recommand[0]])
            self.vertical_rule.update(EMPTY_VERTICAL_RULE)
            for i in range(3):
                self.consumes[i].update(TILE_2_UNICODE_ART_RICH["?"])
            self.app.rpc_server.draw_top3([self.recommand_idx, recommand[0], "?", "?", "?", weight_text])
        elif recommand[0] in ['chi_low', 'chi_mid', 'chi_high']:
            self.action.label = "chi"
            self.action.add_class("action_chi")
            last_kawa_tile = state.last_kawa_tile()
            self.pai.update(TILE_2_UNICODE_ART_RICH[last_kawa_tile])
            self.vertical_rule.update(VERTICAL_RULE)
            last_kawa_tile_idx = TILE_LIST.index(last_kawa_tile)
            match recommand[0]:
                case 'chi_low':
                    c0 = TILE_LIST[last_kawa_tile_idx+1]
                    c1 = TILE_LIST[last_kawa_tile_idx+2]
                case 'chi_mid':
                    c0 = TILE_LIST[last_kawa_tile_idx-1]
                    c1 = TILE_LIST[last_kawa_tile_idx+1]
                case 'chi_high':
                    c0 = TILE_LIST[last_kawa_tile_idx-2]
                    c1 = TILE_LIST[last_kawa_tile_idx-1]
            self.consumes[0].update(TILE_2_UNICODE_ART_RICH[c0])
            self.consumes[1].update(TILE_2_UNICODE_ART_RICH[c1])
            self.consumes[2].update(TILE_2_UNICODE_ART_RICH["?"])
            self.app.rpc_server.draw_top3([self.recommand_idx, "chi", last_kawa_tile, c0, c1, weight_text])
        elif recommand[0] in ['pon']:
            self.action.label = "pon"
            self.action.add_class("action_pon")
            last_kawa_tile = state.last_kawa_tile()
            self.pai.update(TILE_2_UNICODE_ART_RICH[last_kawa_tile])
            self.vertical_rule.update(VERTICAL_RULE)
            for i in range(2):
                self.consumes[i].update(TILE_2_UNICODE_ART_RICH[last_kawa_tile])
            self.consumes[2].update(TILE_2_UNICODE_ART_RICH["?"])
            self.app.rpc_server.draw_top3([self.recommand_idx, "pon", last_kawa_tile, last_kawa_tile, last_kawa_tile, weight_text])
        elif recommand[0] in ['kan_select']:
            # The recommandation only shows kan_select, but not ['daiminkan', 'ankan', 'kakan'],
            # this is due to the Mortal model structure limitations.
            # We can only know the model wants to do a kan.
            self.action.label = "kan"
            self.action.add_class("action_kakan") # We don't know which kan it is, so we just use kakan as a placeholder.
            self.pai.update(TILE_2_UNICODE_ART_RICH["?"])
            self.vertical_rule.update(EMPTY_VERTICAL_RULE)
            for i in range(3):
                self.consumes[i].update(TILE_2_UNICODE_ART_RICH["?"])
            self.app.rpc_server.draw_top3([self.recommand_idx, "kan", "?", "?", "?", weight_text])
        elif recommand[0] in ['reach', 'hora', 'ryukyoku', 'none']:
            self.action.label = recommand[0]
            self.action.add_class("action_"+recommand[0])
            self.pai.update(TILE_2_UNICODE_ART_RICH["?"])
            self.vertical_rule.update(EMPTY_VERTICAL_RULE)
            for i in range(3):
                self.consumes[i].update(TILE_2_UNICODE_ART_RICH["?"])
            self.app.rpc_server.draw_top3([self.recommand_idx, recommand[0], "?", "?", "?", weight_text])
        elif recommand[0] in ['nukidora']:
            self.action.label = "nukidora"
            self.action.add_class("action_nukidora")
            self.pai.update(TILE_2_UNICODE_ART_RICH["N"])
            self.vertical_rule.update(EMPTY_VERTICAL_RULE)
            for i in range(3):
                self.consumes[i].update(TILE_2_UNICODE_ART_RICH["?"])
            self.app.rpc_server.draw_top3([self.recommand_idx, "nukidora", "N", "?", "?", weight_text])
        pass


class FlowScreen(Screen):

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, flow_id, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.flow_id = flow_id
        self.liqi_msg_idx = 0
        self.mjai_msg_idx = 0
        self.consume_ids = []
        self.latest_operation_list = None
        self.syncing = True
        self.action = Action(self.app.rpc_server)
        self.isLiqi = False
        self.dahai_verfication_job = None

    def compose(self) -> ComposeResult:
        """Called to add widgets to the app."""
        # liqi_log_container = ScrollableContainer(Pretty(self.app.liqi_msg_dict[self.flow_id], id="liqi_log"), id="liqi_log_container")
        recommandations = [Recommandation(i, classes="recommandations", id="recommandation_"+str(i)) for i in range(3)]
        recommandations_container = Vertical(*recommandations, id="recommandations_container")
        mjai_log_container = ScrollableContainer(Pretty(self.app.mjai_msg_dict[self.flow_id], id="mjai_log"), id="mjai_log_container")
        log_container = Horizontal(recommandations_container, mjai_log_container, id="log_container")
        recommandations_container.border_title = "Recommandations"
        mjai_log_container.border_title = "Mjai"
        tehai_labels = [Label(TILE_2_UNICODE_ART_RICH["?"], id="tehai_"+str(i)) for i in range(13)]
        # tehai_value_labels = [Label(HAI_VALUE[40], id="tehai_value_"+str(i)) for i in range(13)]
        tehai_rule = Label(VERTICAL_RULE, id="tehai_rule")
        tsumohai_label = Label(TILE_2_UNICODE_ART_RICH["?"], id="tsumohai")
        # tsumohai_value_label = Label(HAI_VALUE[40], id="tsumohai_value")
        tehai_container = Horizontal(id="tehai_container")
        for i in range(13):
            tehai_container.mount(tehai_labels[i])
            # tehai_container.mount(tehai_value_labels[i])
        tehai_container.mount(tehai_rule)
        tehai_container.mount(tsumohai_label)
        # tehai_container.mount(tsumohai_value_label)
        tehai_container.border_title = "Tehai"
        akagi_action = Button("Akagi", id="akagi_action", variant="default")
        akagi_pai    = Button("Pai", id="akagi_pai", variant="default")
        pai_unicode_art = Label(TILE_2_UNICODE_ART_RICH["?"], id="pai_unicode_art")
        vertical_rule = Label(EMPTY_VERTICAL_RULE, id="vertical_rule")
        consumed_pais = [Label(TILE_2_UNICODE_ART_RICH["?"], id="consumed_"+str(i)) for i in range(3)]
        akagi_container = Horizontal(akagi_action, akagi_pai, pai_unicode_art, vertical_rule, 
                                     consumed_pais[0], consumed_pais[1], consumed_pais[2], id="akagi_container")
        akagi_container.border_title = "Akagi"
        loading_indicator = LoadingIndicator(id="loading_indicator")
        loading_indicator.styles.height = "3"
        checkbox_autoplay = Checkbox("Autoplay", id="checkbox_autoplay", classes="short", value=AUTOPLAY)
        checkbox_overlay = Checkbox("Overlay ", id="checkbox_overlay", classes="short", value=OVERLAY)
        checkbox_test_one = Checkbox("test_one", id="checkbox_test_one", classes="short")
        checkbox_container = Vertical(checkbox_autoplay, checkbox_overlay, id="checkbox_container")
        checkbox_container.border_title = "Options"
        bottom_container = Horizontal(checkbox_container, akagi_container, id="bottom_container")
        yield Header()
        yield Footer()
        yield loading_indicator
        yield log_container
        yield tehai_container
        yield bottom_container

    def on_mount(self) -> None:
        # self.liqi_log = self.query_one("#liqi_log")
        self.mjai_log = self.query_one("#mjai_log")
        self.akagi_action = self.query_one("#akagi_action")
        self.akagi_pai = self.query_one("#akagi_pai")
        self.pai_unicode_art = self.query_one("#pai_unicode_art")
        self.vertical_rule = self.query_one("#vertical_rule")
        self.consumed_pais = [self.query_one("#consumed_"+str(i)) for i in range(3)]
        self.akagi_container = self.query_one("#akagi_container")
        # self.liqi_log.update(self.app.liqi_msg_dict[self.flow_id])
        self.mjai_log.update(self.app.mjai_msg_dict[self.flow_id])
        # self.liqi_log_container = self.query_one("#liqi_log_container")
        self.recommandations_container = self.query_one("#recommandations_container")
        self.mjai_log_container = self.query_one("#mjai_log_container")
        self.tehai_labels = [self.query_one("#tehai_"+str(i)) for i in range(13)]
        # self.tehai_value_labels = [self.query_one("#tehai_value_"+str(i)) for i in range(13)]
        self.tehai_rule = self.query_one("#tehai_rule")
        self.tsumohai_label = self.query_one("#tsumohai")
        # self.tsumohai_value_label = self.query_one("#tsumohai_value")
        self.tehai_container = self.query_one("#tehai_container")
        # self.liqi_log_container.scroll_end(animate=False)
        self.mjai_log_container.scroll_end(animate=False)
        self.liqi_msg_idx = len(self.app.liqi_msg_dict[self.flow_id])
        self.mjai_msg_idx = len(self.app.mjai_msg_dict[self.flow_id])
        self.update_log = self.set_interval(0.10, self.refresh_log)
        try:
            self.akagi_action.label = self.app.mjai_msg_dict[self.flow_id][-1]["type"]
            for akagi_action_class in self.akagi_action.classes:
                self.akagi_action.remove_class(akagi_action_class)
            self.akagi_action.add_class("action_"+self.app.mjai_msg_dict[self.flow_id][-1]["type"])
            for akagi_pai_class in self.akagi_pai.classes:
                self.akagi_pai.remove_class(akagi_pai_class)
            self.akagi_pai.add_class("pai_"+self.app.mjai_msg_dict[self.flow_id][-1]["type"])
        except IndexError:
            self.akagi_action.label = "Akagi"

        if OVERLAY:
            self.app.rpc_server.start_overlay_action()

    def refresh_log(self) -> None:
        try:
            if self.flow_id not in self.app.liqi_msg_dict:
                self.action_quit()
            if self.liqi_msg_idx < len(self.app.liqi_msg_dict[self.flow_id]):
                # self.liqi_log.update(self.app.liqi_msg_dict[self.flow_id][-1])
                # self.liqi_log_container.scroll_end(animate=False)
                self.liqi_msg_idx += 1
                liqi_msg = self.app.liqi_msg_dict[self.flow_id][-1]
                if liqi_msg['type'] == MsgType.Notify:
                    if liqi_msg['method'] == '.lq.ActionPrototype':
                        if 'operation' in liqi_msg['data']['data']:
                            if 'operationList' in liqi_msg['data']['data']['operation']:
                                self.action.latest_operation_list = liqi_msg['data']['data']['operation']['operationList']
                        if liqi_msg['data']['name'] == 'ActionDiscardTile':
                            self.action.isNewRound = False
                            if liqi_msg['data']['data']['isLiqi']:
                                self.isLiqi = True
                            pass
                        if liqi_msg['data']['name'] == 'ActionNewRound':
                            self.action.isNewRound = True
                            self.action.reached = False
                        # No matter what the action is, as long as we get a new action, we should stop the verification job as it's outdated.
                        if self.dahai_verfication_job is not None:
                            self.dahai_verfication_job.stop()
                            self.dahai_verfication_job = None
                    if liqi_msg['method'] == '.lq.NotifyGameEndResult' or liqi_msg['method'] == '.lq.NotifyGameTerminate':
                        self.action_quit()
            
            elif self.syncing:
                self.query_one("#loading_indicator").remove()
                self.syncing = False
                if AUTOPLAY and len(self.app.mjai_msg_dict[self.flow_id]) > 0:
                    self.app.set_timer(2, self.autoplay)
            if self.mjai_msg_idx < len(self.app.mjai_msg_dict[self.flow_id]):
                bridge = self.app.bridge[self.flow_id]
                self.app.mjai_msg_dict[self.flow_id][-1]['meta'] = meta_to_recommend(self.app.mjai_msg_dict[self.flow_id][-1]['meta'], bridge.is_3p)
                latest_mjai_msg = self.app.mjai_msg_dict[self.flow_id][-1]
                # Update tehai
                player_state = bridge.mjai_client.bot.state()
                tehai, tsumohai = state_to_tehai(player_state)
                for idx, tehai_label in enumerate(self.tehai_labels):
                    tehai_label.update(TILE_2_UNICODE_ART_RICH[tehai[idx]])
                # action_list = [x[0] for x in latest_mjai_msg['meta']]
                # for idx, tehai_value_label in enumerate(self.tehai_value_labels):
                #     # latest_mjai_msg['meta'] is list of (pai, value)
                #     try:
                #         pai_value = int(latest_mjai_msg['meta'][action_list.index(tehai[idx])][1] * 40)
                #         if pai_value == 40:
                #             pai_value = 39
                #     except ValueError:
                #         pai_value = 40
                #     tehai_value_label.update(HAI_VALUE[pai_value])
                self.tsumohai_label.update(TILE_2_UNICODE_ART_RICH[tsumohai])
                # if tsumohai in action_list:
                #     try:
                #         pai_value = int(latest_mjai_msg['meta'][action_list.index(tsumohai)][1] * 40)
                #         if pai_value == 40:
                #             pai_value = 39
                #     except ValueError:
                #         pai_value = 40
                #     self.tsumohai_value_label.update(HAI_VALUE[pai_value])

                self.app.rpc_server.clear_top3()

                # 將weight轉換為字典形式以便快速查找
                weight_dict = dict(self.app.mjai_msg_dict[self.flow_id][-1]['meta'])

                # 生成對應tile_list的權重列表
                tile_order_weight = [weight_dict[tile] if tile in weight_dict else -1.0 if tile == "?" else 0.0 for tile in tehai]
                tile_order_weight.append(weight_dict[tsumohai] if tsumohai in weight_dict else -1.0 if tsumohai == "?" else 0.0)
                # tile_order_weight is numpy.float64, need to convert to float
                tile_order_weight = [float(weight) for weight in tile_order_weight]
                self.app.rpc_server.draw_weight(tile_order_weight)

                # mjai log
                self.mjai_log.update(self.app.mjai_msg_dict[self.flow_id][-3:])
                self.mjai_log_container.scroll_end(animate=False)
                self.mjai_msg_idx += 1
                self.akagi_action.label = latest_mjai_msg["type"]
                for akagi_action_class in self.akagi_action.classes:
                    self.akagi_action.remove_class(akagi_action_class)
                self.akagi_action.add_class("action_"+latest_mjai_msg["type"])
                for akagi_pai_class in self.akagi_pai.classes:
                    self.akagi_pai.remove_class(akagi_pai_class)
                self.akagi_pai.add_class("pai_"+latest_mjai_msg["type"])
                for consumed_pai in self.consumed_pais:
                    consumed_pai.update(TILE_2_UNICODE_ART_RICH["?"])
                self.vertical_rule.update(EMPTY_VERTICAL_RULE)
                if "consumed" in latest_mjai_msg:
                    self.akagi_pai.label = str(latest_mjai_msg["consumed"])
                    if "pai" in latest_mjai_msg:
                        self.pai_unicode_art.update(TILE_2_UNICODE_ART_RICH[latest_mjai_msg["pai"]])
                    for i, c in enumerate(latest_mjai_msg["consumed"]):
                        if i >= 3:
                            # ankan
                            self.pai_unicode_art.update(TILE_2_UNICODE_ART_RICH[c])
                            continue
                        self.consumed_pais[i].update(TILE_2_UNICODE_ART_RICH[c])
                    self.vertical_rule.update(VERTICAL_RULE)
                elif "pai" in latest_mjai_msg:
                    self.consume_ids = []
                    self.akagi_pai.label = str(latest_mjai_msg["pai"])
                    self.pai_unicode_art.update(TILE_2_UNICODE_ART_RICH[latest_mjai_msg["pai"]])
                else:
                    self.akagi_pai.label = "None"
                    self.pai_unicode_art.update(TILE_2_UNICODE_ART_RICH["?"])
                for recommandation in self.recommandations_container.children:
                    recommandation.update(latest_mjai_msg, player_state)
                
                # Action
                self.tehai = tehai
                self.tsumohai = tsumohai
                if not self.syncing and ENABLE_PLAYWRIGHT and AUTOPLAY:
                    self.app.set_timer(0.15, self.autoplay)
                    # self.autoplay(tehai, tsumohai)
                    
        except Exception as e:
            pass

    @on(Checkbox.Changed, "#checkbox_autoplay")
    def checkbox_autoplay_changed(self, event: Checkbox.Changed) -> None:
        global AUTOPLAY
        AUTOPLAY = event.value
        pass

    @on(Checkbox.Changed, "#checkbox_overlay")
    def checkbox_overlay_changed(self, event: Checkbox.Changed) -> None:
        global OVERLAY
        OVERLAY = event.value
        if event.value:
            self.app.rpc_server.start_overlay_action()
        else:
            self.app.rpc_server.stop_overlay_action()
        pass
    
    def redo_action(self) -> None:
        try:
            self.action.mjai2action(self.app.mjai_msg_dict[self.flow_id][-1], self.tehai, self.tsumohai, None, True)
        except Exception as e:
            if self.dahai_verfication_job is not None:
                self.dahai_verfication_job.stop()
                self.dahai_verfication_job = None

    def autoplay(self) -> None:
        isliqi = self.isLiqi
        try:
            self.action.mjai2action(self.app.mjai_msg_dict[self.flow_id][-1], self.tehai, self.tsumohai, isliqi, False)
        except KeyError:
            return
        self.isLiqi = False
        if self.dahai_verfication_job is not None:
            self.dahai_verfication_job.stop()
            self.dahai_verfication_job = None
        self.dahai_verfication_job = self.set_interval(2.5, self.redo_action)
        pass

    def action_quit(self) -> None:
        self.app.rpc_server.stop_overlay_action()
        self.app.set_timer(2, self.app.update_flow.resume)
        self.update_log.stop()
        self.app.pop_screen()


class FlowDisplay(Static):

    def __init__(self, flow_id, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.flow_id = flow_id

    def compose(self) -> ComposeResult:
        yield Button(f"Flow {self.flow_id}", id=f"flow_{self.flow_id}_btn", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.push_screen(FlowScreen(self.flow_id))
        self.app.update_flow.pause()


class HoverLink(Static):
    def __init__(self, text, url, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.renderable = text
        self.url = url
        self.add_class("hover-link")
        self.border_title = self.url
        self.border_subtitle = "Click to open link"

    def on_click(self, event):
        webbrowser.open_new_tab(self.url)
        pass


class SettingsScreen(Static):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        with open("settings.json", "r") as f:
            settings = json.load(f)
            self.value_port_setting_mitm_input = settings["Port"]["MITM"]
            self.value_port_setting_xmlrpc_input = settings["Port"]["XMLRPC"]
            self.value_unlocker_setting_enable_checkbox = settings["Unlocker"]
            self.value_helper_setting_checkbox = settings["Helper"]
            self.value_overlay_setting_enable_checkbox = settings["Overlay"]
            self.value_autoplay_setting_enable_checkbox = settings["Autoplay"]
            self.value_autoplay_setting_random_time_new_min_input = settings["RandomTime"]["new_min"]
            self.value_autoplay_setting_random_time_new_max_input = settings["RandomTime"]["new_max"]
            self.value_autoplay_setting_random_time_min_input = settings["RandomTime"]["min"]
            self.value_autoplay_setting_random_time_max_input = settings["RandomTime"]["max"]
            self.value_playwright_setting_enable_checkbox = settings["Playwright"]["enable"]
            self.value_playwright_setting_width_input = settings["Playwright"]["width"]
            self.value_playwright_setting_height_input = settings["Playwright"]["height"]

    def compose(self) -> ComposeResult:
        self.port_setting_mitm_label = Label("MITM Port", id="port_setting_mitm_label")
        self.port_setting_mitm_input = Input(placeholder="Port", type="integer", id="port_setting_mitm_input", value=str(self.value_port_setting_mitm_input))
        self.port_setting_mitm_container = Horizontal(self.port_setting_mitm_label, self.port_setting_mitm_input, id="port_setting_mitm_container")
        self.port_setting_xmlrpc_label = Label("XMLRPC Port", id="port_setting_xmlrpc_label")
        self.port_setting_xmlrpc_input = Input(placeholder="Port", type="integer", id="port_setting_xmlrpc_input", value=str(self.value_port_setting_xmlrpc_input))
        self.port_setting_xmlrpc_container = Horizontal(self.port_setting_xmlrpc_label, self.port_setting_xmlrpc_input, id="port_setting_xmlrpc_container")
        self.port_setting_container = Vertical(self.port_setting_mitm_container, self.port_setting_xmlrpc_container, id="port_setting_container")
        self.port_setting_container.border_title = "Port"

        self.unlocker_setting_label = Label("Unlocker", id="unlocker_setting_label")
        self.unlocker_setting_enable_checkbox = Checkbox("Enable", id="unlocker_setting_enable_checkbox", classes="short", value=self.value_unlocker_setting_enable_checkbox)
        self.unlocker_setting_container = Horizontal(self.unlocker_setting_label, self.unlocker_setting_enable_checkbox, id="unlocker_setting_container")
        self.unlocker_setting_container.border_title = "Unlocker"

        self.helper_setting_label = Label("Helper", id="helper_setting_label")
        self.helper_setting_checkbox = Checkbox("Enable", id="helper_setting_checkbox", classes="short", value=self.value_helper_setting_checkbox)
        self.helper_setting_container = Horizontal(self.helper_setting_label, self.helper_setting_checkbox, id="helper_setting_container")
        self.helper_setting_container.border_title = "Helper"

        self.overlay_setting_label = Label("Overlay", id="overlay_setting_label")
        self.overlay_setting_checkbox = Checkbox("Enable", id="overlay_setting_checkbox", classes="short", value=self.value_overlay_setting_enable_checkbox)
        self.overlay_setting_container = Horizontal(self.overlay_setting_label, self.overlay_setting_checkbox, id="overlay_setting_container")
        self.overlay_setting_container.border_title = "Overlay"

        self.autoplay_setting_enable_label = Label("Enable", id="autoplay_setting_enable_label")
        self.autoplay_setting_enable_checkbox = Checkbox("Enable", id="autoplay_setting_enable_checkbox", classes="short", value=self.value_autoplay_setting_enable_checkbox)
        self.autoplay_setting_enable_container = Horizontal(self.autoplay_setting_enable_label, self.autoplay_setting_enable_checkbox, id="autoplay_setting_enable_container")
        self.autoplay_setting_random_time_new_label = Label("Random New", id="autoplay_setting_random_time_new_label")
        self.autoplay_setting_random_time_new_min_input = Input(placeholder="Min", type="number", id="autoplay_setting_random_time_new_min_input", value=str(self.value_autoplay_setting_random_time_new_min_input))
        self.autoplay_setting_random_time_new_max_input = Input(placeholder="Max", type="number", id="autoplay_setting_random_time_new_max_input", value=str(self.value_autoplay_setting_random_time_new_max_input))
        self.autoplay_setting_random_time_new_container = Horizontal(self.autoplay_setting_random_time_new_label, self.autoplay_setting_random_time_new_min_input, self.autoplay_setting_random_time_new_max_input, id="autoplay_setting_random_time_new_container")
        self.autoplay_setting_random_time_label = Label("Random", id="autoplay_setting_random_time_label")
        self.autoplay_setting_random_time_min_input = Input(placeholder="Min", type="number", id="autoplay_setting_random_time_min_input", value=str(self.value_autoplay_setting_random_time_min_input))
        self.autoplay_setting_random_time_max_input = Input(placeholder="Max", type="number", id="autoplay_setting_random_time_max_input", value=str(self.value_autoplay_setting_random_time_max_input))
        self.autoplay_setting_random_time_container = Horizontal(self.autoplay_setting_random_time_label, self.autoplay_setting_random_time_min_input, self.autoplay_setting_random_time_max_input, id="autoplay_setting_random_time_container")
        self.autoplay_setting_container = Vertical(self.autoplay_setting_enable_container, self.autoplay_setting_random_time_new_container, self.autoplay_setting_random_time_container, id="autoplay_setting_container")
        self.autoplay_setting_container.border_title = "Autoplay"

        self.playwright_setting_enable_label = Label("Enable", id="playwright_setting_enable_label")
        self.playwright_setting_enable_checkbox = Checkbox("Enable", id="playwright_setting_enable_checkbox", classes="short", value=self.value_playwright_setting_enable_checkbox)
        self.playwright_setting_enable_container = Horizontal(self.playwright_setting_enable_label, self.playwright_setting_enable_checkbox, id="playwright_setting_enable_container")
        self.playwright_setting_resolution_label = Label("Resolution", id="playwright_setting_resolution_label")
        self.playwright_setting_width_input = Input(placeholder="Width", type="integer", id="playwright_setting_width_input", value=str(self.value_playwright_setting_width_input))
        self.playwright_setting_height_input = Input(placeholder="Height", type="integer", id="playwright_setting_height_input", value=str(self.value_playwright_setting_height_input))
        self.playwright_setting_resolution_container = Horizontal(self.playwright_setting_resolution_label, self.playwright_setting_width_input, self.playwright_setting_height_input, id="playwright_setting_resolution_container")
        self.playwright_setting_container = Vertical(self.playwright_setting_enable_container, self.playwright_setting_resolution_container, id="playwright_setting_container")
        self.playwright_setting_container.border_title = "Playwright"

        self.setting_save_button = Button("Save", variant="warning", id="setting_save_button")

        self.remove_this_then_you_badluck_for_100years_and_get_hit_by_a_car_then_die = HoverLink("Akagi is Free and Open Sourced on GitHub.\n本程式Akagi在GitHub上完全開源且免費。如果你是付費取得的，你已經被賣家欺騙，請立即舉報、差評、退款。", "https://github.com/shinkuan/Akagi", id="remove_this_you_die")

        self.setting_container = ScrollableContainer(
                                                     self.port_setting_container, 
                                                     self.unlocker_setting_container, 
                                                     self.helper_setting_container,
                                                     self.overlay_setting_container,
                                                     self.autoplay_setting_container,
                                                     self.playwright_setting_container,
                                                     self.setting_save_button,
                                                     self.remove_this_then_you_badluck_for_100years_and_get_hit_by_a_car_then_die,
                                                     id="setting_container"
                                                    )

        yield self.setting_container

    @on(Input.Changed, "#port_setting_mitm_input")
    def port_setting_mitm_input_changed(self, event: Input.Changed) -> None:
        try:
            self.value_port_setting_mitm_input = int(event.value)
        except:
            pass

    @on(Input.Changed, "#port_setting_xmlrpc_input")
    def port_setting_xmlrpc_input_changed(self, event: Input.Changed) -> None:
        try:
            self.value_port_setting_xmlrpc_input = int(event.value)
        except:
            pass

    @on(Checkbox.Changed, "#unlocker_setting_enable_checkbox")
    def unlocker_setting_enable_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.value_unlocker_setting_enable_checkbox = event.value

    @on(Checkbox.Changed, "#helper_setting_checkbox")
    def helper_setting_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.value_helper_setting_checkbox = event.value

    @on(Checkbox.Changed, "#overlay_setting_checkbox")
    def overlay_setting_checkbox_changed(self, event: Checkbox.Changed) -> None:
        global OVERLAY
        OVERLAY = event.value
        self.value_overlay_setting_enable_checkbox = event.value

    @on(Checkbox.Changed, "#autoplay_setting_enable_checkbox")
    def autoplay_setting_enable_checkbox_changed(self, event: Checkbox.Changed) -> None:
        global AUTOPLAY
        AUTOPLAY = event.value
        self.value_autoplay_setting_enable_checkbox = event.value

    @on(Input.Changed, "#autoplay_setting_random_time_new_min_input")
    def autoplay_setting_random_time_new_min_input_changed(self, event: Input.Changed) -> None:
        try:
            self.value_autoplay_setting_random_time_new_min_input = float(event.value)
        except:
            pass

    @on(Input.Changed, "#autoplay_setting_random_time_new_max_input")
    def autoplay_setting_random_time_new_max_input_changed(self, event: Input.Changed) -> None:
        try:
            self.value_autoplay_setting_random_time_new_max_input = float(event.value)
        except:
            pass

    @on(Input.Changed, "#autoplay_setting_random_time_min_input")
    def autoplay_setting_random_time_min_input_changed(self, event: Input.Changed) -> None:
        try:
            self.value_autoplay_setting_random_time_min_input = float(event.value)
        except:
            pass

    @on(Input.Changed, "#autoplay_setting_random_time_max_input")
    def autoplay_setting_random_time_max_input_changed(self, event: Input.Changed) -> None:
        try:
            self.value_autoplay_setting_random_time_max_input = float(event.value)
        except:
            pass

    @on(Checkbox.Changed, "#playwright_setting_enable_checkbox")
    def playwright_setting_enable_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.value_playwright_setting_enable_checkbox = event.value

    @on(Input.Changed, "#playwright_setting_width_input")
    def playwright_setting_width_input_changed(self, event: Input.Changed) -> None:
        try:
            self.value_playwright_setting_width_input = int(event.value)
        except:
            pass

    @on(Input.Changed, "#playwright_setting_height_input")
    def playwright_setting_height_input_changed(self, event: Input.Changed) -> None:
        try:
            self.value_playwright_setting_height_input = int(event.value)
        except:
            pass

    @on(Button.Pressed, "#setting_save_button")
    def setting_save_button_pressed(self) -> None:
        with open("settings.json", "r") as f:
            settings = json.load(f)
            settings["Port"]["MITM"] = self.value_port_setting_mitm_input
            settings["Port"]["XMLRPC"] = self.value_port_setting_xmlrpc_input
            settings["Unlocker"] = self.value_unlocker_setting_enable_checkbox
            settings["Helper"] = self.value_helper_setting_checkbox
            settings["Overlay"] = self.value_overlay_setting_enable_checkbox
            settings["Autoplay"] = self.value_autoplay_setting_enable_checkbox
            settings["RandomTime"]["new_min"] = self.value_autoplay_setting_random_time_new_min_input
            settings["RandomTime"]["new_max"] = self.value_autoplay_setting_random_time_new_max_input
            settings["RandomTime"]["min"] = self.value_autoplay_setting_random_time_min_input
            settings["RandomTime"]["max"] = self.value_autoplay_setting_random_time_max_input
            settings["Playwright"]["enable"] = self.value_playwright_setting_enable_checkbox
            settings["Playwright"]["width"] = self.value_playwright_setting_width_input
            settings["Playwright"]["height"] = self.value_playwright_setting_height_input
        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=4)


class Akagi(App):
    CSS_PATH = "client.tcss"

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, rpc_server, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rpc_server = rpc_server
        self.liqi: dict[str, LiqiProto] = {}
        self.bridge: dict[str, MajsoulBridge] = {}
        self.active_flows = []
        self.messages_dict  = dict() # flow.id -> List[flow_msg]
        self.liqi_msg_dict  = dict() # flow.id -> List[liqi_msg]
        self.mjai_msg_dict  = dict() # flow.id -> List[mjai_msg]
        self.akagi_log_dict = dict() # flow.id -> List[akagi_log]
        self.mitm_started = False

    def on_mount(self) -> None:
        self.update_flow = self.set_interval(1, self.refresh_flow)
        self.get_messages_flow = self.set_interval(0.05, self.get_messages)

    def refresh_flow(self) -> None:
        if not self.mitm_started:
            return
        flows = self.rpc_server.get_activated_flows()
        for flow_id in self.active_flows:
            if flow_id not in flows:
                try:
                    self.query_one(f"#flow_{flow_id}").remove()
                except NoMatches:
                    pass
                self.active_flows.remove(flow_id)
                self.messages_dict.pop(flow_id)
                self.liqi_msg_dict.pop(flow_id)
                self.mjai_msg_dict.pop(flow_id)
                self.akagi_log_dict.pop(flow_id)
                self.liqi.pop(flow_id)
                self.bridge.pop(flow_id)
        for flow_id in flows:
            try:
                self.query_one("#FlowContainer")
            except NoMatches:
                continue
            try:
                self.query_one(f"#flow_{flow_id}")
            except NoMatches:
                self.query_one("#FlowContainer").mount(FlowDisplay(flow_id, id=f"flow_{flow_id}"))
                self.active_flows.append(flow_id)
                self.messages_dict[flow_id] = []
                self.liqi_msg_dict[flow_id] = []
                self.mjai_msg_dict[flow_id] = []
                self.akagi_log_dict[flow_id] = []
                self.liqi[flow_id] = LiqiProto()
                self.bridge[flow_id] = MajsoulBridge()

    def get_messages(self):
        if not self.mitm_started:
            return
        for flow_id in self.active_flows:
            messages = self.rpc_server.get_messages(flow_id)
            if messages is not None:
                # Convert xmlrpc.client.Binary to bytes
                messages = messages.data
                assert isinstance(messages, bytes)
                self.messages_dict[flow_id].append(messages)
                liqi_msg = self.liqi[flow_id].parse(messages)
                if liqi_msg is not None:
                    self.liqi_msg_dict[flow_id].append(liqi_msg)
                    if liqi_msg['method'] == '.lq.FastTest.authGame' and liqi_msg['type'] == MsgType.Req:
                        self.app.push_screen(FlowScreen(flow_id))
                        pass
                    mjai_msg = self.bridge[flow_id].input(liqi_msg)
                    if mjai_msg is not None:
                        if self.bridge[flow_id].reach and mjai_msg["type"] == "dahai":
                            mjai_msg["type"] = "reach"
                            self.bridge[flow_id].reach = False
                        self.mjai_msg_dict[flow_id].append(mjai_msg)


    def compose(self) -> ComposeResult:
        """Called to add widgets to the app."""
        yield Header()
        yield Button(label="Start MITM", variant="success", id="start_mitm_button")
        yield SettingsScreen(id="settings_screen")
        yield ScrollableContainer(id="FlowContainer")
        yield Footer()

    def on_event(self, event: Event) -> Coroutine[Any, Any, None]:
        return super().on_event(event)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start_mitm_button":
            self.query_one("#settings_screen").remove()
            start_mitm()
            event.button.variant = "default"
            event.button.disabled = True
            self.set_timer(5, self.mitm_connected)
        pass

    def mitm_connected(self):
        try:
            self.rpc_server.ping()
            self.mitm_started = True
        except:
            self.set_timer(2, self.mitm_connected)

    def action_quit(self) -> None:
        self.update_flow.stop()
        self.get_messages_flow.stop()
        self.exit()


def exit_handler():
    global mitm_exec
    try:
        mitm_exec.kill()
    except:
        pass
    pass


def start_mitm():
    global mitm_exec

    command = [sys.executable, pathlib.Path(__file__).parent / "mitm.py"]

    if sys.platform == "win32":
        # Windows特定代码
        mitm_exec = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        # macOS和其他Unix-like系统
        mitm_exec = subprocess.Popen(command, preexec_fn=os.setsid)


if __name__ == '__main__':
    with open("settings.json", "r") as f:
        settings = json.load(f)
        rpc_port = settings["Port"]["XMLRPC"]
    rpc_host = "127.0.0.1"
    s = ServerProxy(f"http://{rpc_host}:{rpc_port}", allow_none=True)
    app = Akagi(rpc_server=s)
    atexit.register(exit_handler)
    try:
        app.run()
    except Exception as e:
        exit_handler()
        raise e
