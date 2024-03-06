"""
HX711 calibration script
"""
from hx711 import HX711


def get_weight(hx):
    """
    Get the weight from the load cell
    :return: the weight, or exit if no data
    """
    raw_data = hx.get_raw_data()
    if not raw_data:
        print("Error while getting raw data (no data)")
        exit(-1)
    raw_weight = sum(raw_data) / len(raw_data)
    return raw_weight


def measure_and_filter(hx, k):
    print("Measuring with the new calibration coefficient")
    weight_list = []
    for _ in range(int(k)):
        weight = get_weight(hx711) - tare
        print(f"Weight: {weight}")
        weight_list.append(weight)

    print(f"Unfiltered weight list: {weight_list}")
    print(f"Average weight: {sum(weight_list) / len(weight_list)}")
    # Filter the weight list, removing the outliers (keep only the values between the 25th and 75th percentile)
    weight_list.sort()
    q1 = weight_list[int(len(weight_list) / 4)]
    q3 = weight_list[int(3 * len(weight_list) / 4)]
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    print(f"Lower bound: {lower_bound}")
    print(f"Upper bound: {upper_bound}")
    weight_list = [x for x in weight_list if lower_bound <= x <= upper_bound]
    print(f"Filtered weight list: {weight_list}")
    print(f"Average weight: {sum(weight_list) / len(weight_list)}")
    return weight_list


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
    n = input("Enter the number of loops to average the weight: ")
    print("Weighting")
    lst = measure_and_filter(hx711, n)
    coef = float(real_weight) / (sum(lst) / len(lst))
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
        n = input("Enter the number of loops to average the weight, -1 to exit: ")
        if n == "-1":
            exit(0)
        print("Measuring")
        lst = measure_and_filter(hx711, n)
        # Calculate the weight in g
        weight = sum(lst) / len(lst) * coef
        print(f"Weight: {weight} g")
