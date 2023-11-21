"""
Script python qui récupère les images et les mesures de poids et les envoie à la base de données influxDB
"""
from PhenoStation import *
from show_display import show_image, show_measuring_menu, show_menu, show_cal_prev_menu, show_cal_menu, \
    show_collecting_data
from utils import debug_print


def main():
    """
    Main function, initialize the station and start the main loop
    """
    debug_print("---Initializing---")
    Station = Phenostation()  # Initialize the station
    n_round = 0

    while True:
        is_shutdown = int(Station.parser['Var_Verif']["is_shutdown"])
        show_menu(Station.disp, Station.WIDTH, Station.HEIGHT)
        try:
            # Main menu loop
            if not gpio.input(Station.but_left):
                debug_print("Configuration menu loop")
                # Configuration Menu loop
                show_cal_prev_menu(Station.disp, Station.WIDTH, Station.HEIGHT)
                time.sleep(1)
                while True:

                    if not gpio.input(Station.but_right):
                        # Preview loop
                        while True:
                            path_img = Station.photo(preview=True, time_to_wait=1)
                            show_image(Station.disp, Station.WIDTH, Station.HEIGHT, path_img)

                            if not gpio.input(Station.but_right):
                                # Go back to the main menu
                                break
                        time.sleep(1)
                        break

                    if not gpio.input(Station.but_left):
                        # Calibration loop
                        Station.tare = Station.get_weight()
                        Station.parser['cal_coef']["tare"] = str(Station.tare)
                        raw_weight = 0
                        while True:
                            show_cal_menu(Station.disp, Station.WIDTH, Station.HEIGHT, raw_weight, Station.tare)
                            if not gpio.input(Station.but_left):
                                # Get measurement
                                raw_weight = Station.get_weight()
                                Station.load_cell_cal = 1500 / (raw_weight - Station.tare)
                                Station.parser['cal_coef']["load_cell_cal"] = str(Station.load_cell_cal)
                                with open("config.ini", 'w') as configfile:
                                    Station.parser.write(configfile)

                            if not gpio.input(Station.but_right):
                                # Go back to the main menu
                                break
                        time.sleep(1)
                        break

            if not gpio.input(Station.but_right) or is_shutdown == 1:
                Station.parser['Var_Verif']["is_shutdown"] = str(1)
                with open("config.ini", 'w') as configfile:
                    Station.parser.write(configfile)

                time.sleep(1)
                # Measuring loop
                debug_print("Measuring loop")
                growth_value = 0
                weight = 0
                time_delta = datetime.timedelta(seconds=Station.time_interval)
                time_now = datetime.datetime.now()
                time_nxt_measure = time_now + time_delta
                while True:
                    # Get time
                    time_now = datetime.datetime.now()
                    # Showing measurement
                    show_measuring_menu(Station.disp, Station.WIDTH, Station.HEIGHT, round(weight, 2),
                                        round(growth_value, 2), time_now.strftime("%Y/%m/%d %H:%M:%S"),
                                        time_nxt_measure.strftime("%H:%M:%S"), n_round)

                    if time_now >= time_nxt_measure:
                        # If time to measure reached, start measurement
                        debug_print("Measuring time reached, starting measurement")
                        show_collecting_data(Station.disp, Station.WIDTH, Station.HEIGHT, "")
                        growth_value, weight = Station.measurement_pipeline()
                        time_nxt_measure = datetime.datetime.now() + time_delta  # Update next measurement time
                        n_round += 1

                    if not gpio.input(Station.but_right):
                        # If right button pressed, go back to the main menu
                        debug_print("Right button pressed, going back to the main menu")
                        Station.parser['Var_Verif']["is_shutdown"] = str(0)
                        with open("config.ini", 'w') as configfile:
                            Station.parser.write(configfile)
                        break
                time.sleep(1)
        except Exception as e:
            debug_print(f"Error : {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
