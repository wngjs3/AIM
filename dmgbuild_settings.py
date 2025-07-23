# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os.path
import os

# 환경변수에서 앱 이름 가져오기 (기본값 'Intention(new)')
app_name = os.environ.get("APP_NAME", "Intention(new)")

# 현재 앱 번들 경로 설정
application = defines.get("app", f"dist/{app_name}.app")
appname = os.path.basename(application)

# Volume format (see hdiutil create -help)
format = defines.get("format", "UDBZ")

# Volume size
size = defines.get("size", None)

# Files to include
files = [application]

# Symlinks to create
symlinks = {"Applications": "/Applications"}

# Volume icon
#
# You can either define icon, in which case that icon file will be copied to the
# image, *or* you can define badge_icon, in which case the icon file you specify
# will be used to badge the system's Removable Disk icon
#
icon = "src/assets/icon.png"
badge_icon = None

# Where to put the icons
icon_locations = {appname: (140, 120), "Applications": (500, 120)}

# Window configuration
background = "build_assets/dmg_background.png"
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
sidebar_width = 180

# Window position in ((x, y), (w, h)) format
window_rect = ((100, 100), (640, 280))

# Select the default view; must be one of
# 'icon-view'
# 'list-view'
# 'column-view'
# 'coverflow'
default_view = "icon-view"

# General view configuration
show_icon_preview = False

# Set these to True to force inclusion of icon/list view settings even
# if the corresponding view is not the default view
include_icon_view_settings = True
include_list_view_settings = False

# Icon view configuration
arrange_by = None
grid_offset = (0, 0)
grid_spacing = 100
scroll_position = (0, 0)
label_pos = "bottom"  # or 'right'
text_size = 16
icon_size = 128
