#!/usr/bin/python3
# import dbus
import colorlog
import logging
import os
from subprocess import check_output, run
import socket
import time
import datetime
from threading import Timer


from advertisement import Advertisement
from service import Application, Service, Characteristic

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
        local_name = "VPS_" + socket.gethostname()
        self.add_local_name(local_name)
        self.include_tx_power = True
        # logger.debug("Debug: Starting BLE advertisement")


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
        # logger.debug("Debug: Adding characteristics to service")


class RemoteControlCharacteristic(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(self, REMOTE_CONTROL_CHARACTERISTIC_UUID, ["write"], service)

    def WriteValue(self, value, options):
        received_value = "".join([chr(byte) for byte in value])
        logger.debug("Debug: Value received: " + received_value)
        # TODO:
        # Start recording trigger


class DeviceStatusCharacteristic(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(self, DEVICE_STATUS_CHARACTERISTIC_UUID, ["read"], service)

    def ReadValue(self, options):
        status = "69,Ready"
        return status.encode("utf-8")


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
        self.update_timer = Timer(1.0, self.periodic_update)
        self.update_timer.start()

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False
        if self.update_timer:
            self.update_timer.cancel()

    def periodic_update(self):
        if self.notifying:
            self.output += "1"
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": self.output.encode("utf-8")}, [])
            self.update_timer = Timer(1.0, self.periodic_update)
            self.update_timer.start()


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


# class CommandCharacteristic(Characteristic):
#     def __init__(self, service):
#         Characteristic.__init__(self, REMOTE_CONTROL_CHARACTERISTIC_UUID, ["write"], service)

#     def WriteValue(self, value, options):
#         received_value = "".join([chr(byte) for byte in value])
#         logger.debug("Debug: Value received: " + received_value)
#         # TODO:
#         # Start recording trigger


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


# def get_connected_ssid():
#     try:
#         output = check_output(["iwgetid", "-r"])
#         connected_ssid = output.strip().decode("utf-8")
#         return connected_ssid
#     except CalledProcessError:
#         return "Not Connected"


def get_connected_ssid():
    output = check_output(["nmcli", "connection", "show", "--active"], universal_newlines=True)
    lines = output.split('\n')
    for line in lines:
        if "wifi" in line:
            return line.split()[0]
    return "Not connected"

# def connect_to_wifi(ssid, password):
#     WPA_SUPPLICANT_CONF_PATH = "/etc/wpa_supplicant/wpa_supplicant.conf"
#     # append new credentials
#     # cmd = f"wpa_passphrase {ssid} {password} | sudo tee -a {WPA_SUPPLICANT_CONF_PATH} > /dev/null"
#     # print(cmd)
#     # os.system(cmd)

#     run_command(f"nmcli d wifi connect {ssid} password {password}")
#     # reconfigure wifi
#     # os.system("wpa_cli -i wlan0 reconfigure")


if __name__ == "__main__":
    LOG_LEVEL = "DEBUG" if not os.environ.get("LOG_LEVEL") else os.environ["LOG_LEVEL"]
    setup_logging(LOG_LEVEL)

    logger.info("Turning on bluetooth")
    # ok = start_bluetooth()
    # if not ok:
    #     logger.error(f"Failed to activate bluetooth")
    # else:
    #     logger.info(f"Bluetooth activated")

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
