#!/usr/bin/python3
import re
import dbus
import colorlog
import logging
import os
from subprocess import check_output, run
import socket
import time
from threading import Timer

from advertisement import Advertisement
from service import Application, Service, Characteristic
from api import blyqt_start_recording, blyqt_stop_recording

logger = logging.getLogger(__name__)


GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
VPS_SERVICE_UUID = "00001000-710e-4a5b-8d75-3e5b444bc3cf"

CSSID_CHARACTERISTIC_UUID = "00002001-710e-4a5b-8d75-3e5b444bc3cf"
IP_CHARACTERISTIC_UUID = "00002002-710e-4a5b-8d75-3e5b444bc3cf"
WIFI_CONFIG_CHARACTERISTIC_UUID = "00002003-710e-4a5b-8d75-3e5b444bc3cf"
TERMINAL_CHARACTERISTIC_UUID = "00002004-710e-4a5b-8d75-3e5b444bc3cf"
LOCALNAME_CHARACTERISTIC_UUID = "00002005-710e-4a5b-8d75-3e5b444bc3cf"
REMOTE_CONTROL_CHARACTERISTIC_UUID = "00002006-710e-4a5b-8d75-3e5b444bc3cf"
DEVICE_STATUS_CHARACTERISTIC_UUID = "00002007-710e-4a5b-8d75-3e5b444bc3cf"


class VpsAdvertisement(Advertisement):
    def __init__(self, index):
        Advertisement.__init__(self, index, "peripheral")
        local_name = "VPS-" + socket.gethostname()
        self.add_local_name(local_name)
        self.include_tx_power = True
        logger.info(f"Starting BLE advertisement")


class VpsService(Service):
    def __init__(self, index):
        Service.__init__(self, index, VPS_SERVICE_UUID, True)
        self.add_characteristic(WifiConnectCharacteristic(self))
        self.add_characteristic(CurrentSSIDCharacteristic(self))
        self.add_characteristic(IPCharacteristic(self))
        self.add_characteristic(LocalNameCharacteristic(self))
        self.add_characteristic(TerminalCharacteristic(self))
        self.add_characteristic(RemoteControlCharacteristic(self))
        self.add_characteristic(DeviceStatusCharacteristic(self))
        logger.info(f"Adding characteristics to service")


