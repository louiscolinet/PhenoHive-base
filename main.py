"""
Script python qui récupère les images et les mesures de poids et les envoies à la base de données influxDB
"""
import subprocess
import time
import datetime
import RPi.GPIO as gpio
from picamera2 import Picamera2, Preview
from image_processing import get_height_pix, get_total_length
import configparser
import ST7735 as TFT
import Adafruit_GPIO as GPIO
import Adafruit_GPIO.SPI as SPI
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from hx711 import HX711
from show_display import show_image, show_logo, show_measuring_menu, show_menu, show_cal_prev_menu, show_cal_menu, \
    show_collecting_data


def debug_print(*args):
    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    with open("logs.txt", "a") as f:
        for arg in args:
            f.write(f"{now} - " + str(arg) + "\n")


def what_wifi():
    process = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi'], stdout=subprocess.PIPE)
    if process.returncode == 0:
        return process.stdout.decode('utf-8').strip().split(':')[1]
    else:
        return process.stdout.decode('utf-8').strip()


def scan_wifi():
    process = subprocess.run(['nmcli', '-t', '-f', 'SSID,SECURITY,SIGNAL', 'dev', 'wifi'], stdout=subprocess.PIPE)
    wifi_list = process.stdout.decode('utf-8').strip()
    debug_print(f"Wifi list : {wifi_list}")
    # If no wifi available, check if 'wlan0' device is up
    if wifi_list == '':
        process = subprocess.run(['nmcli', 'dev', 'show', 'wlan0'], stdout=subprocess.PIPE)
        wifi_list = process.stdout.decode('utf-8').strip()
        debug_print(f"nmcli dev show wlan0 result : {wifi_list}")
        process = subprocess.run(['nmcli', 'dev', 'wifi'], stdout=subprocess.PIPE)
        wifi_list = process.stdout.decode('utf-8').strip()
        debug_print(f"nmcli dev wifi : {wifi_list}")
    return wifi_list


def is_wifi_available(ssid: str):
    return ssid in [x.split(':')[0] for x in scan_wifi()]


def connect_to(ssid: str, password: str):
    if not is_wifi_available(ssid):
        return False
    subprocess.call(['nmcli', 'd', 'wifi', 'connect', ssid, 'password', password])
    return what_wifi() == ssid


def init():
    global LED, token, org, bucket, url, path, pot_limit, channel, kernel_size, fill_size, cam, client, disp, WIDTH, \
        HEIGHT, but_left, but_right, hx, time_interval, load_cell_cal, tare, ID_station, parser
    # Parse Config.ini file
    parser = configparser.ConfigParser()
    parser.read('config.ini')

    token = str(parser["InfluxDB"]["token"])
    org = str(parser["InfluxDB"]["org"])
    bucket = str(parser["InfluxDB"]["bucket"])
    url = str(parser["InfluxDB"]["url"])

    ID_station = str(parser["ID_station"]["ID"])
    path = str(parser["Path_to_save_img"]["absolute_path"])

    pot_limit = int(parser["image_arg"]["pot_limit"])
    channel = str(parser["image_arg"]["channel"])
    kernel_size = int(parser["image_arg"]["kernel_size"])
    fill_size = int(parser["image_arg"]["fill_size"])

    time_interval = int(parser["time_interval"]["time_interval"])
    debug_print(f"Confing file read : {parser}")

    # InfluxDB client initialization
    client = InfluxDBClient(url=url, token=token, org=org)
    debug_print(f"InfluxDB client initialized with url : {url}, org : {org} and token : {token}",
                f"InfluxDB state : {client.ping()}")

    # Hx711
    hx = HX711(dout_pin=5, pd_sck_pin=6)

    # Load cell calibration coefficient
    load_cell_cal = float(parser["cal_coef"]["load_cell_cal"])
    tare = float(parser["cal_coef"]["tare"])

    # Screen initialization
    WIDTH = 128
    HEIGHT = 160
    SPEED_HZ = 4000000
    DC = 24
    RST = 25
    SPI_PORT = 0
    SPI_DEVICE = 0

    disp = TFT.ST7735(
        DC,
        rst=RST,
        spi=SPI.SpiDev(
            SPI_PORT,
            SPI_DEVICE,
            max_speed_hz=SPEED_HZ))

    # Camera and LED init
    cam = Picamera2()
    gpio.setwarnings(False)

    LED = 23
    gpio.setup(LED, gpio.OUT)
    gpio.output(LED, gpio.HIGH)

    # Button init
    but_left = 21
    but_right = 16
    gpio.setup(but_left, gpio.IN, pull_up_down=gpio.PUD_UP)
    gpio.setup(but_right, gpio.IN, pull_up_down=gpio.PUD_UP)


