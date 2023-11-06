import coloredlogs
import json
import requests
import logging

BLYQT_API_PREFIX = "http://0.0.0.0:8000/api/v1"


logger = logging.getLogger(__name__)
coloredlogs.install(level=logging.DEBUG, logger=logger)


def update_blyqt_recording_settings(updated_settings_json):
    URL = f"{BLYQT_API_PREFIX}/liteunit/settings/recording"
    payload = {
        "gaze_overlay": updated_settings_json["recording"]["gazeoverlay"],
        "gaze_file": updated_settings_json["recording"]["gazefile"],
        "audio": updated_settings_json["recording"]["audio"],
        "heat_map": updated_settings_json["recording"]["heatmap"],
        "location": updated_settings_json["recording"]["location"],
        "file_format": updated_settings_json["recording"]["container"],
        "front_resolution": updated_settings_json["recording"]["fc_resolution"]
    }
    return blyqt_send_post_request(URL, payload)


def update_blyqt_miscellaneous_settings(updated_settings_json):
    URL = f"{BLYQT_API_PREFIX}/liteunit/settings/miscellaneous"
    payload = {
        "buzzer_on": updated_settings_json["hmi"]["buzzer"],
        "glasses_led": "continuous-blinking",  # TODO: retrieve from JS
    }
    return blyqt_send_post_request(URL, payload)


def blyqt_send_post_request(endpoint="", payload=None):
    if not endpoint:
        logger.fatal(f"Provide a valid endpoint to send request, got: `{endpoint}`")
    headers = {"Content-Type": "application/json",
               "accept": "application/json"}
    logger.debug(f"{endpoint=}")
    if payload:
        response = requests.post(endpoint, json=payload, headers=headers, verify=False)
    else:
        response = requests.post(endpoint, headers=headers, verify=False)
    logger.info(f"HTTP POST request send, got: {response}")
    return response.status_code == 200


def blyqt_start_recording():
    URL = f"{BLYQT_API_PREFIX}/liteunit/recording/front/start"
    return blyqt_send_post_request(URL)


def blyqt_stop_recording():
    URL = f"{BLYQT_API_PREFIX}/liteunit/recording/front/stop"
    return blyqt_send_post_request(URL)


def blyqt_start_front_live():
    URL = f"{BLYQT_API_PREFIX}/liteunit/live/front/start"
    return blyqt_send_post_request(URL)


def blyqt_stop_front_live():
    URL = f"{BLYQT_API_PREFIX}/liteunit/live/front/stop"
    return blyqt_send_post_request(URL)


def blyqt_start_eye_live():
    URL = f"{BLYQT_API_PREFIX}/liteunit/live/eye/start"
    return blyqt_send_post_request(URL)


def blyqt_stop_eye_live():
    URL = f"{BLYQT_API_PREFIX}/liteunit/live/eye/stop"
    return blyqt_send_post_request(URL)
