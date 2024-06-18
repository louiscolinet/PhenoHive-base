#!/bin/bash

# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo "Please run as root: sudo ./monitor.sh"
  exit
fi

PROGRAM_OUTPUT_FILE="running_programs.csv"
RESOURCE_OUTPUT_FILE="resource_usage.csv"
INTERVAL=60 # seconds

# Write the header
echo "Time,PID,CPU%,Memory%,Disk%,Command" > $PROGRAM_OUTPUT_FILE
echo "Time,CPU%,Memory%,Disk%" > $RESOURCE_OUTPUT_FILE

while true; do
    # Get the current time
    TIME=$(date +"%Y-%m-%d %H:%M:%S")

    # Collect the data for each process
    ps -eo pid,%cpu,%mem,comm | tail -n +2 | while read -r line; do
        # Extract the data
        PID=$(echo "$line" | awk '{print $1}')
        CPU=$(echo "$line" | awk '{print $2}')
        MEM=$(echo "$line" | awk '{print $3}')
        COMMAND=$(echo "$line" | awk '{print $4}')

        # Get the disk usage
        DISK=$(du -s /proc/"$PID" | awk '{print $1}')

        # Write the data to the output file
        echo "$TIME,$PID,$CPU,$MEM,$DISK,$COMMAND" >> $PROGRAM_OUTPUT_FILE
    done

    # Collect the overall resource usage
    CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' |  tr , .)
    MEM=$(free | grep Mem | awk '{print $3/$2 * 100}')
    DISK=$(df / | tail -n +2 | awk '{print $5}')
    # Remove the % sign from the disk usage
    DISK=${DISK%?}

    # Write the data to the output file
    echo "$TIME,$CPU,$MEM,$DISK" >> $RESOURCE_OUTPUT_FILE

    # Wait for the next interval
    sleep $INTERVAL
done