class RemoteControlCharacteristic(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(self, REMOTE_CONTROL_CHARACTERISTIC_UUID, ["write"], service)

    def WriteValue(self, value, options):
        # received_value = "".join([chr(byte) for byte in value])  
        received_value = bytearray(value).decode()
        logger.debug("Debug: Value received: " + received_value)
        if received_value == "0":
            blyqt_start_recording()
        elif received_value == "1":
            blyqt_start_recording()

        # TODO:
        # Calibration, reset to factory settings, ..


class DeviceStatusCharacteristic(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(self, DEVICE_STATUS_CHARACTERISTIC_UUID, ["read", "notify"], service)
        self.notifying = False
        self.batLvl = 1

    def ReadValue(self, options):
        self.batLvl = get_batt_level()
        status = "%s,Ready" % (self.batLvl)
        return status.encode("utf-8")
    
    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False


class TerminalCharacteristic(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(
            self, TERMINAL_CHARACTERISTIC_UUID, ["notify", "write", "read"], service
        )
        self.notifying = False
        self.output = "1"
        self.update_timer = None  # Timer for periodic updates

    def ReadValue(self, options):
        self.output += "1"
        print("read terminal {self.output}")
        return self.output.encode("utf-8")

    def WriteValue(self, value, options):
        print(bytearray(value).decode())
        command = bytearray(value).decode()
        self.output = check_output(command, shell=True, universal_newlines=True)
        print(self.output)
        if self.notifying:
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": self.output.encode("utf-8")}, [])

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True
        # self.update_timer = Timer(1.0, self.periodic_update)
        # self.update_timer.start()
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": "1"}, [])
        self.add_timeout(1000, self.set_temperature_callback)

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False
        # if self.update_timer:
        #     self.update_timer.cancel()

    # def periodic_update(self):
    #     if self.notifying:
    #         print("timer")
    #         self.output += "1"
    #         self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": self.output.encode("utf-8")}, [])
    #         self.update_timer = Timer(1.0, self.periodic_update)
    #         self.update_timer.start()

    def set_temperature_callback(self):
        if self.notifying:
            print("trigger")
            value = 1
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])
        return self.notifying

    # def StartNotify(self):
    #     if self.notifying:
    #         return

    #     self.notifying = True

    #     value = self.get_temperature()
    #     self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])
    #     self.add_timeout(NOTIFY_TIMEOUT, self.set_temperature_callback)

    # def StopNotify(self):
    #     self.notifying = False


class WifiConnectCharacteristic(Characteristic):
    def __init__(self, service):
        self.notifying = False
        Characteristic.__init__(self, WIFI_CONFIG_CHARACTERISTIC_UUID, ["write"], service)

    def WriteValue(self, value, options):
        received_value = bytearray(value).decode()
        logger.debug("Debug: Value received: " + received_value)
        ssid, password = received_value.split(",")
        command = f"nmcli d wifi connect {ssid} password {password}"
        ok, stdout, stderr = run_command(command)
        if not ok:
            logger.error(f"Executing command: {command} failed: {stdout=}, {stderr=}")


class CurrentSSIDCharacteristic(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(self, CSSID_CHARACTERISTIC_UUID, ["read"], service)

    def ReadValue(self, options):
        cssid = get_connected_ssid()
        return cssid.encode("utf-8")
    

class IPCharacteristic(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(self, IP_CHARACTERISTIC_UUID, ["read"], service)

    def ReadValue(self, options):
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address.encode("utf-8")


class LocalNameCharacteristic(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(self, LOCALNAME_CHARACTERISTIC_UUID, ["read"], service)

    def ReadValue(self, options):
        host_name = socket.gethostname()
        return host_name.encode("utf-8")


def run_command(command, timeout_sec=0.3):
    result = run(command, shell=True, check=True)
    time.sleep(timeout_sec)
    return result.returncode == 0, result.stdout, result.stderr


def start_bluetooth():
    initialization_commands = [
        "hciconfig hci0 up",
        "hciconfig hci0 piscan",
        "hciconfig hci0 sspmode 1",
    ]
    init_done = True
    for command in initialization_commands:
        ok, stdout, stderr = run_command(command)
        if not ok:
            init_done = False
            logger.error(f"Executing command: {command} failed: {stdout=}, {stderr=}")
    return init_done


def setup_logging(level):
    logger = logging.getLogger()
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "(%(asctime)s) [%(log_color)s%(levelname)-7s] | %(name)s %(filename)s:%(lineno)d | %(message)s"
        )
    )
    logger.addHandler(handler)
    logger.setLevel(level)


def get_connected_ssid():
    output = check_output(["nmcli", "connection", "show", "--active"], universal_newlines=True)
    lines = output.split('\n')
    for line in lines:
        if "wifi" in line:
            return line.split()[0]
    return "Not connected"


def get_batt_level():
    check_batt_status_command = "dbus-send --system --print-reply --dest=io.vpsrecorder.mcucom /io/vpsrecorder/mcucom io.vpsrecorder.mcucom.getBatterySOC boolean:true"
    output = check_output(check_batt_status_command, shell=True, universal_newlines=True)
    match = re.search(r'uint16 (\d+)', output)
    return int(match.group(1))


if __name__ == "__main__":
    LOG_LEVEL = "DEBUG" if not os.environ.get("LOG_LEVEL") else os.environ["LOG_LEVEL"]
    setup_logging(LOG_LEVEL)

    logger.info("Turning on bluetooth")
    ok = start_bluetooth()
    if not ok:
        logger.error(f"Failed to activate bluetooth")
    else:
        logger.info(f"Bluetooth activated")

    app = Application()
    logger.info(f"Application created")
    app.add_service(VpsService(0))
    app.register()
    adv = VpsAdvertisement(0)
    adv.register()
    try:
        logger.info(f"Running the application")
        app.run()
    except KeyboardInterrupt:
        app.quit()