def photo(path, preview=False, time_to_wait=8):
    cam.start_preview(Preview.NULL)
    cam.start()
    time.sleep(time_to_wait)
    if not preview:
        name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    else:
        name = "img"

    path_img = path + "/%s.jpg" % name
    cam.capture_file(path_img)
    cam.stop_preview()
    cam.stop()
    return path_img


def send_to_db(client, bucket, point, field, value):
    # Save data to a csv file in case of connection error
    with open("data.csv", "a") as f:
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        f.write(f"{now},{point},{field},{value}\n")
    write_api = client.write_api(write_options=SYNCHRONOUS)
    debug_print(f"Sending data to the DB : {point} {field} {value}")
    p = Point(point).field(field, int(value))
    # p = Point(point).field(field, int(value))
    debug_print(f"Point created : {p}")
    write_api.write(bucket=bucket, record=p)
    debug_print("Data sent to the DB")


def get_weight():
    raw_weight = sum(hx.get_raw_data()) / 5
    return raw_weight


def measurement_pipeline():
    global load_cell_cal
    # Get photo
    debug_print("Starting measurement pipeline")
    show_collecting_data(disp, WIDTH, HEIGHT, "Starting measurement pipeline")
    time.sleep(1)
    try:
        show_collecting_data(disp, WIDTH, HEIGHT, "Taking photo")
        gpio.output(LED, gpio.LOW)
        path_img = photo(path, preview=False, time_to_wait=6)
        time.sleep(2)
        gpio.output(LED, gpio.HIGH)
        print(path_img)
        debug_print(f"Photo taken and saved at {path_img}")
        show_collecting_data(disp, WIDTH, HEIGHT, "Processing photo")
        time.sleep(2)
    except Exception as e:
        debug_print(f"Error while taking the photo: {e}")
        show_collecting_data(disp, WIDTH, HEIGHT, "Error while taking the photo")
        time.sleep(5)
        return 0, 0
    # Get numerical value from the photo
    try:
        growth_value = get_total_length(image_path=path_img, channel=channel, kernel_size=kernel_size)
        debug_print(f"Growth value : {growth_value}")
        show_collecting_data(disp, WIDTH, HEIGHT, f"Growth value : {growth_value}")
        time.sleep(2)
    except Exception as e:
        debug_print(f"Error while processing the photo: {e}")
        show_collecting_data(disp, WIDTH, HEIGHT, "Error while processing the photo")
        time.sleep(5)
        return 0, 0
    # Get weight
    try:
        show_collecting_data(disp, WIDTH, HEIGHT, "Getting weight")
        weight = get_weight() - tare
        weight = weight * load_cell_cal
        debug_print(f"Weight : {weight}")
        show_collecting_data(disp, WIDTH, HEIGHT, f"Weight : \n{weight}")
        time.sleep(2)
    except Exception as e:
        debug_print(f"Error while getting the weight: {e}")
        show_collecting_data(disp, WIDTH, HEIGHT, "Error while getting the weight")
        time.sleep(5)
        return 0, 0
    # Send data to the DB
    try:
        show_collecting_data(disp, WIDTH, HEIGHT, "Sending data to the DB")
        field_ID = "StationID_%s" % ID_station
        debug_print(f"Sending data to the DB with field ID : {field_ID}")
        send_to_db(client, bucket, "Growth", field_ID, growth_value)
        send_to_db(client, bucket, "Weight", field_ID, weight)
        debug_print("Data sent to the DB, measurement pipeline finished")
        show_collecting_data(disp, WIDTH, HEIGHT, "Data sent to the DB")
        time.sleep(2)
    except Exception as e:
        debug_print(f"Error while sending data to the DB: {e}")
        show_collecting_data(disp, WIDTH, HEIGHT, "Error while sending data to the DB")
        time.sleep(5)
        return 0, 0
    debug_print("Measurement pipeline finished")
    show_collecting_data(disp, WIDTH, HEIGHT, "Measurement pipeline finished")
    time.sleep(1)
    return growth_value, weight


