"""
Script python qui récupère les images et les mesures de poids et les envoie à la base de données influxDB
"""
from PhenoStation import PhenoStation
from show_display import show_image, show_measuring_menu, show_menu, show_cal_prev_menu, show_cal_menu, \
    show_collecting_data
from utils import LOGGER
import time
import datetime
import RPi.GPIO as GPIO

CONFIG_FILE = "config.ini"


def main():
    """
    Main function, initialize the station and start the main loop
    TODO: this main function has a too high cognitive complexity, it should be refactored (10/03/2024: complexity=58)
    """
    LOGGER.info("Initializing the station")
    station = PhenoStation()  # Initialize the station
    n_round = 0

    while True:
        is_shutdown = int(station.parser['Var_Verif']["is_shutdown"])
        show_menu(station.disp, station.WIDTH, station.HEIGHT)
        try:
            # Main menu loop
            if not GPIO.input(station.BUT_LEFT):
                LOGGER.info("Left button pressed, going to the configuration menu")
                # Configuration Menu loop
                show_cal_prev_menu(station.disp, station.WIDTH, station.HEIGHT)
                time.sleep(1)
                while True:

                    if not GPIO.input(station.BUT_RIGHT):
                        # Preview loop
                        while True:
                            path_img = station.photo(preview=True, time_to_wait=1)
                            show_image(station.disp, station.WIDTH, station.HEIGHT, path_img)

                            if not GPIO.input(station.BUT_RIGHT):
                                # Go back to the main menu
                                break
                        time.sleep(1)
                        break

                    if not GPIO.input(station.BUT_LEFT):
                        # Calibration loop
                        station.tare = station.get_weight()
                        station.parser['cal_coef']["tare"] = str(station.tare)
                        raw_weight = 0
                        while True:
                            show_cal_menu(station.disp, station.WIDTH, station.HEIGHT, raw_weight, station.tare)
                            if not GPIO.input(station.BUT_LEFT):
                                # Get measurement
                                raw_weight = station.get_weight()
                                station.load_cell_cal = 1500 / (raw_weight - station.tare)
                                station.parser['cal_coef']["load_cell_cal"] = str(station.load_cell_cal)
                                with open(CONFIG_FILE, 'w') as configfile:
                                    station.parser.write(configfile)

                            if not GPIO.input(station.BUT_RIGHT):
                                # Go back to the main menu
                                break
                        time.sleep(1)
                        break

            if not GPIO.input(station.BUT_RIGHT) or is_shutdown == 1:
                station.parser['Var_Verif']["is_shutdown"] = str(1)
                with open(CONFIG_FILE, 'w') as configfile:
                    station.parser.write(configfile)

                time.sleep(1)
                # Measuring loop
                LOGGER.info("Measuring loop")
                growth_value = 0
                weight = 0
                time_delta = datetime.timedelta(seconds=station.time_interval)
                time_now = datetime.datetime.now()
                time_nxt_measure = time_now + time_delta
                while True:
                    # Get time
                    time_now = datetime.datetime.now()
                    # Showing measurement
                    show_measuring_menu(station.disp, station.WIDTH, station.HEIGHT, round(weight, 2),
                                        round(growth_value, 2), time_now.strftime("%Y/%m/%d %H:%M:%S"),
                                        time_nxt_measure.strftime("%H:%M:%S"), n_round)

                    if time_now >= time_nxt_measure:
                        # If time to measure reached, start measurement
                        LOGGER.info("Measuring time reached, starting measurement")
                        show_collecting_data(station.disp, station.WIDTH, station.HEIGHT, "")
                        growth_value, weight = station.measurement_pipeline()
                        time_nxt_measure = datetime.datetime.now() + time_delta  # Update next measurement time
                        n_round += 1

                    if not GPIO.input(station.BUT_RIGHT):
                        # If right button pressed, go back to the main menu
                        LOGGER.info("Right button pressed, going back to the main menu")
                        station.parser['Var_Verif']["is_shutdown"] = str(0)
                        with open(CONFIG_FILE, 'w') as configfile:
                            station.parser.write(configfile)
                        break
                time.sleep(1)
        except Exception as e:
            # This is a broad catch, it should be refactored to catch only the exceptions that are expected
            LOGGER.error(f"Error : {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
