from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def show_image(disp, width, height, path_img):
    """
    Show an image on the display
    :param disp: ST7735 object
    :param width: width of the display
    :param height: height of the display
    :param path_img: path of the image to show
    :return:
    """
    image = Image.open(path_img)
    image = image.rotate(0).resize((width, height))
    disp.display(image)


def show_logo():
    """
    Show the logo of the station
    :return: an Image object of the logo, resized to 128x70
    """
    logo = Image.open("assets/logo_phenohive.jpg")
    logo = logo.rotate(0).resize((128, 70))
    return logo


def show_measuring_menu(disp, width, height, weight, growth, time_now, time_next_measure, n_rounds):
    """
    Show the measuring menu
    :param disp: ST7735 object
    :param width: width of the display
    :param height: height of the display
    :param weight: weight of the plant
    :param growth: growth value of the plant
    :param time_now: current time
    :param time_next_measure: time of the next measurement
    :param n_rounds: number of the current measurement
    """
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 10)
    draw.text((5, 70), str(time_now), font=font, fill=(0, 0, 0))
    draw.text((0, 90), "Next : " + str(time_next_measure), font=font, fill=(0, 0, 0))
    draw.text((0, 120), "Measurement n°" + str(n_rounds), font=font, fill=(0, 0, 0))
    draw.text((0, 100), "Weight : " + str(weight), font=font, fill=(0, 0, 0))
    draw.text((0, 110), "Growth : " + str(growth), font=font, fill=(0, 0, 0))
    draw.text((80, 130), "Stop -->", font=font, fill=(0, 0, 0))
    logo = show_logo()
    img.paste(logo, (0, 0))
    disp.display(img)


def show_menu(disp, width, height):
    """
    Show the main menu
    :param disp: ST7735 object
    :param width: width of the display
    :param height: height of the display
    """
    # Initialize display.    
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Menu
    font = ImageFont.truetype(FONT, 15)
    draw.text((40, 80), "Menu", font=font, fill=(0, 0, 0))
    # Button
    font = ImageFont.truetype(FONT, 10)
    draw.text((0, 130), "<-- Config        Start -->", font=font, fill=(0, 0, 0))
    logo = show_logo()
    img.paste(logo, (0, 0))
    disp.display(img)


def show_cal_prev_menu(disp, width, height):
    """
    Show the preview menu
    :param disp: ST7735 object
    :param width: width of the display
    :param height: height of the display
    """
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Menu
    font = ImageFont.truetype(FONT, 13)
    draw.text((13, 80), "Configuration", font=font, fill=(0, 0, 0))
    # Button
    font = ImageFont.truetype(FONT, 10)
    draw.text((0, 130), "<-- Calib           Prev -->", font=font, fill=(0, 0, 0))
    logo = show_logo()
    img.paste(logo, (0, 0))
    disp.display(img)


def show_cal_menu(disp, width, height, raw_weight, tare):
    """
    Show the calibration menu
    :param disp: ST7735 object
    :param width: width of the display
    :param height: height of the display
    :param raw_weight: current weight value
    :param tare: tare value
    :return:
    """
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Menu
    font = ImageFont.truetype(FONT, 10)
    draw.text((0, 80), "Tare :" + str(tare), font=font, fill=(0, 0, 0))
    draw.text((0, 95), "Raw val :" + str(raw_weight), font=font, fill=(0, 0, 0))
    # Button
    font = ImageFont.truetype(FONT, 10)
    draw.text((0, 130), "<-- Get Calib    Back -->", font=font, fill=(0, 0, 0))
    logo = show_logo()
    img.paste(logo, (0, 0))
    disp.display(img)


def show_collecting_data(disp, width, height, status):
    """
    Show the collecting data menu
    :param disp: ST7735 object
    :param width: width of the display
    :param height: height of the display
    :param status: status of the station (ex: "Taking photo...")
    """
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Menu
    font = ImageFont.truetype(FONT, 12)
    draw.text((5, 85), "Collecting data...", font=font, fill=(0, 0, 0))
    if status != "":
        font = ImageFont.truetype(FONT, 8)
        draw.text((5, 100), status, font=font, fill=(0, 0, 0))
    logo = show_logo()
    img.paste(logo, (0, 0))
    disp.display(img)
