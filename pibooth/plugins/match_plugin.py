# -*- coding: utf-8 -*-

import time

from pibooth.camera.opencv import AICvCamera, get_cv_camera_proxy
from pibooth.utils import LOGGER, PoolingTimer
import pibooth

__version__ = "0.0.1"

@pibooth.hookimpl
def state_wait_validate(cfg, app, events):
    if isinstance(app.camera, AICvCamera):
        return 'qr'

@pibooth.hookimpl
def pibooth_configure(cfg):
    cfg.add_option('CONTROLS', 'DB_API_KEY', '', "Database API KEY")
    cfg.add_option('CONTROLS', 'DB_URL', '/api/public/printing', "Database API KEY")
                   
@pibooth.hookimpl
def pibooth_startup(cfg, app):
    app.db_url = cfg.get('CONTROLS', 'DB_URL')
    app.db_key = cfg.get('CONTROLS', 'DB_API_KEY')
    app.qr_data = ''
    app._last_qr_check = time.time()
    app._machine.add_state('qr')
    

@pibooth.hookimpl
def state_qr_enter(cfg, app, win):
    LOGGER.info("QR DETECTION MODE")

@pibooth.hookimpl
def state_qr_do(cfg, app, win, events):
    res = app.camera.preview(win)
    current_time = time.time()
    if current_time - app._last_qr_check > 0.3:
        app._last_qr_check = current_time
        app.qr_data = app.camera.detect_qr()

@pibooth.hookimpl
def state_qr_validate(cfg, app, win, events):
    if app.qr_data == 'expected':
        app.capture_nbr = app.capture_choices[0]
        app.camera.stop_preview()
        return 'preview'

@pibooth.hookimpl
def state_qr_exit(cfg, app, win):
    app.qr_data = ''

@pibooth.hookimpl
def pibooth_setup_camera(cfg):
    cv_cam_proxy = get_cv_camera_proxy()
    if cv_cam_proxy:
        LOGGER.info("Configuring OpenCV camera ...")
        return AICvCamera(cv_cam_proxy)
    raise EnvironmentError("No OpenCV Camera compatible found. :(")