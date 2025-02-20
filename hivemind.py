import contextlib
import importlib
import io
import os
import time
import subprocess
import sys
from datetime import datetime, timedelta

'''import scan_movies
import scan_shows
import fresh_honey
import scan_interstitials
import scheduler'''

LOG_FILE_PATH = "hivemind.log"

def setup_log_file():
    """Create or refresh the log file at the start of the day."""
    with open(LOG_FILE_PATH, "w") as f:
        f.write(f"Log file created at {datetime.now()}\n")

def refresh_log_file():
    """Clear the log file."""
    with open("script_log.txt", "w") as log_file:
        log_file.write("")  # Clear the file

def write_to_log(content, mode="a"):
    """Write content to the log file, either appending or overwriting."""
    #mode = "w" if overwrite else "a"
    with open(LOG_FILE_PATH, mode) as f:
        f.write(content)

def time_until_midnight():
    """Calculate the seconds remaining until the next midnight."""
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    next_midnight = datetime.combine(tomorrow.date(), datetime.min.time())
    return (next_midnight - now).total_seconds()

def countdown(seconds):
    while seconds > 0:
        print(f"\033[2K\rWaiting {seconds} seconds...",end="", flush=True)
        time.sleep(1)
        seconds -= 1

def seconds_to_hms(seconds):
    # Use divmod to break down seconds into hours, minutes, and seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    # Format as hh:mm:ss with leading zeros
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

def run_scripts(on_start=False):
    """Run the sequence of scripts."""
    scripts = [
        "scan_movies",
        "scan_shows",
        "fresh_honey",
        "scan_interstitials",
        "scheduler"
    ]
    for script in scripts:
        if on_start is False:
            if script in ['fresh_honey', 'scheduler']:
                continue
        if script == 'fresh_honey' and datetime.now().weekday() != 6:
            continue

        try:
            print(f"\nStarting: {script} at {datetime.now()}")
            write_to_log(f"\nStarting: {script} at {datetime.now()}\n")  # Log script start
            # Launch the script 
            #script_module = globals()[script]
            if script in sys.modules:
                script_module = imoprtlib.reload(script)
            else:
                script_module = importlib.import_module(script)

            # Redirect stdout to capture print statements
            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                script_module.main()  # Run the script's main function
                captured_output = buf.getvalue()

            # Process captured output for \r handling
            last_line = ""  # Buffer for lines ending with \r
            for line in captured_output.splitlines():
                if line.endswith("\r"):
                    # Overwrite the buffer for carriage return lines
                    #last_line = line.strip()
                    continue
                else:
                    # Write buffered \r line before new line
                    '''if last_line:
                        write_to_log(f"{last_line}\n", mode="a")
                        last_line = ""  # Clear buffer'''
                    print(line)
                    write_to_log(f"{line}\n", mode="a")

            # Write the last buffered \r line to the log
            if last_line:
                print(line)
                write_to_log(f"{last_line}\n", mode="a")

            # Finalize logging for the script
            write_to_log(f"Finished: {script} at {datetime.now()}\n")
            print(f"Finished: {script} at {datetime.now()}\n")
            
        except Exception as e:
            error_msg = f"Exception occurred while running {script}: {e}"
            print(error_msg)
            write_to_log(f"{error_msg}\n")
            
def main(run_on_start):
    # Create or refresh the log file at the start
    setup_log_file()
    
    # Run scripts
    countdown(10)

    if run_on_start is False:
        output = "\nRunning Initial Library Scan"
        print(output)
        write_to_log(output)
        run_scripts(on_start=False)

    elif run_on_start is True:
        output = "\nRunning daily scripts immediately..."
        print(output)
        write_to_log(output)
        run_scripts(on_start=True)
        
    while True:
        # Calculate the time until 12:05am
        current_time = datetime.now().strftime("%H:%M:%S")
        seconds_until_start = time_until_midnight() + 300
        output=f"\nThe time is {current_time}\n"
        print(output,end="")
        write_to_log(output)
        output = f"{seconds_to_hms(seconds_until_start)} until next run."
        print(output)
        write_to_log(output)
        time.sleep(seconds_until_start) # Sleep until midnight

        refresh_log_file()  # Clear the log at the start of the day

        # Run scripts
        output = "\nRunning daily scripts..."
        print(output)
        write_to_log(output)
        run_scripts(on_start=True)

        # Sleep for an extra 60 seconds to ensure we don't start the loop too early
        countdown(10)

if __name__ == "__main__":
    run_on_start = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "--on_start":
            run_on_start = True

    # Pass the argument to the main function
    main(run_on_start)
