#!/usr/bin/env python3

# Copyright (c) 2019, Alchemy Meister
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice,this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
"""
import logging
import sys

from config import DefaultSettings
from constants.event import GraphicSettingsChangeEvent
from constants.overlay import OverlayMode, OverlayPosition, OverlayLayout
from gui.model import OverlayModel
from log import Formatter
from patterns.factory import OverlayFactory
from patterns.observer import Subscriber
from patterns.singleton import Singleton

from .overlay import Overlay
from .interfaces import Writable

class OverlayManager(metaclass=Singleton):
    """
    """
    def __init__(self, launcher, initial_settings=None):
        self.launcher = launcher

        logging_handler = logging.StreamHandler(sys.stdout)
        logging_handler.setFormatter(Formatter())

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging_handler)

        graphic_settings_publisher = (
            self.launcher.game_state.graphic_settings_publisher
        )
        subscriber = Subscriber()
        graphic_settings_publisher.register(
            GraphicSettingsChangeEvent.RESOLUTION, subscriber,
            self.__resolution_change
        )
        graphic_settings_publisher.register(
            GraphicSettingsChangeEvent.SCREEN_MODE, subscriber,
            self.__screen_mode_change
        )
        graphic_settings_publisher.register(
            GraphicSettingsChangeEvent.POSITION, subscriber,
            self.__position_change
        )

        self.overlay_factory = OverlayFactory()
        self.overlays = dict()

        sys.stdout.callback = self.write_to_overlays

        self.tekken_position = None
        self.tekken_resolution = None
        self.tekken_screen_mode = None

        self.current_overlay: Overlay
        self.current_overlay = None

        self.overlay_model = OverlayModel()

        self.overlays_enabled = False

        self.active_slots = 0
        self.overlay_slots = [None] * list(OverlayLayout).pop().value

        self.reloadable_initial_settings = initial_settings
        self.reload()

    def enable_automatic_overlay_hide(self, enable):
        for overlay_id in self.overlays:
            self.overlays[overlay_id].set_automatic_hide(enable)

    def enable_overlays(self, enable):
        self.overlays_enabled = enable
        for slot_index in range(self.active_slots):
            self.overlays[self.overlay_slots[slot_index]].set_enable(
                self.overlays_enabled
            )

    def change_overlay_layout(self, layout):
        min_value = min(self.active_slots, layout.value)
        max_value = max(self.active_slots, layout.value)
        enable = self.active_slots < layout.value
        for turn_id in self.overlay_slots[min_value:max_value]:
            self.logger.debug(
                'turning %s overlay %s',
                OverlayMode(self.overlays[turn_id].__class__.CLASS_ID).name,
                'on' if enable else 'off'
            )
            self.overlays[turn_id].set_enable(enable)
        self.logger.debug(
            'changing layout from %s to %s',
            OverlayLayout(self.active_slots).name,
            layout.name
        )
        self.active_slots = layout.value

    def change_overlay_mode(self, mode: OverlayMode, slot, swap):
        overlay = self.overlays[self.overlay_slots[slot]]
        previous_mode = OverlayMode(self.overlay_slots[slot])

        self.logger.debug(
            'arguments: layout: %s, mode: %s, overlay slot: %d, swap: %s',
            OverlayLayout(self.active_slots).name,
            mode.name,
            slot + 1,
            swap
        )
        self.logger.debug(
            'overlay slot id list: %s',
            [
                OverlayMode(overlay_id).name
                for overlay_id in self.overlay_slots
            ]
        )
        self.logger.debug(
            'overlay settings in overlay slots: %s',
            [
                self.overlays[overlay_id]
                for overlay_id in self.overlay_slots
            ]
        )
        if swap:
            previous_slot = self.overlay_slots.index(
                self.overlays[mode.value].__class__.CLASS_ID
            )
            self.overlay_slots[slot], self.overlay_slots[previous_slot] = (
                self.overlay_slots[previous_slot], self.overlay_slots[slot]
            )
            self.logger.debug(
                'overlay slot id list after swap: %s',
                [
                    OverlayMode(overlay_id).name
                    for overlay_id in self.overlay_slots
                ]
            )
            if self.active_slots == 1:
                self.logger.debug(
                    'turning %s overlay off',
                    previous_mode.name
                )
                overlay.set_enable(False)
                self.logger.debug(
                    'turning %s overlay on',
                    mode.name
                )
                self.overlays[mode.value].set_enable(True)

            self.logger.debug(
                'swapping %s and %s overlay settings',
                mode.name,
                previous_mode.name
            )
            previous_settings = overlay.set_settings_from_overlay(
                self.overlays[mode.value]
            )
            self.overlays[mode.value].set_settings(*previous_settings)
            self.logger.debug(
                'overlay settings swapped: %s',
                [
                    self.overlays[overlay_id]
                    for overlay_id in self.overlay_slots
                ]
            )
        else:
            self.logger.debug(
                'turning %s overlay off',
                previous_mode.name
            )
            overlay.set_enable(False)
            change_overlay = self.overlays.get(mode.value)
            if not change_overlay:
                change_overlay = self.__add_overlay(
                    mode, previous_overlay=overlay
                )
                self.overlay_slots[slot] = change_overlay.__class__.CLASS_ID
            else:
                self.logger.debug(
                    'swapping %s and %s overlay settings',
                    mode.name,
                    previous_mode.name
                )
                previous_settings = change_overlay.set_settings_from_overlay(
                    overlay
                )
                overlay.set_settings(*previous_settings)
            if self.overlays_enabled:
                self.logger.debug(
                    'turning %s overlay on',
                    mode.name
                )
                change_overlay.set_enable(True)

        self.logger.debug('exit')

    def change_overlay_position(self, position, slot, swap):
        overlay = self.overlays[self.overlay_slots[slot]]

        self.logger.debug(
            'arguments: layout: %s, overlay slot: %s, position: %s, swap: %s',
            OverlayLayout(self.active_slots).name,
            slot + 1,
            position.name,
            swap
        )
        self.logger.debug(
            'overlay settings in overlay slots: %s',
            [self.overlays[overlay_id] for overlay_id in self.overlay_slots]
        )

        if swap:
            swap_overlay = next(
                self.overlays[overlay_id]
                for overlay_id in self.overlay_slots
                if self.overlays[overlay_id].position == position
            )
            self.logger.debug(
                'swapping %s and %s overlay positions',
                OverlayMode(self.overlay_slots[slot]).name,
                OverlayMode(swap_overlay.__class__.CLASS_ID).name
            )
            previous_position = overlay.position
            overlay.set_position(position)
            swap_overlay.set_position(previous_position)
            self.logger.debug(
                'overlay settings after position swap: %s',
                [
                    self.overlays[overlay_id]
                    for overlay_id in self.overlay_slots
                ]
            )
        else:
            overlay.set_position(position)
            self.logger.debug('overlay position changed: %s', overlay)

        self.logger.debug('exit')


    def change_overlay_theme(self, theme_dict, slot):
        self.overlays[self.overlay_slots[slot]].set_theme(theme_dict)

    def get_overlay_mode(self, slot):
        return OverlayMode(
            self.overlays[self.overlay_slots[slot]].__class__.CLASS_ID
        )

    def reload(self):
        if self.reloadable_initial_settings:
            initial_settings = self.reloadable_initial_settings.config[
                'DEFAULT'
            ]
        else:
            initial_settings = DefaultSettings.SETTINGS['DEFAULT']

        for slot in range(1, list(OverlayLayout).pop().value + 1):
            mode = OverlayMode[
                initial_settings.get('overlay_{}_mode'.format(slot))
            ]
            self.overlay_slots[slot - 1] = mode.value

            if self.overlays.get(mode.value):
                overlay = self.overlays[mode.value]
            else:
                overlay = self.__add_overlay(mode)

            overlay.set_position(
                OverlayPosition[
                    initial_settings.get('overlay_{}_position'.format(slot))
                ]
            )

            overlay.set_theme(
                self.overlay_model.get_theme(
                    self.overlay_model.get_index_by_filename(
                        mode.name,
                        initial_settings.get('overlay_{}_theme'.format(slot))
                    ),
                    mode.name
                )
            )

        self.enable_automatic_overlay_hide(
            initial_settings.get('overlay_automatic_hide')
        )
        self.set_framedata_overlay_column_settings(
            initial_settings.get('framedata_overlay_columns')
        )
        self.active_slots = (
            OverlayLayout[
                initial_settings.get('overlay_layout')
            ].value
        )
        self.enable_overlays(initial_settings.get('overlay_enable'))

    def set_framedata_overlay_column_settings(self, column_settings):
        frame_data_overlay = self.overlays.get(OverlayMode.FRAMEDATA.value)
        if not frame_data_overlay:
            frame_data_overlay = self.__add_overlay(OverlayMode.FRAMEDATA)
        frame_data_overlay.set_display_columns(column_settings)

    def write_to_overlays(self, string):
        for overlay_id in self.overlay_slots:
            overlay = self.overlays.get(overlay_id)
            if(
                    isinstance(overlay, Writable)
                    and overlay.enabled
            ):
                overlay.write(string)

    def __add_overlay(self, overlay_mode, previous_overlay=None):
        self.logger.debug('overlays before creation: %s', self.overlays)
        self.logger.debug('creating %s overlay', overlay_mode.name)
        overlay_id = overlay_mode.value
        self.overlays[overlay_id] = self.overlay_factory.create_class(
            overlay_id, self.launcher
        )
        if self.tekken_screen_mode:
            self.overlays[overlay_id].set_tekken_screen_mode(
                self.tekken_screen_mode
            )
        if self.tekken_resolution:
            self.overlays[overlay_id].set_tekken_resolution(
                self.tekken_resolution
            )
        if self.tekken_position:
            self.overlays[overlay_id].set_tekken_position(self.tekken_position)

        if previous_overlay:
            self.logger.debug(
                "initializing %s overlay with %s's settings",
                overlay_mode.name,
                OverlayMode(previous_overlay.__class__.CLASS_ID).name
            )
            self.overlays[overlay_id].set_settings_from_overlay(
                previous_overlay
            )

        self.logger.debug('overlays after creation: %s', self.overlays)
        return self.overlays[overlay_id]

    def __position_change(self, position):
        self.tekken_position = position
        for overlay in self.overlays.values():
            overlay.set_tekken_position(position)

    def __resolution_change(self, resolution):
        self.tekken_resolution = resolution
        for overlay in self.overlays.values():
            overlay.set_tekken_resolution(resolution)

    def __screen_mode_change(self, screen_mode):
        self.tekken_screen_mode = screen_mode
        for overlay in self.overlays.values():
            overlay.set_tekken_screen_mode(screen_mode)
