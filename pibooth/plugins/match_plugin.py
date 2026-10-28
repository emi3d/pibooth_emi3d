# -*- coding: utf-8 -*-

import requests
import time
import pygame
import io
import mimetypes
import os

from pibooth.camera.opencv import AICvCamera, get_cv_camera_proxy
from pibooth.utils import LOGGER, PoolingTimer
from pibooth import pictures, fonts
from pibooth.view import background
import pibooth

__version__ = "0.0.1"

""" Config hooks """
@pibooth.hookimpl
def pibooth_configure(cfg):
    cfg.add_option('CONTROLS', 'DB_API_KEY', '', "Database API KEY")
    cfg.add_option('CONTROLS', 'DB_URL', '', "Database URL KEY")
                   
@pibooth.hookimpl
def pibooth_startup(cfg, app):
    app.db_url = cfg.get('CONTROLS', 'DB_URL')
    app.qr_data = ''
    app._last_opencv_check = time.time()
    app._machine.add_state('qr')
    app._machine.add_state('liked')
    app.liked_photo = ''
    app.match_photo_url = ''
    app.session = requests.Session()
    app.session.headers["Authorization"] = f"Bearer {cfg.get('CONTROLS', 'DB_API_KEY')}"

""" Existing hooks """
@pibooth.hookimpl
def state_wait_validate(cfg, app, events):
    if isinstance(app.camera, AICvCamera):
        if not app.qr_data: 
            return 'qr'
        if app.qr_data:
            app.capture_nbr = app.capture_choices[1]
            return 'preview'

@pibooth.hookimpl
def state_finish_validate(cfg, app):
    if app.liked_photo == 'yes':
        app.liked_photo = ''
        return 'wait'
    return 'liked'

""" New hooks """

@pibooth.hookimpl
def state_qr_enter(cfg, app, win):
    win._update_background(background.EmptyBackground())
    LOGGER.info("QR DETECTION MODE")

@pibooth.hookimpl
def state_qr_do(cfg, app, win, events):
    app.camera.show_text_overlay(win, 'Porfavor muestra tu QR a la cámara')
    if app.qr_data:
        return
    current_time = time.time()
    if current_time - app._last_opencv_check > 0.3:
        app._last_opencv_check = current_time
        app.qr_data = app.camera.detect_qr()

@pibooth.hookimpl
def state_qr_validate(cfg, app, win, events):
    if app.qr_data and validate_qr(app.qr_data, app):
        app.capture_nbr = app.capture_choices[1]
        app.camera.stop_preview()
        return 'preview'
    else:
        app.qr_data = ''

@pibooth.hookimpl
def state_qr_exit(cfg, app, win):
    pass

@pibooth.hookimpl
def state_liked_enter(cfg, app, win):
    win.show_finished()
    win._update_background(background.EmptyBackground())
    app.liked_photo = ''
    LOGGER.info("LIKE OR DISLAKE PHOTO DETECTION MODE")

@pibooth.hookimpl
def state_liked_do(cfg, app, win, events):
    current_time = time.time()
    if current_time - app._last_opencv_check > 0.3:
        app._last_opencv_check = current_time
        pygame.event.pump()
        app.liked_photo = app.camera.detect_like(win, picture=app.previous_picture)

@pibooth.hookimpl
def state_liked_validate(cfg, app, win, events):
    app.camera.stop_preview()
    if (like := app.liked_photo) in ('no', 'yes'):
        if like == 'yes' and save_to_db(app.qr_data, app.previous_picture_file, app):
            img = app.previous_picture.copy()
            win._update_background(background.EmptyBackground())
            app.camera._draw_text(img, 'Foto aceptada, guardando...', 'midbottom')
            win._update_foreground(img, win.FULLSCREEN)
            app.qr_data = ''
            app.match_photo_url = ''
            timer = PoolingTimer(8)
            pygame.display.update()
            while not timer.is_timeout():
                pygame.event.pump()
            return 'finish'
        else:
            app.capture_nbr = app.capture_choices[1]
            return 'wait'

@pibooth.hookimpl
def state_liked_exit(cfg, app, win):
    pass

""" Misc """     
@pibooth.hookimpl
def pibooth_setup_camera(cfg):
    cv_cam_proxy = get_cv_camera_proxy()
    if cv_cam_proxy:
        LOGGER.info("Configuring OpenCV camera ...")
        return AICvCamera(cv_cam_proxy)
    raise EnvironmentError("No OpenCV Camera compatible found. :(")

def validate_qr(code, app):
    try:
        r = app.session.post(
            app.db_url, 
            timeout=10,
            json={"code": code, "action": 'lookup'},
        ).json()

        if can_print :=  r.get("canPrint") is True:
            if not r.get('usePlaceholder'):
                app.match_photo_url = r.get('matchPhotoUrl')
        return can_print
    except Exception:
            return False
    
def save_to_db(code, image_path, app):
    ext = image_path.rsplit(".", 1)[-1].lower()
    mime = f"image/{ext}"
    filename = f"{code}.{ext}"
    try:
        with open(image_path, "rb") as f:
            r = app.session.post(
                app.db_url,
                timeout=30,
                data={"code": code, "action": "mark_printed"},
                files={"photo": (filename, f, mime)},
            )
        body = r.json()
        if success := body.get("markedPrinted") is True and body.get("photoStored") is True:
            after_save_to_db(app.qr_data, image_path, app.match_photo_url)
        return success
    except Exception:
        return False

def after_save_to_db(code, image_path, match_image_url):
    return True