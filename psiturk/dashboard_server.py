# Import flask
import os
import argparse
from flask import Flask, render_template, request, Response, jsonify
import werkzeug.serving
import subprocess
from gevent import monkey
from socketio import socketio_manage
from socketio.server import SocketIOServer
import dashboard as Dashboard
import webbrowser
# import zmq
import socket
from config import config
import signal
import urllib2


monkey.patch_all()


def launch_browser(port):
    launchurl = "http://{host}:{port}/dashboard".format(host=config.get("Server Parameters", "host"), port=port)
    webbrowser.open(launchurl, new=1, autoraise=True)

def is_port_available(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('127.0.0.1', port))
        s.shutdown(1)
        return 0
    except:
        return 1

# Pass messages between psiturk and dashboard via socket
# pubsub_socket_port = int(sys.argv[1])
# print(pubsub_socket_port)
# context = zmq.Context()
# pubsub_socket = context.socket(zmq.PUB)
# pubsub_socket.connect("tcp://127.0.0.1:" + str(pubsub_socket_port))

def find_open_port():
    open_port = next(port for port in range(5000, 10000) if is_port_available(port))
    return(open_port)

parser = argparse.ArgumentParser(description='Launch psiTurk and psiTurk dashboard.')
parser.add_argument('-p', '--port', default=72361,
                    help='optional port for dashboard. default is 72361.')
args = parser.parse_args()
dashboard_port = args.port

#dashboard_port = find_open_port()


app = Flask("Psiturk_Dashboard")

# Routes for handling dashboard activity
@app.route('/dashboard', methods=['GET'])
def dashboard():
    """
    Serves dashboard.
    """
    return render_template('dashboard.html')

@app.route('/dashboard_model', methods=['GET', 'POST'])
def dashbaord_model():
    """
    Sync for dashboard model.
    """
    config = Dashboard.PsiTurkConfig()

    if request.method == 'GET':
        return jsonify(config.get_serialized())

    if request.method == 'POST':
        config_model = request.json
        config.set_serialized(config_model)

    return render_template('dashboard.html')

@app.route('/at_a_glance_model', methods=['GET'])
def at_a_glance_model():
    """
    Sync for dashboard at-a-glance pane.
    """
    config = Dashboard.PsiTurkConfig()
    services = Dashboard.MTurkServices(config)

    if request.method == 'GET':
        return services.get_summary()

@app.route('/verify_aws_login', methods=['POST'])
def verify_aws():
    """
    """
    config = Dashboard.PsiTurkConfig()
    services = Dashboard.MTurkServices(config)
    key_id = request.json['aws_access_key_id']
    secret_key = request.json['aws_secret_access_key']
    is_valid = str(bool(services.verify_aws_login(key_id, secret_key)))
    return jsonify(aws_accnt=is_valid)


@app.route('/mturk_services', methods=['POST'])
def turk_services():
    """
    """
    config = Dashboard.PsiTurkConfig()
    services = Dashboard.MTurkServices(config)
    mturk_request = request.json
    if "mturk_request" in request.json:
        if request.json["mturk_request"] == "create_hit":
            services.create_hit()
            return("hit created")
        elif request.json["mturk_request"] == "expire_hit":
            hitid = request.json["hitid"]
            services.expire_hit(hitid)
            return("hit expired")
        elif request.json["mturk_request"] == "extend_hit":
           hitid = request.json["hitid"]
           assignments_increment = request.json["assignments_increment"]
           expiration_increment = request.json["expiration_increment"]
           services.extend_hit(hitid, assignments_increment, expiration_increment)
           return("hit expired")
    return "psiTurk failed to recognize your request."

@app.route('/get_hits', methods=['GET'])
def get_hits():
    """
    """
    config = Dashboard.PsiTurkConfig()
    services = Dashboard.MTurkServices(config)
    return(jsonify(hits=services.get_active_hits()))

@app.route('/monitor_server', methods=['GET'])
def monitor_server():
    config = Dashboard.PsiTurkConfig()
    server = Dashboard.Server(port=config.port)
    server.start_monitoring()
    return "Monitoring..."

@app.route('/is_port_available', methods=['POST'])
def is_port_available_route():
    """
    Check if port is available on localhost
    """
    if request.method == 'POST':
        test_port = request.json['port']
        config = Dashboard.PsiTurkConfig()
        if test_port == config.port:
            is_available = 1
        else:
            server = Dashboard.Server(port=test_port)
            is_available = server.is_port_available(test_port)
        return jsonify(is_available=is_available)
    return "port check"

@app.route('/socket.io/<path:rest>')
def push_stream(rest):
    try:
        socketio_manage(request.environ, {
          '/server_status': Dashboard.ServerNamespace
        }, request)
    except:
        app.logger.error("Exception while handling socketio connection",
                     exc_info=True)
    return "socket attempt"

@app.route("/server_status", methods=["GET"])
def status():
    status = request.args.get('status', None)
    if status:
        Dashboard.ServerNamespace.broadcast('status', status)
        return Response("Status change")
    else:
        return Response("Missing status")

@app.route("/participant_status", methods=["GET"])
def participant_status():
    database = Dashboard.Database()
    status = database.get_participant_status()
    return status


#----------------------------------------------
# psiTurk server routes
#----------------------------------------------
@app.route("/launch", methods=["GET"])
def launch():
    subprocess.Popen("python psiturk_server.py", shell=True)
    return "psiTurk launching..."

@app.route("/shutdown_dashboard", methods=["GET"])
def shutdown():
    print("shutting down dashboard...")
    pid = os.getpid()
    os.kill(pid, signal.SIGKILL)
    return("shutting down dashboard...")

@app.route("/shutdown_psiturk", methods=["GET"])
def shutdown_psiturk():
    config = Dashboard.PsiTurkConfig()
    psiturk_server_url = "http://"+config.get("Server Parameters", "host")+":"+config.get("Server Parameters", "port")+"/ppid"
    ppid_request = urllib2.Request(psiturk_server_url)
    ppid = urllib2.urlopen(ppid_request).read()
    print("shutting down dashboard...")
    os.kill(int(ppid), signal.SIGKILL)
    return("shutting down dashboard...")

@werkzeug.serving.run_with_reloader
def run_dev_server():
    app.debug = True
    port = dashboard_port
    config = Dashboard.PsiTurkConfig()
    launch_browser(port)
    SocketIOServer(('', int(port)), app, resource="socket.io").serve_forever() 

if __name__ == "__main__":
    app.run(debug=True, port=dashboard_port)
    run_dev_server()