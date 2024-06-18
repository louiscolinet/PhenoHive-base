"""
Main file to run the station
This script starts the main loop of the station, and handles the different menus and measurements
"""
from PhenoStation import PhenoStation
from utils import setup_logger
import time
import datetime
import RPi.GPIO as GPIO
import argparse
import logging

CONFIG_FILE = "config.ini"
LOGGER = None


def main() -> None:
    """
    Main function, initialize the station and start the main loop
    """
    LOGGER.info("Initializing the station")
    station = PhenoStation()  # Initialize the station
    n_round = 0

    while True:
        is_shutdown = int(station.parser['Var_Verif']["is_shutdown"])
        station.disp.show_menu()
        try:
            handle_button_presses(station, is_shutdown, n_round)
        except Exception as e:
            LOGGER.error(f"Error : {e}")
            time.sleep(5)


def handle_button_presses(station: PhenoStation, is_shutdown: int, n_round: int) -> None:
    """
    Function to handle the button presses
    :param station: station object
    :param is_shutdown: shutdown flag
    :param n_round: number of measurement rounds done
    """
    if not GPIO.input(station.BUT_LEFT):
        LOGGER.info("Left button pressed, going to the configuration menu")
        station.disp.show_cal_prev_menu()
        time.sleep(1)
        handle_configuration_menu(station)

    if not GPIO.input(station.BUT_RIGHT) or is_shutdown:
        station.parser['Var_Verif']["is_shutdown"] = str(1)
        with open(CONFIG_FILE, 'w') as configfile:
            station.parser.write(configfile)
        time.sleep(1)
        handle_measurement_loop(station, n_round)


def handle_configuration_menu(station: PhenoStation) -> None:
    """
    Configuration menu
    :param station: station object
    """
    while True:
        if not GPIO.input(station.BUT_RIGHT):
            handle_preview_loop(station)
            time.sleep(1)
            break

        if not GPIO.input(station.BUT_LEFT):
            handle_calibration_loop(station)
            time.sleep(1)
            break


def handle_preview_loop(station: PhenoStation) -> None:
    """
    Preview loop
    :param station: station object
    """
    while True:
        path_img = station.save_photo(preview=True, time_to_wait=1)
        station.disp.show_image(path_img)
        if not GPIO.input(station.BUT_RIGHT):
            break


def handle_calibration_loop(station: PhenoStation) -> None:
    """
    Calibration loop
    :param station: station object
    """
    def tare(station: PhenoStation, n: int = 1) -> float:
        """
        Collect the weight from the load cell with a filter (if n > 1)
        The collected weight is the average of the collected measurements, where only the values between the 25th and
        75th percentile are kept
        :param station: station object
        :param n: number of measurements to take (default: 1)
        :return: The weight collected from the load cell (filtered if n > 1, raw otherwise)
        """
        # Start the measurement
        weight_list = []
        for _ in range(n):
            weight = station.get_weight() - station.tare
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
    
    # station.tare = station.get_weight()  # Deprecated
    station.tare = tare(station, 100)
    station.parser['cal_coef']["tare"] = str(station.tare)
    raw_weight = 0
    while True:
        station.disp.show_cal_menu(raw_weight, station.tare)
        if not GPIO.input(station.BUT_LEFT):
            raw_weight = station.get_weight()
            # TODO: check relevance of 1500 (and more generally of the load_cell_cal parameter)
            station.load_cell_cal = 1500 / (raw_weight - station.tare)
            station.parser['cal_coef']["load_cell_cal"] = str(station.load_cell_cal)
            with open(CONFIG_FILE, 'w') as configfile:
                station.parser.write(configfile)
        if not GPIO.input(station.BUT_RIGHT):
            break


def handle_measurement_loop(station: PhenoStation, n_round: int) -> None:
    """
    Measurement loop
    :param station: station object
    :param n_round: number of measurement rounds done
    """
    LOGGER.info("Measuring loop")
    growth_value = 0
    weight = 0
    time_delta = datetime.timedelta(seconds=station.time_interval)
    time_now = datetime.datetime.now()
    time_nxt_measure = time_now + time_delta
    while True:
        time_now = datetime.datetime.now()
        station.disp.show_measuring_menu(round(weight, 2), round(growth_value, 2),
                                         time_now.strftime("%Y/%m/%d %H:%M:%S"),
                                         time_nxt_measure.strftime("%H:%M:%S"), n_round)

        if time_now >= time_nxt_measure:
            LOGGER.info("Measuring time reached, starting measurement")
            station.disp.show_collecting_data("")
            growth_value, weight = station.measurement_pipeline()
            time_nxt_measure = datetime.datetime.now() + time_delta
            n_round += 1

        if not GPIO.input(station.BUT_RIGHT):
            station.parser['Var_Verif']["is_shutdown"] = str(0)
            with open(CONFIG_FILE, 'w') as configfile:
                station.parser.write(configfile)
            break
    time.sleep(1)


if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description='Définition du niveau de log')
    parser.add_argument('-l', '--logger', type=str, help='Niveau de log (DEBUG, INFO, WARNING, ERROR,'
                                                         'CRITICAL). Défaut = DEBUG', default='DEBUG')
    args = parser.parse_args()

    # Setup logger
    log_level_map = {
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    try:
        LOGGER = setup_logger("PhenoStation", level=log_level_map[args.logger])
    except KeyError:
        LOGGER = setup_logger("PhenoStation", level=logging.DEBUG)

    main()
