"""
Script python qui récupère les images et les mesures de poids et les envoies à la base de données influxDB
"""
import base64
import subprocess
import time
import datetime
import RPi.GPIO as gpio
import hx711
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


class DebugHx711(HX711):
    def __init__(self, dout_pin, pd_sck_pin):
        super().__init__(dout_pin, pd_sck_pin)

    def _read(self, times=10):
        # Custom read function to debug (times=10 to reduce the time of the measurement)
        return super()._read(times)

    def get_raw_data(self, times=5):
        # Custom read function to debug (with a max of 100 tries)
        start = time.time()
        data_list = []
        count = 0
        while len(data_list) < times and count < 1000:
            data = self._read()
            if data not in [False, -1]:
                data_list.append(data)
            count += 1
        debug_print(f"Time to get {len(data_list)} raw data : {round(time.time() - start)} seconds, in {count} tries")
        return data_list


def debug_print(*args):
    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    with open("logs.txt", "a") as f:
        for arg in args:
            f.write(f"{now} - " + str(arg) + "\n")


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

    # InfluxDB client initialization
    client = InfluxDBClient(url=url, token=token, org=org)
    debug_print(f"InfluxDB client initialized with url : {url}, org : {org} and token : {token}"
                f", Ping returned : {client.ping()}")


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
    disp.clear()
    disp.begin()
    show_image(disp, WIDTH, HEIGHT, "/home/pi/Desktop/phenostation/assets/logo_elia.jpg")

    # Hx711
    # hx = HX711(dout_pin=5, pd_sck_pin=6)
    hx = DebugHx711(dout_pin=5, pd_sck_pin=6)
    try:
        debug_print("Resetting HX711")
        hx.reset()
    except hx711.GenericHX711Exception as e:
        debug_print(f"Error while resetting HX711 : {e}")
    else:
        debug_print("HX711 ready to use")
    # raw = hx.get_raw_data()
    # if raw:
    #     debug_print(f"Raw data : {raw")
    # else:
    #     debug_print("Error while getting raw data")

    # Load cell calibration coefficient
    load_cell_cal = float(parser["cal_coef"]["load_cell_cal"])
    tare = float(parser["cal_coef"]["tare"])

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
    if not client.ping():
        # Save data to a csv file in case of connection error
        # now = datetime.datetime.now().strftime("%Y-%m-%d")
        # with open(f"{now}_data.csv", "a") as f:
        with open(f"data.csv", "a") as f:
            now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            f.write(f"{now},{point},{field},{value}\n")
    else:
        # Send data to the DB
        write_api = client.write_api(write_options=SYNCHRONOUS)
        debug_print(f"Sending data to the DB : {point} {field}")  # {value}")
        if point == "Picture":
            debug_print("Picture")
            p = Point(point).field(field, value)
        else:
            p = Point(point).field(field, int(value))
        # p.field(time, datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
        write_api.write(bucket=bucket, record=p)


def get_weight():
    raw_data = hx.get_raw_data()
    if not raw_data:
        debug_print("Error while getting raw data (no data)")
        return -1
    raw_weight = sum(raw_data) / len(raw_data)
    return raw_weight


def take_photo():
    # Take photo
    gpio.output(LED, gpio.LOW)
    path_img = photo(path, preview=False, time_to_wait=6)
    time.sleep(2)
    gpio.output(LED, gpio.HIGH)
    # Display photo
    debug_print(f"Photo taken and saved at {path_img}")
    show_image(disp, WIDTH, HEIGHT, path_img)
    # Convert image to base64
    with open(path_img, "rb") as image_file:
        pic = base64.b64encode(image_file.read()).decode('utf-8')
    time.sleep(2)
    return pic, path_img


def measurement_pipeline():
    global load_cell_cal
    # Get photo
    debug_print("Starting measurement pipeline")
    show_collecting_data(disp, WIDTH, HEIGHT, "Starting measurement pipeline")
    time.sleep(1)
    try:
        show_collecting_data(disp, WIDTH, HEIGHT, "Taking photo")
        pic, path_img = take_photo()
        show_collecting_data(disp, WIDTH, HEIGHT, "Processing photo")
        time.sleep(1)
    except Exception as e:
        debug_print(f"Error while taking the photo: {e}")
        show_collecting_data(disp, WIDTH, HEIGHT, "Error while taking the photo")
        time.sleep(5)
        return 0, 0
    # Get numerical value from the photo
    try:
        growth_value = get_total_length(image_path=path_img, channel=channel, kernel_size=kernel_size)
        debug_print(f"Growth value : {growth_value}")
        show_collecting_data(disp, WIDTH, HEIGHT, f"Growth value : {round(growth_value, 2)}")
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
        show_collecting_data(disp, WIDTH, HEIGHT, f"Weight : {round(weight, 2)}")
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
        send_to_db(client, bucket, "Picture", field_ID, pic)  # Send picture in base64
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
    init()
    n_round = 0

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
                    show_measuring_menu(disp, WIDTH, HEIGHT, round(weight, 2), round(growth_value, 2),
                                        time_now.strftime("%Y/%m/%d %H:%M:%S"),
                                        time_nxt_measure.strftime("%H:%M:%S"),
                                        n_round)

                    if time_now >= time_nxt_measure:
                        debug_print("Measuring time reached, starting measurement")
                        show_collecting_data(disp, WIDTH, HEIGHT, "")
                        growth_value, weight = measurement_pipeline()
                        time_nxt_measure = datetime.datetime.now() + time_delta # Update next measurement time
                        n_round += 1

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
