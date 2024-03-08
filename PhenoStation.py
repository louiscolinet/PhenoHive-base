import base64
import configparser
import os
import time
import datetime
import Adafruit_GPIO.SPI as SPI
import ST7735 as TFT
import hx711
import RPi.GPIO as GPIO
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from picamera2 import Picamera2, Preview
from image_processing import get_total_length
from utils import debug_print
from show_display import show_image, show_collecting_data


class Phenostation:
    """
    Phenostation class, contains all the variables and functions of the station
    """

    # Station variables
    parser = None
    station_id = None
    token = None
    org = None
    bucket = None
    url = None
    path = None
    pot_limit = None
    channel = None
    kernel_size = None
    fill_size = None
    cam = None
    client = None
    disp = None
    hx = None
    time_interval = None
    load_cell_cal = None
    tare = None
    connected = False  # True if the station is connected to influxDB

    # Station constants
    WIDTH = 128
    HEIGHT = 160
    SPEED_HZ = 4000000
    DC = 24
    RST = 25
    SPI_PORT = 0
    SPI_DEVICE = 0
    LED = 23
    BUT_LEFT = 21
    BUT_RIGHT = 16
    HUMIDITY = 18
    MOISTURE_AO = 14
    MOISTURE_DO = 15

    def __init__(self):
        """
        Initialize the Phenostation
        """
        # Parse Config.ini file
        self.parser = configparser.ConfigParser()
        self.parser.read('config.ini')

        self.token = str(self.parser["InfluxDB"]["token"])
        self.org = str(self.parser["InfluxDB"]["org"])
        self.bucket = str(self.parser["InfluxDB"]["bucket"])
        self.url = str(self.parser["InfluxDB"]["url"])

        self.station_id = str(self.parser["ID_station"]["ID"])
        self.path = str(self.parser["Path_to_save_img"]["absolute_path"])

        self.pot_limit = int(self.parser["image_arg"]["pot_limit"])
        self.channel = str(self.parser["image_arg"]["channel"])
        self.kernel_size = int(self.parser["image_arg"]["kernel_size"])
        self.fill_size = int(self.parser["image_arg"]["fill_size"])

        self.time_interval = int(self.parser["time_interval"]["time_interval"])

        # InfluxDB client initialization
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.connected = self.client.ping()
        debug_print(f"InfluxDB client initialized with url : {self.url}, org : {self.org} and token : {self.token}"
                    f", Ping returned : {self.connected}")

        # Screen initialization
        debug_print("Initializing screen")
        self.disp = TFT.ST7735(
            self.DC,
            rst=self.RST,
            spi=SPI.SpiDev(
                self.SPI_PORT,
                self.SPI_DEVICE,
                max_speed_hz=self.SPEED_HZ
            )
        )
        self.disp.clear()
        self.disp.begin()
        show_image(self.disp, self.WIDTH, self.HEIGHT, "assets/logo_elia.jpg")

        # Hx711
        self.hx = DebugHx711(dout_pin=5, pd_sck_pin=6)
        try:
            debug_print("Resetting HX711")
            self.hx.reset()
        except hx711.GenericHX711Exception as e:
            debug_print(f"Error while resetting HX711 : {e}")
        else:
            debug_print("HX711 ready to use")

        # Load cell calibration coefficient
        self.load_cell_cal = float(self.parser["cal_coef"]["load_cell_cal"])
        self.tare = float(self.parser["cal_coef"]["tare"])

        # Camera and LED init
        self.cam = Picamera2()
        GPIO.setwarnings(False)

        GPIO.setup(self.LED, GPIO.OUT)
        GPIO.output(self.LED, GPIO.HIGH)

        # Button init
        GPIO.setup(self.BUT_LEFT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.BUT_RIGHT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def photo(self, preview=False, time_to_wait=8):
        """
        Take a photo and save it
        :param preview: if True, the photo will be saved as "img.jpg"
        :param time_to_wait: time to wait before taking the photo
        :return: the path to the photo
        """
        self.cam.start_preview(Preview.NULL)
        self.cam.start()
        time.sleep(time_to_wait)
        if not preview:
            name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        else:
            name = "img"

        path_img = self.path + "/%s.jpg" % name
        try:
            self.cam.capture_file(file_output=path_img)
        except Exception as e:
            debug_print(f"Error while capturing the photo: {e}")
            path_img = ""
        self.cam.stop_preview()
        self.cam.stop()
        return path_img

    def send_to_db(self, point, field, value):
        """
        Send data to the InfluxDB
        :param point: String, name of the measurement (ex: Growth)
        :param field: String, name of the field (ex: StationID_1)
        :param value: value of the field, must be a type supported by InfluxDB (int, float, string, boolean)
        """
        self.connected = self.reconnect()

        if not self.connected:
            # Save data to the corresponding csv file in case of connection error (create file if it doesn't exist)
            with open(f"data/{point}.csv", "a+") as f:
                now = datetime.datetime.now()  # Influx DB timestamps are in nanoseconds Unix time
                f.write(f"{now},{point},{field},{value}\n")
        else:
            # Send data to the DB
            write_api = self.client.write_api(write_options=SYNCHRONOUS)
            if point == "Picture":
                debug_print(f"Sending data to the DB : {point}")
            else:
                debug_print(f"Sending data to the DB : {point}: {value}")
            if point == "Picture":
                p = Point(point).field(field, value)
            else:
                p = Point(point).field(field, int(value))
            write_api.write(bucket=self.bucket, record=p)

    def reconnect(self):
        """
        Try to reconnect to the InfluxDB and send the data saved in the csv files
        :return: True if the connection is successful, False otherwise
                 If the connection is successful, the data saved in the csv files are sent to the DB
        """
        ping = self.client.ping()
        if not ping:
            return False
        for file in os.listdir("data/"):
            if file.endswith(".csv"):
                with open(f"data/{file}", "r") as f:
                    lines = f.readlines()
                    debug_print(f"Sending {len(lines)} data from {file} to the DB")
                    for line in lines:
                        line = line.strip().split(",")
                        timestamp = line[0]
                        point = line[1]
                        field = line[2]
                        value = line[3]
                        write_api = self.client.write_api(write_options=SYNCHRONOUS)
                        if point == "Picture":
                            write_api.write(bucket=self.bucket, record=Point(point).field(field, value),
                                            time=timestamp)
                        else:
                            write_api.write(bucket=self.bucket, record=Point(point).field(field, int(float(value))),
                                            time=timestamp)
                # os.remove(f"data/{file}")
                # Rename the file to keep a trace of the data sent (add a timestamp to the filename)
                new_name = f"data/sent/{file.split('.')[0]}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
                os.rename(f"data/{file}", f"{new_name}")
        return True

    def get_weight(self):
        """
        Get the weight from the load cell
        :return: the weight, or -1 if there is an error
        """
        raw_data = self.hx.get_raw_data()
        if not raw_data:
            debug_print("Error while getting raw data (no data)")
            return -1
        raw_weight = sum(raw_data) / len(raw_data)
        return raw_weight

    def take_photo(self):
        """
        Take a photo and display it on the screen, and return it in base64
        :return: a tuple with the photo in base64 and the path to the photo
        """
        # Take photo
        GPIO.output(self.LED, GPIO.LOW)
        path_img = self.photo(preview=False, time_to_wait=6)
        time.sleep(2)
        GPIO.output(self.LED, GPIO.HIGH)
        # Display photo
        if path_img != "":
            debug_print(f"Photo taken and saved at {path_img}")
            show_image(self.disp, self.WIDTH, self.HEIGHT, path_img)
            # Convert image to base64
            with open(path_img, "rb") as image_file:
                pic = base64.b64encode(image_file.read()).decode('utf-8')
            time.sleep(2)
            return pic, path_img
        else:
            return "", ""

    def measurement_pipeline(self):
        """
        Measurement pipeline
        :return: a tuple with the growth value and the weight
        """
        # Get photo
        debug_print("Starting measurement pipeline")
        show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Starting measurement pipeline")
        time.sleep(1)
        try:
            show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Taking photo")
            pic, path_img = self.take_photo()
            show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Processing photo")
            time.sleep(1)
        except Exception as e:
            debug_print(f"Error while taking the photo: {e}")
            show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Error while taking the photo")
            time.sleep(5)
            return 0, 0
        # Get numerical value from the photo
        if pic != "" and path_img != "":
            try:
                growth_value = get_total_length(image_path=path_img, channel=self.channel, kernel_size=self.kernel_size)
                debug_print(f"Growth value : {growth_value}")
                show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, f"Growth value : {round(growth_value, 2)}")
                time.sleep(2)
            except Exception as e:
                debug_print(f"Error while processing the photo: {e}")
                show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Error while processing the photo")
                time.sleep(5)
                return 0, 0
        else:
            growth_value = -1
        # Get weight
        try:
            show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Getting weight")
            # Start the measurement
            weight_list = []
            for _ in range(int(10)):
                weight = self.get_weight() - self.tare
                weight_list.append(weight)

            # Filter the weight list, removing the outliers (keep only the values between the 25th and 75th percentile)
            # This is done to avoid the noise and abnormal values from the load cell
            weight_list.sort()
            q1 = weight_list[int(len(weight_list) / 4)]
            q3 = weight_list[int(3 * len(weight_list) / 4)]
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            weight_list = [x for x in weight_list if lower_bound <= x <= upper_bound]

            # Compute the average weight from the filtered list
            weight = sum(weight_list) / len(weight_list)
            debug_print(f"Weight : {weight}")

            # Measurement finished, display the weight
            show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, f"Weight : {round(weight, 2)}")
            time.sleep(2)
        except Exception as e:
            debug_print(f"Error while getting the weight: {e}")
            show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Error while getting the weight")
            time.sleep(5)
            return 0, 0
        # Send data to the DB
        try:
            show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Sending data to the DB")
            field_id = "StationID_%s" % self.station_id
            debug_print(f"Sending data to the DB with field ID : {field_id}")
            self.send_to_db("Growth", field_id, growth_value)
            self.send_to_db("Weight", field_id, weight)
            self.send_to_db("Picture", field_id, pic)  # Send picture in base64
            debug_print("Data sent to the DB, measurement pipeline finished")
            show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Data sent to the DB")
            time.sleep(2)
        except Exception as e:
            debug_print(f"Error while sending data to the DB: {e}")
            show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Error while sending data to the DB")
            time.sleep(5)
            return 0, 0
        debug_print("Measurement pipeline finished")
        show_collecting_data(self.disp, self.WIDTH, self.HEIGHT, "Measurement pipeline finished")
        time.sleep(1)
        return growth_value, weight


class DebugHx711(hx711.HX711):
    """
    DebugHx711 class, inherits from hx711.HX711
    Modified to avoid the infinite loop in the _read function
    """
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
