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
from utils import LOGGER, save_to_csv
from show_display import Display


class PhenoStation:
    """
    PhenoStation class, contains all the variables and functions of the station
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
    cam = None  # picamera2
    client = None
    st7735 = None  # ST7735 display (device)
    disp = None  # ST7735 display (object)
    hx = None  # hx711 controller
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

    WEIGHT_FILE = "data/weight_values.csv"

    def __init__(self) -> None:
        """
        Initialize the station
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
        self.disp = Display(self.st7735, self.WIDTH, self.HEIGHT)
        self.disp.show_image("assets/logo_elia.jpg")

        # Hx711
        self.hx = DebugHx711(dout_pin=5, pd_sck_pin=6)
        try:
            LOGGER.debug("Resetting HX711")
            self.hx.reset()
        except hx711.GenericHX711Exception as e:
            LOGGER.error(f"Error while resetting HX711 : {e}")
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

        # Create the weight_values.csv file if it doesn't exist
        if not os.path.exists(self.WEIGHT_FILE):
            save_to_csv([
                "raw_weight", "time_raw_weight",
                "avg_10", "time_avg_10",
                "avg_100", "time_avg_100",
                "avg_1000", "time_avg_1000",
                "flt_10", "time_flt_10",
                "flt_100", "time_flt_100",
                "flt_1000", "time_flt_1000"],
                        self.WEIGHT_FILE)

    def send_to_db(self, point: str, field: str, value) -> None:
        """
        Send data to the InfluxDB
        :param point: String, name of the measurement (ex: Growth)
        :param field: String, name of the field (ex: StationID_1)
        :param value: value of the field, must be a type supported by InfluxDB (int, float, string, boolean)
        """
        self.connected = self.reconnect()

        if not self.connected:
            # Save data to the corresponding csv file in case of connection error (create file if it doesn't exist)
            save_to_csv([point, field, value], f"data/{point}.csv")
            with open(f"data/{point}.csv", "a+") as f:
                now = datetime.datetime.now()  # Influx DB timestamps are in nanoseconds Unix time
                f.write(f"{now},{point},{field},{value}\n")
        else:
            # Send data to the DB
            write_api = self.client.write_api(write_options=SYNCHRONOUS)
            LOGGER.debug(f"Sending data to the DB : {point}: {field} : {str(value)[:12]}")
            if point == "Picture":
                p = Point(point).field(field, value)
            else:
                p = Point(point).field(field, int(value))
            write_api.write(bucket=self.bucket, record=p)

    def reconnect(self) -> bool:
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
                    LOGGER.debug(f"Sending {len(lines)} data from {file} to the DB")
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

    def get_weight(self) -> float:
        """
        Get the weight from the load cell
        :return: the weight, or -1 if there is an error
        """
        raw_data = self.hx.get_raw_data()
        if not raw_data:
            LOGGER.error("Error while getting raw data (no data)")
            return -1
        raw_weight = sum(raw_data) / len(raw_data)
        return raw_weight

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
            name = "img"

        path_img = self.path + "/%s.jpg" % name
        try:
            self.cam.capture_file(file_output=path_img)
        except Exception as e:
            LOGGER.error(f"Error while capturing the photo: {e}")
            path_img = ""
        self.cam.stop_preview()
        self.cam.stop()
        return path_img

    def collect_weight_average(self, n: int = 1) -> float:
        """
        Collect the weight from the load cell with a filter (if n > 1)
        The collected weight is the average of the n measurements (50th percentile)
        :param n: number of measurements to take (default: 1)
        :type n: int
        :return: The weight collected from the load cell (filtered if n > 1, raw otherwise)
        :rtype: float
        """
        # Start the measurement
        weight_list = []

        for _ in range(n):
            weight = self.get_weight() - self.tare
            weight_list.append(weight)

        if n == 1:
            return weight_list[0]

        # Take the average of the measurements (acts as the 50th percentile)
        filtered_value = sum(weight_list) / len(weight_list)

        # Return the filtered value
        return filtered_value

    def collect_weight_percentile(self, n: int = 1) -> float:
        """
        Collect the weight from the load cell with a filter (if n > 1)
        The collected weight is the average of the collected measurements, where only the values between the 25th and
        75th percentile are kept
        :param n: number of measurements to take (default: 1)
        :return: The weight collected from the load cell (filtered if n > 1, raw otherwise)
        """
        # Start the measurement
        weight_list = []
        for _ in range(n):
            weight = self.get_weight() - self.tare
            weight_list.append(weight)

        if n == 1:
            return weight_list[0]

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
        filtered_value = sum(weight_list) / len(weight_list)

        # Return the filtered value
        return filtered_value

    def measurement_pipeline(self) -> tuple[int, float]:
        """
        Measurement pipeline
        :return: a tuple with the growth value and the weight
        """
        LOGGER.info("Starting measurement pipeline")
        self.disp.show_collecting_data("Starting measurement pipeline")
        time.sleep(1)

        # Take and process photo
        # Disabled (18/03/2024) to focus on weight collection
        # try:
        #     self.disp.show_collecting_data("Taking photo")
        #     pic, growth_value = "", 0  # self.picture_pipeline()
        # except Exception as e:
        #     LOGGER.error(f"Error while taking the photo: {e}")
        #     self.disp.show_collecting_data("Error while taking the photo")
        #     time.sleep(5)
        #     return 0, 0

        # Get weight
        try:
            weight = self.weight_pipeline()

            # Measurement finished, display the weight
            self.disp.show_collecting_data(f"Weight : {round(weight, 2)}")
            time.sleep(2)
        except Exception as e:
            LOGGER.error(f"Error while getting the weight: {e}")
            self.disp.show_collecting_data("Error while getting the weight")
            time.sleep(5)
            return 0, 0

        # Send data to the DB
        # Disabled (18/03/2024) to focus on weight collection (data is saved to a csv, no need for the DB
        # try:
        #     self.disp.show_collecting_data("Sending data to the DB")
        #     self.database_pipeline(growth_value, weight, pic)
        #     LOGGER.debug("Data sent to the DB")
        #     self.disp.show_collecting_data("Data sent to the DB")
        #     time.sleep(2)
        # except Exception as e:
        #     LOGGER.error(f"Error while sending data to the DB: {e}")
        #     self.disp.show_collecting_data("Error while sending data to the DB")
        #     time.sleep(5)
        #     return 0, 0

        LOGGER.info("Measurement pipeline finished")
        self.disp.show_collecting_data("Measurement pipeline finished")
        time.sleep(1)
        # return growth_value, weight
        return 0, weight

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

    def weight_pipeline(self):
        """
        Weight collection pipeline
        :return: the weight of the plant
        """
        collected = []

        self.disp.show_collecting_data("Getting weight (1)")
        start = time.time()
        weight = self.collect_weight_average(1)
        elp_1 = time.time() - start
        collected.append(weight)
        collected.append(elp_1)

        self.disp.show_collecting_data("Getting weight (avg, 10)")
        start = time.time()
        weight_avg_10 = self.collect_weight_average(10)
        elp_avg_10 = time.time() - start
        collected.append(weight_avg_10)
        collected.append(elp_avg_10)

        self.disp.show_collecting_data("Getting weight (avg, 100)")
        start = time.time()
        weight_avg_100 = self.collect_weight_average(100)
        elp_avg_100 = time.time() - start
        collected.append(weight_avg_100)
        collected.append(elp_avg_100)

        self.disp.show_collecting_data("Getting weight (avg, 1000)")
        start = time.time()
        weight_avg_1000 = self.collect_weight_average(1000)
        elp_avg_1000 = time.time() - start
        collected.append(weight_avg_1000)
        collected.append(elp_avg_1000)

        self.disp.show_collecting_data("Getting weight (per, 10)")
        start = time.time()
        weight_flt_10 = self.collect_weight_percentile(10)
        elp_ftl_10 = time.time() - start
        collected.append(weight_flt_10)
        collected.append(elp_ftl_10)

        self.disp.show_collecting_data("Getting weight (per, 100)")
        start = time.time()
        weight_flt_100 = self.collect_weight_percentile(100)
        elp_ftl_100 = time.time() - start
        collected.append(weight_flt_100)
        collected.append(elp_ftl_100)

        self.disp.show_collecting_data("Getting weight (per, 1000)")
        start = time.time()
        weight_flt_1000 = self.collect_weight_percentile(1000)
        elp_ftl_1000 = time.time() - start
        collected.append(weight_flt_1000)
        collected.append(elp_ftl_1000)

        LOGGER.debug(f"Weight : {weight} in {elp_1}s, {weight_avg_10} in {elp_avg_10}s, {weight_avg_100} in "
                     f"{elp_avg_100}s, {weight_avg_1000} in {elp_avg_1000}s, {weight_flt_10} in {elp_ftl_10}s, "
                     f"{weight_flt_100} in {elp_ftl_100}s, {weight_flt_1000} in {elp_ftl_1000}s")

        # Modification of the 16/03/2024
        # Keep the different weight values in a csv file
        save_to_csv(collected, self.WEIGHT_FILE)
        return weight

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
        # Custom read function to debug (with a max of 100 tries)
        start = time.time()
        data_list = []
        count = 0
        while len(data_list) < times and count < 1000:
            data = self._read()
            if data not in [False, -1]:
                data_list.append(data)
            count += 1
        LOGGER.debug(f"Time to get {len(data_list)} raw data : {round(time.time() - start)} seconds, in {count} tries")
        return data_list
