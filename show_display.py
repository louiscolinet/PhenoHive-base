from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from ST7735 import TFT

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
LOGO = "assets/logo_phenohive.jpg"


class Display:
    def __init__(self, disp: TFT.ST7735, width: int, height: int) -> None:
        """
        Initialize the class variables
        :param disp: ST7735 display object
        :param width: width of the display
        :param height: height of the display
        """
        self.DISP = disp
        self.DISP.clear()
        self.DISP.begin()
        self.WIDTH = width
        self.HEIGHT = height
        self.SIZE = (self.WIDTH, self.HEIGHT)
        self.LOGO = Image.open(LOGO).rotate(0).resize((128, 70))

    def show_image(self, path_img: str) -> None:
        """
        Show an image on the display
        :param path_img: path of the image to show
        """
        image = Image.open(path_img)
        image = image.rotate(0).resize(self.SIZE)
        self.DISP.display(image)

    def show_measuring_menu(self, weight: float, growth: int, time_now: str, time_next_measure: str, n_rounds: int) -> None:
        """
        Show the measuring menu
        :param weight: weight of the plant
        :param growth: growth value of the plant
        :param time_now: current time
        :param time_next_measure: time of the next measurement
        :param n_rounds: number of the current measurement
        """
        img = Image.new('RGB', self.SIZE, color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(FONT, 10)
        draw.text((5, 70), str(time_now), font=font, fill=(0, 0, 0))
        draw.text((0, 90), "Next : " + str(time_next_measure), font=font, fill=(0, 0, 0))
        draw.text((0, 120), "Measurement n°" + str(n_rounds), font=font, fill=(0, 0, 0))
        draw.text((0, 100), "Weight : " + str(weight), font=font, fill=(0, 0, 0))
        draw.text((0, 110), "Growth : " + str(growth), font=font, fill=(0, 0, 0))
        draw.text((80, 130), "Stop -->", font=font, fill=(0, 0, 0))
        img.paste(self.LOGO, (0, 0))
        self.DISP.display(img)

    def show_menu(self) -> None:
        """
        Show the main menu
        """
        # Initialize display.
        img = Image.new('RGB', self.SIZE, color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # Menu
        font = ImageFont.truetype(FONT, 15)
        draw.text((40, 80), "Menu", font=font, fill=(0, 0, 0))
        # Button
        font = ImageFont.truetype(FONT, 10)
        draw.text((0, 130), "<-- Config        Start -->", font=font, fill=(0, 0, 0))
        img.paste(self.LOGO, (0, 0))
        self.DISP.display(img)

    def show_cal_prev_menu(self) -> None:
        """
        Show the preview menu
        """
        img = Image.new('RGB', self.SIZE, color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # Menu
        font = ImageFont.truetype(FONT, 13)
        draw.text((13, 80), "Configuration", font=font, fill=(0, 0, 0))
        # Button
        font = ImageFont.truetype(FONT, 10)
        draw.text((0, 130), "<-- Calib           Prev -->", font=font, fill=(0, 0, 0))
        img.paste(self.LOGO, (0, 0))
        self.DISP.display(img)

    def show_cal_menu(self, raw_weight, tare) -> None:
        """
        Show the calibration menu
        :param raw_weight: current weight value
        :param tare: tare value
        :return:
        """
        img = Image.new('RGB', self.SIZE, color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # Menu
        font = ImageFont.truetype(FONT, 10)
        draw.text((0, 80), "Tare :" + str(tare), font=font, fill=(0, 0, 0))
        draw.text((0, 95), "Raw val :" + str(raw_weight), font=font, fill=(0, 0, 0))
        # Button
        font = ImageFont.truetype(FONT, 10)
        draw.text((0, 130), "<-- Get Calib    Back -->", font=font, fill=(0, 0, 0))
        img.paste(self.LOGO, (0, 0))
        self.DISP.display(img)

    def show_collecting_data(self, status):
        """
        Show the collecting data menu
        :param status: status of the station (ex: "Taking photo...")
        """
        img = Image.new('RGB', self.SIZE, color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # Menu
        font = ImageFont.truetype(FONT, 12)
        draw.text((5, 85), "Collecting data...", font=font, fill=(0, 0, 0))
        if status != "":
            font = ImageFont.truetype(FONT, 8)
            draw.text((5, 100), status, font=font, fill=(0, 0, 0))
        img.paste(self.LOGO, (0, 0))
        self.DISP.display(img)
