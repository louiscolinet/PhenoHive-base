import base64
import configparser
import os
import statistics
import time
import Adafruit_GPIO.SPI as SPI
import ST7735 as TFT
import hx711
import RPi.GPIO as GPIO
import logging
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from picamera2 import Picamera2, Preview
from image_processing import get_total_length
from utils import save_to_csv
from show_display import Display

CONFIG_FILE = "config.ini"
LOGGER = logging.getLogger("PhenoHiveStation")
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DATE_FORMAT_FILE = "%Y-%m-%dT%H-%M-%SZ"  # Date format for file names (no ':', which is not illegal in Windows)


class PhenoHiveStation:
    """
    PhenoHiveStation class, contains all the variables and functions of the station.
    It functions as a singleton. Use PhenoHiveStation.get_instance() method to get an instance.
    """
    # Instance class variable for singleton
    __instance = None

    # Station constants
    WIDTH = -1
    HEIGHT = -1
    SPEED_HZ = -1
    DC = -1
    RST = -1
    SPI_PORT = -1
    SPI_DEVICE = -1
    LED = -1
    BUT_LEFT = -1
    BUT_RIGHT = -1

    # Station variables
    parser = None
    token = ""
    org = ""
    bucket = ""
    url = ""
    station_id = ""
    image_path = ""
    csv_path = ""
    pot_limit = -1
    channel = ""
    kernel_size = -1
    fill_size = -1
    time_interval = -1
    load_cell_cal = -1.0
    tare = -1.0
    status = -1
    last_error = ("", "")

    @staticmethod
    def get_instance() -> 'PhenoHiveStation':
        """
        Static access method to create a new instance of the station if not already initialised.
        Otherwise, return the current instance.
        :return: A PhenoHiveStation instance
        """
        if PhenoHiveStation.__instance is None:
            PhenoHiveStation()
        return PhenoHiveStation.__instance

    def __init__(self) -> None:
        """
        Initialize the station
        :raises RuntimeError: If trying to instantiate a new PhenoHiveStation if one was already instantiated
                                (use get_instance() instead)
        """
        if PhenoHiveStation.__instance is not None:
            raise RuntimeError("PhenoHiveStation class is a singleton. Use PhenoHiveStation.get_instance() to "
                               "initiate it.")
        else:
            PhenoHiveStation.__instance = self

        self.parser = configparser.ConfigParser()

        # Parse Config.ini file
        self.parse_config_file(CONFIG_FILE)
        self.status = 0  # 0: idle, 1: measuring, -1: error

        # InfluxDB client initialization
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.connected = self.client.ping()
        self.last_connection = datetime.now().strftime(DATE_FORMAT)
        LOGGER.debug(f"InfluxDB client initialised with url : {self.url}, org : {self.org} and token : {self.token}" +
                     f", Ping returned : {self.connected}")

        # Screen initialisation
        LOGGER.debug("Initialising screen")
        self.st7735 = TFT.ST7735(
            self.DC,
            rst=self.RST,
            spi=SPI.SpiDev(
                self.SPI_PORT,
                self.SPI_DEVICE,
                max_speed_hz=self.SPEED_HZ
            )
        )
        self.disp = Display(self)
        self.disp.show_image("assets/logo_elia.jpg")

        # Hx711
        self.hx = DebugHx711(dout_pin=5, pd_sck_pin=6)
        try:
            LOGGER.debug("Resetting HX711")
            self.hx.reset()
        except hx711.GenericHX711Exception as e:
            self.register_error(type(e)(f"Error while resetting HX711 : {e}"))
        else:
            LOGGER.debug("HX711 reset")

        # Camera and LED init
        self.cam = Picamera2()
        GPIO.setwarnings(False)
        GPIO.setup(self.LED, GPIO.OUT)
        GPIO.output(self.LED, GPIO.HIGH)

        # Button init
        GPIO.setup(self.BUT_LEFT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.BUT_RIGHT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Initial (placeholder) measurement data
        self.data = {
            "status": self.status,  # current status
            "error_time": self.last_error[0],  # last registered error
            "error_message": str(self.last_error[1]),  # last registered error
            "growth": -1.0,  # plant's growth
            "weight": -1.0,  # plant's (measured) weight
            "weight_g": -1.0,  # plant's (measured) weight in grams (if calibrated)
            "standard_deviation": -1.0,  # measured weight standard deviation
            "picture": ""  # last picture as a base-64 string
        }
        self.to_save = ["growth", "weight", "weight_g", "standard_deviation"]

    def parse_config_file(self, path: str) -> None:
        """
        Parse the config file at the given path and initialise the station's variables with the values
        :param path: the path to the config file
        :raises RuntimeError: If the config file could not be parsed
        """
        try:
            self.parser.read(path)
        except configparser.ParsingError as e:
            LOGGER.error(f"Failed to parse config file: {type(e).__name__}: {e}")
            raise RuntimeError(f"Failed to parse config file {e}")

        self.token = str(self.parser["InfluxDB"]["token"])
        self.org = str(self.parser["InfluxDB"]["org"])
        self.bucket = str(self.parser["InfluxDB"]["bucket"])
        self.url = str(self.parser["InfluxDB"]["url"])
        self.station_id = str(self.parser["Station"]["ID"])
        self.image_path = str(self.parser["Paths"]["image_folder"])
        self.csv_path = str(self.parser["Paths"]["csv_path"])
        self.pot_limit = int(self.parser["image_arg"]["pot_limit"])
        self.channel = str(self.parser["image_arg"]["channel"])
        self.kernel_size = int(self.parser["image_arg"]["kernel_size"])
        self.fill_size = int(self.parser["image_arg"]["fill_size"])
        self.time_interval = int(self.parser["time_interval"]["time_interval"])
        self.WIDTH = int(self.parser["Display"]["width"])
        self.HEIGHT = int(self.parser["Display"]["height"])
        self.SPEED_HZ = int(self.parser["Display"]["speed_hz"])
        self.DC = int(self.parser["Display"]["dc"])
        self.RST = int(self.parser["Display"]["rst"])
        self.SPI_PORT = int(self.parser["Display"]["spi_port"])
        self.SPI_DEVICE = int(self.parser["Display"]["spi_device"])
        self.load_cell_cal = float(self.parser["cal_coef"]["load_cell_cal"])
        self.tare = float(self.parser["cal_coef"]["tare"])
        self.LED = int(self.parser["Camera"]["led"])
        self.BUT_LEFT = int(self.parser["Buttons"]["left"])
        self.BUT_RIGHT = int(self.parser["Buttons"]["right"])

    def register_error(self, exception: Exception) -> None:
        """
        Register an exception by logging it, updating the station's status and sending it to the DB
        :param exception: The exception that occurred
        """
        LOGGER.error(f"{type(exception).__name__}: {exception}")
        timestamp = datetime.now().strftime(DATE_FORMAT)
        self.status = -1
        self.last_error = (timestamp, exception)
        self.data["status"] = self.status
        self.data["error_time"] = self.last_error[0]
        self.data["error_message"] = str(self.last_error[1])

    def send_to_db(self) -> bool:
        """
        Saves the measurements to the csv file, then sends it to InfluxDB (if connected)
        Uses `PhenoHiveStation.measurements` dictionary containing the measurements and their values.
        :return True if the data was sent to the DB, False otherwise
        """
        # Check connection with the database
        self.connected = self.client.ping()
        timestamp = datetime.now().strftime(DATE_FORMAT)

        # If the csv file does not exist, create it with the headers
        if not os.path.exists(self.csv_path):
            save_to_csv(["time"] + self.to_save, self.csv_path)

        # Save data to the corresponding csv file
        measurements_list = [timestamp]
        for key in self.to_save:
            measurements_list.append(self.data[key])
        save_to_csv(measurements_list, "data/measurements.csv")

        if not self.connected:
            return False

        points = []
        for field, value in self.data.items():
            p = Point(f"station_{self.station_id}").field(field, value)
            points.append(p)

        # Send data to the DB
        LOGGER.debug(f"Sending data to the DB: {str(points)}")
        self.write_api.write(bucket=self.bucket, org=self.org, record=points)
        return True

    def get_weight(self, n: int = 15) -> tuple[float, float]:
        """
        Get the weight from the load cell (median of n measurements)
        :param n: the number of measurements to take (default = 15)
        :return: The median of the measurements (-1 in case of error) and the observed standard deviation
        """
        measurements = self.hx.get_raw_data(times=n)
        if not measurements:
            self.register_error(RuntimeError("Error while getting raw data (no data), check load cell connection"))
            return -1.0, -1.0
        return statistics.median(measurements), statistics.stdev(measurements)

    def capture_and_display(self) -> tuple[str, str]:
        """
        Take a photo, display it on the screen and return it in base64
        :return: a tuple with the photo in base64 and the path to the photo
        """
        # Take the photo
        GPIO.output(self.LED, GPIO.LOW)
        path_img = self.save_photo(preview=False, time_to_wait=6)
        time.sleep(2)
        GPIO.output(self.LED, GPIO.HIGH)
        # Display the photo
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
        :param preview: if True the photo will be saved as "img.jpg" (used for the display)
        :param time_to_wait: time to wait before taking the photo (in seconds)
        :return: the path to the photo
        """
        self.cam.start_preview(Preview.NULL)
        self.cam.start()
        time.sleep(time_to_wait)
        if not preview:
            name = datetime.now().strftime(DATE_FORMAT_FILE)
        else:
            name = "preview"

        path_img = self.image_path + "/%s.jpg" % name
        try:
            self.cam.capture_file(file_output=path_img)
        except Exception as e:
            self.register_error(type(e)(f"Error while capturing the photo: {e}"))
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

        # Take and process the photo
        try:
            self.disp.show_collecting_data("Taking photo")
            pic, growth_value = self.picture_pipeline()
            self.data["picture"] = pic
            self.data["growth"] = growth_value
        except Exception as e:
            self.register_error(type(e)(f"Error while taking the photo: {e}"))
            self.disp.show_collecting_data("Error while taking the photo")
            time.sleep(5)
            return 0, 0

        # Get weight
        try:
            weight, std_dev = self.weight_pipeline()
            self.data["weight"] = weight
            self.data["weight_g"] = weight * self.load_cell_cal
            self.data["standard_deviation"] = std_dev

            # Measurement finished, display the weight
            self.disp.show_collecting_data(f"Weight : {round(weight, 2)}")
            time.sleep(2)
        except Exception as e:
            self.register_error(type(e)(f"Error while getting the weight: {e}"))
            self.disp.show_collecting_data("Error while getting the weight")
            time.sleep(5)
            return 0, 0

        # Send data to the DB
        try:
            self.disp.show_collecting_data("Sending data to the DB")
            if self.send_to_db():
                LOGGER.debug("Data sent to the DB")
                self.disp.show_collecting_data("Data sent to the DB")
            else:
                # Data could not be sent to the database but the measurements were still saved to the csv file
                LOGGER.warning("Could not send data to the DB, no connection")
                self.disp.show_collecting_data("Could not send data to the DB, no connection")
            time.sleep(2)
        except Exception as e:
            self.register_error(type(e)(f"Error while sending data to the DB: {e}"))
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
            try:
                growth_value = get_total_length(image_path=path_img, channel=self.channel, kernel_size=self.kernel_size)
            except KeyError:
                self.register_error(KeyError("Error while processing the photo, no segment found in the image."
                                             "Check that the plant is clearly visible."))
                self.disp.show_collecting_data("Error while processing the photo")
                time.sleep(5)
                return pic, 0
            LOGGER.debug(f"Growth value : {growth_value}")
            self.disp.show_collecting_data(f"Growth value : {round(growth_value, 2)}")
            time.sleep(2)
        return pic, growth_value

    def weight_pipeline(self, n=10) -> tuple[float, float]:
        """
        Weight collection pipeline
        :param n: The number of measurements to take (default = 10)
        :return: The median of the measurements (-1 in case of error) and the observed standard deviation
        """
        self.disp.show_collecting_data("Measuring weight")
        start = time.time()
        median_weight, std_dev = self.get_weight(n)
        median_weight = median_weight - self.tare
        if median_weight == -1.0:
            return -1.0, -1.0
        elapsed = time.time() - start
        LOGGER.debug(f"Weight: {median_weight} in {elapsed}s (with standard deviation: {std_dev}")
        return median_weight, std_dev


class DebugHx711(hx711.HX711):
    """
    DebugHx711 class, inherits from hx711.HX711
    Modified to avoid the infinite loop in the _read function
    """

    def __init__(self, dout_pin, pd_sck_pin):
        super().__init__(dout_pin, pd_sck_pin)

    def _read(self, times: int = 10):
        # Custom read function to debug (times=10 to reduce the time of the measurement)
        return super()._read(times)

    def get_raw_data(self, times: int = 5):
        # Modified read function to debug (with a max of 1000 tries) to avoid infinite loops.
        # Furthermore, we check if the data is valid (not False or -1) before appending it to the list
        data_list = []
        count = 0
        while len(data_list) < times and count < 1000:
            data = self._read()
            if data not in [False, -1]:
                data_list.append(data)
            count += 1
        return data_list
