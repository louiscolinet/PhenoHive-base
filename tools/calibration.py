"""
HX711 calibration script
"""
from hx711 import HX711
import statistics


def get_weight(hx, n=20):
    weight_list = []
    for _ in range(n):
        raw_data = hx.get_raw_data()
        if not raw_data:
            print("Error while getting raw data (no data)")
        else:
            print(f"Median data: {statistics.median(raw_data)}")
            weight_list.append(statistics.median(raw_data))
    print(f"Weight list: {weight_list}\n"
          f"Median: {statistics.median(weight_list)}")
    return statistics.median(weight_list)


if __name__ == "__main__":
    # Initialize the HX711
    hx711 = HX711(dout_pin=5, pd_sck_pin=6)
    print("Resetting HX711")
    hx711.reset()
    print("Taring HX711")
    tare = get_weight(hx711)
    print(f"Tare value: {tare}")
    mode = input("Run in calibration mode? (y/n): ")
    if mode == "y":
        # Calibration mode
        print("Calibration mode")
        real_weight = input("Enter the real weight (in g): ")
        print("Weighting")
        measured = get_weight(hx711, 20)
        coef = float(real_weight) / measured
        print(f"Calibration coefficient: {coef}")
        # Save the calibration coefficient in 'coef.txt'
        with open("coef.txt", 'w') as f:
            f.write(str(coef))
        exit(0)
    else:
        # Normal mode
        # Get the calibration coefficient from 'coef.txt'
        with open("coef.txt", 'r') as f:
            coef = float(f.read())
        print(f"Calibration coefficient: {coef}")
        while True:
            k = input("Enter the number of loops to average the weight, -1 to exit:")
            if k == "-1":
                exit(0)
            print("Measuring")
            measured = get_weight(hx711, int(k))
            # Calculate the weight in g
            weight = measured * coef
            print(f"Weight: {weight} g")
