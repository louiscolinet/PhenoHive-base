import datetime


def debug_print(*args):
    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    with open("logs.txt", "a") as f:
        for arg in args:
            f.write(f"{now} - " + str(arg) + "\n")