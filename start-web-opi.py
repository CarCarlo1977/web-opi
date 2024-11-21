from flask import Flask, render_template, redirect, url_for, session, request
import wiringpi
import os
import threading
import urllib3

# Disable SSL warnings (for the sake of this example)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Set a secret key for session management. You can use os.urandom to generate a random secret key.
app.config['SECRET_KEY'] = os.urandom(24)  # Generates a random 24-byte key

# A hardcoded user for simplicity (you could use a database for real apps)
users = {'carlo': {'password': 'Giosue@2017'}}


# WiringPi setup
DEFAULT_LISTEN_ADDR = '0.0.0.0'
DEFAULT_LISTEN_PORT = 80
wiringpi.wiringPiSetup()

# GPIO pins configuration
GPIOs = {
    1: {'nome': 'GPIO 1', 'status': wiringpi.LOW},
    2: {'nome': 'GPIO 2', 'status': wiringpi.LOW},
    3: {'nome': 'GPIO 3', 'status': wiringpi.LOW},
    4: {'nome': 'GPIO 4', 'status': wiringpi.LOW},
    15: {'nome': 'GPIO 15', 'status': wiringpi.LOW},
    22: {'nome': 'GPIO 22', 'status': wiringpi.LOW}
}
# Login route (No login_required here to prevent loop)
@app.route("/login", methods=["GET", "POST"])
def login():
    # If the user is already logged in, redirect them to the panel
    if 'username' in session:
        return redirect(url_for('panel'))

    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            session['username'] = username
            return redirect(url_for("panel"))
        else:
            return render_template("login.html", error="Invalid credentials, please try again.")

    # Render the login form if GET request
    return render_template("login.html")


# Route for logging out
@app.route("/logout")
def logout():
    session.pop('username', None)  # Manually clear session on logout
    return redirect(url_for('login'))



# Reading temperature
temp = float(open('/sys/class/thermal/thermal_zone0/temp').read())
temp = "{0:0.1f} °C".format(temp / 1000)

# Set the GPIO pins to output mode
for pin in GPIOs:
    wiringpi.pinMode(pin, wiringpi.OUTPUT)


# Route for control panel (main page) after login
@app.route("/")
def panel():
    """Route that renders the main template with current GPIOs status."""
        # Check if the user is logged in
    if 'username' not in session:
        return redirect(url_for('login'))

    for GPIO_number in GPIOs:
        GPIOs[GPIO_number]['status'] = wiringpi.digitalRead(GPIO_number)
    data_for_template = {
        'pins': GPIOs,
        'temp': temp
    }
    return render_template('panel.html', **data_for_template)


# Change GPIO status
def change_gpio(gpio_num, value):
    """Changes the current value of the GPIO.
        Args:
            gpio_num (int): the GPIO number to be controlled
            value (str):    'on' to power on the pin, 'off' to power off
    """
    if gpio_num in list(GPIOs.keys()):
        status = {'on': True, 'off': False}.get(value)
        wiringpi.digitalWrite(gpio_num, status)


# Play a sound with mpg123 (using threading)
def speak(pin_number, status):
    """Uses the mpg123 program to play an audio based on the taken action"""
    os.system("mpg123 " + os.path.abspath(f"static/audio/{pin_number}-{status}.mp3"))


# Route for sending GPIO actions (on/off)
@app.route("/<pin_number>/<status>")
def send_action(pin_number, status):
    """Route that renders the updated GPIO's status after an action is taken"""
        # Check if the user is logged in
    if 'username' not in session:
        return redirect(url_for('login'))

    f1 = threading.Thread(target=speak, args=[int(pin_number), status])
    f2 = threading.Thread(target=change_gpio, args=[int(pin_number), status])
    f1.start()
    f2.start()

    # Update GPIO statuses
    for GPIO_number in GPIOs:
        GPIOs[GPIO_number]['status'] = wiringpi.digitalRead(GPIO_number)

    # Return redirect to the main control panel after the action is performed
    return redirect(url_for('panel'))

@app.route("/VNC")
def vnc():
    # Check if the user is logged in
    if 'username' not in session:
        return redirect(url_for('login'))

    # Get the server's IP address dynamically
    server_ip = request.host.split(':')[0]  # Extract host part (ignores port)
    # Redirect to the VNC server
    return redirect(f"http://{server_ip}:6080/vnc.html")


# Route to shutdown the system
@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Route to shutdown the system."""
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'shutdown_flag' in session and session['shutdown_flag']:
        return redirect(url_for('panel'))  # Prevent shutdown if flag is set

    session['shutdown_flag'] = True
    os.system("sudo shutdown now")  # Executes the shutdown command
    return redirect(url_for('panel'))


# Route to restart the system
@app.route("/restart", methods=["POST"])
def restart():
    """Route to restart the system."""
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'restart_flag' in session and session['restart_flag']:
        return redirect(url_for('panel'))  # Prevent restart if flag is set

    session['restart_flag'] = True
    os.system("sudo reboot")  # Executes the reboot command
    return redirect(url_for('panel'))


# Clear the session flags after the operation is complete
@app.before_request
def clear_flags():
    if 'shutdown_flag' in session:
        session.pop('shutdown_flag')
    if 'restart_flag' in session:
        session.pop('restart_flag')


if __name__ == "__main__":
    app.run(host=DEFAULT_LISTEN_ADDR, port=DEFAULT_LISTEN_PORT)
