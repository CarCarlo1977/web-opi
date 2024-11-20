from flask import Flask, render_template, redirect, url_for, session
import wiringpi
import os
import threading
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Set a secret key for session management. You can use os.urandom to generate a random secret key.
app.config['SECRET_KEY'] = os.urandom(24)  # Generates a random 24-byte key


DEFAULT_LISTEN_ADDR = '0.0.0.0'
DEFAULT_LISTEN_PORT = 8081
wiringpi.wiringPiSetup()

GPIOs = {
    1: {'nome': 'GPIO 1', 'status': wiringpi.LOW},
    2: {'nome': 'GPIO 2', 'status': wiringpi.LOW},
    3: {'nome': 'GPIO 3', 'status': wiringpi.LOW},
    4: {'nome': 'GPIO 4', 'status': wiringpi.LOW},
    15: {'nome': 'GPIO 15', 'status': wiringpi.LOW},
    22: {'nome': 'GPIO 22', 'status': wiringpi.LOW}
}

temp = float(open('/sys/class/thermal/thermal_zone0/temp').read())
temp = "{0:0.1f} °C".format(temp / 1000)

for pin in GPIOs:
    # set the pins to output mode.
    wiringpi.pinMode(pin, wiringpi.OUTPUT) ;

@app.route("/")
def control_panel():
    """Route that render the main template with current GPIOs status."""
    for GPIO_number in GPIOs:
        GPIOs[GPIO_number]['status'] = wiringpi.digitalRead(GPIO_number)
    data_for_template = {
        'pins': GPIOs,
        'temp': temp
    }
    return render_template('panel.html', **data_for_template)


def change_gpio(gpio_num, value):
    """Changes the current value of the GPIO.

        Args:
            gpio_num (int): the GPIO number to be controlled
            value (str):    'on' to power on the pin, 'off' to power off
    """
    if gpio_num in list(GPIOs.keys()):
        status = {'on': True, 'off': False}.get(value)
        wiringpi.digitalWrite(gpio_num, status)


def speak(pin_number, status):
    """Uses the mpg123 program to play an audio based on the taken action"""
    os.system("mpg123 " + os.path.abspath("static/audio/{}-{}.mp3".format(pin_number, status)))


@app.route("/<pin_number>/<status>")
def send_action(pin_number, status):
    """Route that render the updated GPIO's status after an taken action
        On button press, two threads starts: one for speaking the action, other
        for changing the GPIO status.
    """
    f1 = threading.Thread(target=speak, args=[int(pin_number), status])
    f2 = threading.Thread(target=change_gpio, args=[int(pin_number), status])
    f1.start()
    f2.start()
    for GPIO_number in GPIOs:
        GPIOs[GPIO_number]['status'] = wiringpi.digitalRead(GPIO_number)
    data_for_template = {
        'pins': GPIOs,
        'temp': temp
    }
    #return render_template('panel.html', **data_for_template)
    # Redirect the user back to the main control panel
    return redirect(url_for('panel'))  # Redirect to the main panel route

@app.route('/')
def panel():
    """Route to render the control panel with the GPIO statuses."""
    data_for_template = {
        'pins': GPIOs,
        'temp': temp
    }
    return render_template('panel.html', **data_for_template)

@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Route to shutdown the system."""
    if 'shutdown_flag' in session and session['shutdown_flag']:
        # If the flag is already set, do nothing (prevent repeated shutdown)
        return redirect(url_for('panel'))

    session['shutdown_flag'] = True  # Set the flag so the shutdown doesn't happen again if refreshed
    os.system("sudo shutdown now")  # Executes the shutdown command
    return redirect(url_for('panel'))  # Redirect back to the panel or show a shutdown page

@app.route("/restart", methods=["POST"])
def restart():
    """Route to restart the system."""
    if 'restart_flag' in session and session['restart_flag']:
        # If the flag is already set, do nothing (prevent repeated restart)
        return redirect(url_for('panel'))

    session['restart_flag'] = True  # Set the flag so the restart doesn't happen again if refreshed
    os.system("sudo reboot")  # Executes the reboot command
    return redirect(url_for('panel'))  # Redirect back to the panel or show a restart page

# Clear the session flags after the operation is complete (to prevent accidental repeated shutdown or restart)
@app.before_request
def clear_flags():
    if 'shutdown_flag' in session:
        session.pop('shutdown_flag')
    if 'restart_flag' in session:
        session.pop('restart_flag')

if __name__ == "__main__":
    app.run(host=DEFAULT_LISTEN_ADDR, port=DEFAULT_LISTEN_PORT)
