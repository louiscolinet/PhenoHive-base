import base64
import configparser
import os
import statistics
import time
import datetime
import Adafruit_GPIO.SPI as SPI
import ST7735 as TFT
import hx711
import RPi.GPIO as GPIO
import logging
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from picamera2 import Picamera2, Preview
from image_processing import get_total_length
from utils import save_to_csv
from show_display import Display

LOGGER = logging.getLogger("PhenoStation")


class PhenoStation:
    """
    PhenoStation class, contains all the variables and functions of the station.
    It functions as a singleton. Use PhenoStation.get_instance() method to get an instance.
    """
    # Instance class variable for singleton
    _instance = None

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
    cam = None  # picamera2
    client = None
    st7735 = None  # ST7735 display (device)
    disp = None  # ST7735 display (object)
    hx = None  # hx711 controller
    time_interval = None
    load_cell_cal = None
    tare = None
    connected = False  # True if the station is connected to influxDB
    status = 0  # Current station status (-1= Error, 0 = OK, 1 = Processing)
    last_error = None  # Last error registered as a tuple of the form (timestamp: str, e:Exception)

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

    @staticmethod
    def get_instance():
        """
        Static access method to create a new instance of the station if not already initialized.
        Otherwise, return the current instance.
        :return: A PhenoStation instance
        """
        if PhenoStation._instance is None:
            PhenoStation()
        return PhenoStation._instance

    def __init__(self) -> None:
        """
        Initialize the station
        :raises RuntimeError: If trying to instantiate a new PhenoStation if one was already instantiated
                                (use get_instance() instead)
        """
        if PhenoStation._instance is not None:
            raise RuntimeError("PhenoStation class is a singleton. Use PhenoStation.get_instance() to initiate it.")
        else:
            PhenoStation._instance = self

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
        self.last_connection = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        LOGGER.debug(f"InfluxDB client initialized with url : {self.url}, org : {self.org} and token : {self.token}" +
                     f", Ping returned : {self.connected}")

        # Screen initialization
        LOGGER.debug("Initializing screen")
        self.st7735 = TFT.ST7735(
            self.DC,
            rst=self.RST,
            spi=SPI.SpiDev(
                self.SPI_PORT,
                self.SPI_DEVICE,
                max_speed_hz=self.SPEED_HZ
            )
        )
        self.disp = Display()
        self.disp.show_image("assets/logo_elia.jpg")

        # Hx711
        self.hx = DebugHx711(dout_pin=5, pd_sck_pin=6)
        try:
            LOGGER.debug("Resetting HX711")
            self.hx.reset()
        except hx711.GenericHX711Exception as e:
            self.register_error(Exception(f"Error while resetting HX711 : {e}"))
        else:
            LOGGER.debug("HX711 reset")

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

    def send_to_db(self, point: str, field: str, value) -> None:
        """
        Send data to the InfluxDB
        :param point: String, name of the measurement (ex: Growth)
        :param field: String, name of the field (ex: StationID_1)
        :param value: value of the field, must be a type supported by InfluxDB (int, float, string, boolean)
        """
        self.connected = self.client.ping()

        # Save data to the corresponding csv file (create file if it doesn't exist)
        save_to_csv([point, field, value], f"data/{point}.csv")
        with open(f"data/{point}.csv", "a+") as f:
            now = datetime.datetime.now()
            f.write(f"{now},{point},{field},{value}\n")

        if self.connected:
            # Send data to the DB
            write_api = self.client.write_api(write_options=SYNCHRONOUS)
            LOGGER.debug(f"Sending data to the DB : {point}: {field} : {str(value)[:12]}")
            if point == "Picture":
                p = Point(point).field(field, value)
            else:
                p = Point(point).field(field, int(value))
            write_api.write(bucket=self.bucket, record=p)

    def register_error(self, exception: Exception) -> None:
        """
        Register an exception by logging it, updating the station's status and sending it to the DB
        :param exception: The exception that occurred
        """
        LOGGER.error(f"Error : {exception}")
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.status = -1
        self.last_error = (timestamp, exception)
        self.send_to_db("Error", "StationID_%s" % self.station_id, str(exception))

    def get_weight(self, n=5) -> float:
        """
        Get the weight from the load cell (median of n measurements)
        :param n: the number of measurements to take (default = 5)
        :return: The median of the measurements (-1 in case of error)
        """
        measurements = self.hx.get_raw_data(times=n)
        if not measurements:
            self.register_error(RuntimeError("Error while getting raw data (no data), check load cell connection"))
            return -1
        return statistics.median(measurements)

    def capture_and_display(self) -> tuple[str, str]:
        """
        Take a photo, display it on the screen and return it in base64
        :return: a tuple with the photo in base64 and the path to the photo
        """
        # Take photo
        GPIO.output(self.LED, GPIO.LOW)
        path_img = self.save_photo(preview=False, time_to_wait=6)
        time.sleep(2)
        GPIO.output(self.LED, GPIO.HIGH)
        # Display photo
        if path_img != "":
            LOGGER.debug(f"Photo taken and saved at {path_img}")
            self.disp.show_image(path_img)
            # Convert image to base64
            with open(path_img, "rb") as image_file:
                pic = base64.b64encode(image_file.read()).decode('utf-8')
            time.sleep(2)
            return pic, path_img
        else:
            return "", ""

    def save_photo(self, preview: bool = False, time_to_wait: int = 8) -> str:
        """
        Take a photo and save it
        :param preview: if True, the photo will be saved as "img.jpg" (used for the display)
        :param time_to_wait: time to wait before taking the photo (in seconds)
        :return: the path to the photo
        """
        self.cam.start_preview(Preview.NULL)
        self.cam.start()
        time.sleep(time_to_wait)
        if not preview:
            name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        else:
            name = "preview"

        path_img = self.path + "/%s.jpg" % name
        try:
            self.cam.capture_file(file_output=path_img)
        except Exception as e:
            self.register_error(Exception(f"Error while capturing the photo: {e}"))
            path_img = ""
        self.cam.stop_preview()
        self.cam.stop()
        return path_img

    def measurement_pipeline(self) -> tuple[int, float]:
        """
        Measurement pipeline
        :return: a tuple with the growth value and the weight
        """
        LOGGER.info("Starting measurement pipeline")
        self.status = 1
        self.disp.show_collecting_data("Starting measurement pipeline")
        time.sleep(1)

        # Take and process photo
        try:
            self.disp.show_collecting_data("Taking photo")
            pic, growth_value = self.picture_pipeline()
        except Exception as e:
            self.register_error(Exception(f"Error while taking the photo: {e}"))
            self.disp.show_collecting_data("Error while taking the photo")
            time.sleep(5)
            return 0, 0

        # Get weight
        try:
            weight = self.weight_pipeline()

            # Measurement finished, display the weight
            self.disp.show_collecting_data(f"Weight : {round(weight, 2)}")
            time.sleep(2)
        except Exception as e:
            self.register_error(Exception(f"Error while getting the weight: {e}"))
            self.disp.show_collecting_data("Error while getting the weight")
            time.sleep(5)
            return 0, 0

        # Send data to the DB
        try:
            self.disp.show_collecting_data("Sending data to the DB")
            self.database_pipeline(growth_value, weight, pic)
            LOGGER.debug("Data sent to the DB")
            self.disp.show_collecting_data("Data sent to the DB")
            time.sleep(2)
        except Exception as e:
            self.register_error(Exception(f"Error while sending data to the DB: {e}"))
            self.disp.show_collecting_data("Error while sending data to the DB")
            time.sleep(5)
            return 0, 0

        LOGGER.info("Measurement pipeline finished")
        self.disp.show_collecting_data("Measurement pipeline finished")
        time.sleep(1)
        self.status = 0
        return growth_value, weight

    def picture_pipeline(self) -> tuple[str, int]:
        """
        Picture processing pipeline
        :return: the picture and the growth value
        """
        # Take and display the photo
        pic, path_img = self.capture_and_display()
        self.disp.show_collecting_data("Processing photo")
        time.sleep(1)
        # Process the segment lengths to get the growth value
        growth_value = -1
        if pic != "" and path_img != "":
            growth_value = get_total_length(image_path=path_img, channel=self.channel, kernel_size=self.kernel_size)
            LOGGER.debug(f"Growth value : {growth_value}")
            self.disp.show_collecting_data(f"Growth value : {round(growth_value, 2)}")
            time.sleep(2)
        return pic, growth_value

    def weight_pipeline(self, n=10) -> float:
        """
        Weight collection pipeline
        :param n: The number of measurements to take (default = 10)
        :return: The median weight from the collected measurements
        """
        self.disp.show_collecting_data("Measuring weight")
        start = time.time()
        median_weight = self.get_weight(n)
        if median_weight == -1:
            return -1
        elapsed = time.time() - start
        LOGGER.debug(f"Weight: {median_weight} in {elapsed}s")
        return median_weight

    def database_pipeline(self, growth_value: int, weight: float, pic: str) -> None:
        """
        Send the collected data to the database
        """
        field_id = "StationID_%s" % self.station_id
        LOGGER.debug(f"Sending data to the DB with field ID : {field_id}")
        self.send_to_db("Growth", field_id, growth_value)
        self.send_to_db("Weight", field_id, weight)
        self.send_to_db("Picture", field_id, pic)  # Send picture in base64


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
        # Modified read function to debug (with a max of 1000 tries) to avoid infinite loops
        # Furthermore, we check if the data is valid (not False or -1) before appending it to the list
        data_list = []
        count = 0
        while len(data_list) < times and count < 1000:
            data = self._read()
            if data not in [False, -1]:
                data_list.append(data)
            count += 1
        return data_list