def main():
    debug_print("---Initializing---")
    interface = subprocess.run(['iwconfig'], stdout=subprocess.PIPE)
    res = connect_to("accesspoint", "0123456789")
    debug_print(f"Wireless interface : {interface.stdout.decode('utf-8').strip()}",
                f"Connection to 'accesspoint' result : {res}",
                f"Current wifi : {what_wifi()}",
                f"Available wifi : {scan_wifi()}")
    init()
    disp.clear()
    disp.begin()
    show_image(disp, WIDTH, HEIGHT, "/home/pi/Desktop/phenostation/assets/logo_elia.jpg")

    while True:
        is_shutdown = int(parser['Var_Verif']["is_shutdown"])
        show_menu(disp, WIDTH, HEIGHT)
        try:
            # Main menu loop
            if not gpio.input(but_left):
                debug_print("Configuration menu loop")
                # Configuration Menu loop
                show_cal_prev_menu(disp, WIDTH, HEIGHT)
                time.sleep(1)
                while True:

                    if not gpio.input(but_right):
                        # Preview loop
                        while True:
                            path_img = photo(path, preview=True, time_to_wait=1)
                            show_image(disp, WIDTH, HEIGHT, path_img)

                            if not gpio.input(but_right):
                                # Go back to the main menu
                                break
                        time.sleep(1)
                        break

                    if not gpio.input(but_left):
                        # Calibration loop
                        global tare, load_cell_cal

                        tare = get_weight()
                        parser['cal_coef']["tare"] = str(tare)
                        raw_weight = 0
                        while True:
                            show_cal_menu(disp, WIDTH, HEIGHT, raw_weight, tare)
                            if not gpio.input(but_left):
                                # Get measurement
                                raw_weight = get_weight()
                                load_cell_cal = 1500 / (raw_weight - tare)
                                parser['cal_coef']["load_cell_cal"] = str(load_cell_cal)
                                with open("config.ini", 'w') as configfile:
                                    parser.write(configfile)

                            if not gpio.input(but_right):
                                # Go back to the main menu
                                break
                        time.sleep(1)
                        break

            if not gpio.input(but_right) or is_shutdown == 1:
                parser['Var_Verif']["is_shutdown"] = str(1)
                with open("config.ini", 'w') as configfile:
                    parser.write(configfile)

                time.sleep(1)
                # Measuring loop
                debug_print("Measuring loop")
                growth_value = 0
                weight = 0
                time_delta = datetime.timedelta(seconds=time_interval)
                time_now = datetime.datetime.now()
                time_nxt_measure = time_now + time_delta
                while True:
                    # Get time
                    time_now = datetime.datetime.now()
                    # Showing measurement
                    show_measuring_menu(disp, WIDTH, HEIGHT, str(weight), str(growth_value),
                                        str(time_now.strftime("%Y/%m/%d %H:%M:%S")),
                                        str(time_nxt_measure.strftime("%H:%M:%S")))

                    if time_now >= time_nxt_measure:
                        debug_print("Measuring time reached, starting measurement")
                        time_nxt_measure = time_now + time_delta
                        show_collecting_data(disp, WIDTH, HEIGHT, "")
                        growth_value, weight = measurement_pipeline()

                    if not gpio.input(but_right):
                        debug_print("Right button pressed, going back to the main menu")
                        parser['Var_Verif']["is_shutdown"] = str(0)
                        with open("config.ini", 'w') as configfile:
                            parser.write(configfile)
                            # Go back to the main menu
                        break
                time.sleep(1)
        except Exception as e:
            debug_print(f"Error : {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
