# -*- coding: utf-8 -*-

from sqlite3 import dbapi2 as sqlite3
from time import strftime
import os
from functools import wraps

from flask import Flask, Markup, request, redirect, url_for, \
    render_template, flash, send_from_directory, abort, g, session
from flask.ext.babel import Babel, gettext
import xlwt



#todo change part of the configuration from config to session object
#todo make login with google
#todo add cache

# Dictionary with the available sensors on the current graph
dictsensores = {}

# create application
app = Flask(__name__)

# Load default config and override config from a local file
app.config.update(dict(
    DATABASE='templog.db',
    DEBUG=True,
    SECRET_KEY = 'a34dkkl123',
    APPLICATION_ROOT = '',
    SUBFOLDER = '',
    SERVER_NAME = '',
    ONDISK = '',
    APPVERSION = '0.68',
    ULTIMODIA = True,
    PORDATAS = False,
    PERIODO = '24',
    DATAINICIO = '2013-12-01',
    DATAFIM = '2013-12-31',
    SENSORESAVER = [],
    SHOWGRAPH = True,
    SHOWLASTHOUR = True,
    LANGUAGE = 'en'
))
app.config.from_pyfile('settings.cfg', silent=True)

# available languages
LANGUAGES = {
    'en': 'English',
    'pt': 'Portugues'
}
babel = Babel(app)

_ = gettext

@babel.localeselector
def get_locale():
    return app.config['LANGUAGE'] #request.accept_languages.best_match(LANGUAGES.keys())

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session['logged_in']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def init_db():
    """Creates the database tables."""
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.before_first_request
def appinit():
    session.pop('used_id', None)
    session['logged_in'] = False

@app.before_request
def load_user():
    try:
        user = session["user_id"]
        g.user = user
    except:
        user = None
        g.user = None


@app.route('/')
def show_main():
    global dictsensores

    option = app.config['PERIODO']

    if app.config['PORDATAS']:
        option = app.config['DATAINICIO'] + "|" + app.config['DATAFIM']
    else:
        app.config['DATAINICIO'] = strftime("%Y-%m-%d")
        app.config['DATAFIM'] = strftime("%Y-%m-%d")

    # get data from the database
    records = get_data(option, "*", "all")
    minimo = get_data(option, "min(temp)", "oneasfloat")
    if not minimo:
        minimo = 0
    maximo = get_data(option, "max(temp)", "oneasfloat")
    if not maximo:
        maximo = 0
    sensores = get_sensors(option)

    session['showgraph'] = False
    graph = ""
    if app.config['SHOWGRAPH']:
        if records:
            session['showgraph'] = True
            graph = print_graph_script(records, minimo, maximo, sensores)
        else:
            session['showgraph'] = False
            flash(_('No data to show! Please change Filter options on the above menu.'), 'alert-warning')
            graph = ""
    else:
        session['showgraph'] = False
        graph = ""

    session['showlasthour'] = False
    lasthour = ""
    if app.config['SHOWLASTHOUR']:
        session['showlasthour'] = True

        db = get_db()
        curs = db.cursor()
        rows = curs.execute("SELECT * FROM temps WHERE timestamp>datetime('now','-1 hour') ORDER BY timestamp DESC")

        lasthour = """
        <table class="table">
        <tr>
        <td><strong>"""
        lasthour += _('Date/Hour')
        lasthour += """</strong></td>
        <td><strong>"""
        lasthour += _('Temperature')
        lasthour += """&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp</strong></td>
        <td><strong>"""
        lasthour += _('Sensor')
        lasthour += """</strong></td>
        </tr>
        """

        totalrows = 0
        for row in rows:
            lasthour += "<tr><td>{0}&emsp;&emsp;</td><td>{1:.1f} C</td><td>{2}</td></tr>".format(str(row[0]), float(row[1]),
                                                                                  dictsensores[row[2]])
            totalrows += 1

        lasthour += "</table>"

        if totalrows == 0:
            session['showlasthour'] = False
            flash(_('No last hour data to show!'), 'alert-warning')
            lasthour = ""

    #todo allow unicode characters on graph
    return render_template('show_main.html', graph = Markup(graph), lasthour = Markup(lasthour))

@app.route('/uploads/<path:filename>')
def download_file(filename):
    option = app.config['PERIODO']
    records = get_data(option, "*", "all")

    if records:
        #create excel file with data
        book = xlwt.Workbook(encoding="utf-8")

        sheet1 = book.add_sheet("Sheet 1")

        sheet1.write(0, 0, _('DateTime stamp'))
        sheet1.write(0, 1, _('Temperature'))
        sheet1.write(0, 2, _('Sensor'))

        linha = 1
        for row in records[:]:
            sheet1.write(linha, 0, row[0])
            sheet1.write(linha, 1, row[1])
            sheet1.write(linha, 2, dictsensores[row[2]])
            linha += 1
        book.save(app.config['ONDISK'] + app.config['SUBFOLDER'] + os.sep + 'uploads' + os.sep + filename)

        #flash("Ficheiro: %s" % (app.config['ONDISK'] + app.config['SUBFOLDER'] + os.sep + 'uploads' + os.sep + filename) , "alert-info")
        return send_from_directory(app.config['ONDISK'] + app.config['SUBFOLDER'] + os.sep + 'uploads', filename, as_attachment=True)
    else:
        return redirect(url_for('show_main'))

@app.route('/<path:filename>')
def favicon(filename):
    if filename in ['favicon.ico', 'README', 'robots.txt']:
        return send_from_directory(app.config['ONDISK'] + app.config['SUBFOLDER'], filename)
    else:
        abort(404)

@app.route('/about')
def about():
    flash(_("This is a program to show temperature logs. Version: {0}").format(app.config['APPVERSION']), 'alert-info')
    return redirect(url_for('show_main'))

@app.route('/bydates', methods=['GET', 'POST'])
def bydates():
    app.config['PORDATAS'] = True
    app.config['ULTIMODIA'] = False

    if request.method == 'POST':
        app.config['DATAINICIO'] = request.form['datainicio']
        app.config['DATAFIM'] = request.form['datafim']

        return redirect(url_for('show_main'))
    else:
        selector = """
        <form method="post" action="%s/bydates">
        From <input value=%s name="datainicio" type="date">
        To <input value=%s name="datafim" type="date">
        <button type="submit" class="btn btn-default">
        """ % (app.config['SUBFOLDER'], app.config['DATAINICIO'], app.config['DATAFIM'])
        selector += _('Show')
        selector += "</button></form>"

        flash(Markup(selector), 'alert-info')
        return redirect(url_for('show_main'))

@app.route('/lastday', methods=['GET', 'POST'])
def lastday():
    app.config['PORDATAS'] = False
    app.config['ULTIMODIA'] = True

    if request.method == 'POST':
        app.config['PERIODO'] = request.form['timeinterval']
        return redirect(url_for('show_main'))
    else:
        s1 = ""
        s2 = ""
        s3 = ""
        if app.config['PERIODO'] == "24":
            s3 = 'selected="selected"'
        if app.config['PERIODO'] == "12":
            s2 = 'selected="selected"'
        if app.config['PERIODO'] == "6":
            s1 = 'selected="selected"'

        selector = """
        <form method="post" action="%s/lastday">
        <select name="timeinterval">
        <option value="6" %s>
        """ % (app.config['SUBFOLDER'], s1)
        selector += _('last 6 hours')
        selector += """</option>
        <option value="12" %s>
        """ %s2
        selector += _('last 12 hours')
        selector += """</option>
        <option value="24" %s>
        """ % s3
        selector += _('last 24 hours')
        selector += """</option>
        </select>
        <button type="submit" class="btn btn-default">
        """
        selector += _('Show')
        selector += """</button>
        </form>
        """

        flash(Markup(selector), 'alert-info')
        return redirect(url_for('show_main'))

@app.route('/allsensors')
def allsensors():
    app.config['SENSORESAVER'] = []
    return redirect(url_for('show_main'))

@app.route('/sensorstoshow', methods=['GET', 'POST'])
def sensorstoshow():
    #todo make filter work with multiple sensors
    if request.method == 'POST':
        app.config['SENSORESAVER'] = []
        app.config['SENSORESAVER'].append(request.form['sensores'])
        flash("Form: '{0}'".format(request.form['sensores']), 'alert-info')
        return redirect(url_for('show_main'))
    else:
        selector = """
        <form method="post" action="%s/sensorstoshow">
        <select name="sensores" multiple>
        """ % app.config['SUBFOLDER']

        for sensid in dictsensores:
            if (sensid in app.config['SENSORESAVER']) or (app.config['SENSORESAVER'] == []):
                seleccionado = 'selected="selected"'
            else:
                seleccionado = ''

            selector += '<option %s value="%s">%s</option>' % (seleccionado, sensid, dictsensores[sensid])

        selector += """
        </select>
        <button type="submit" class="btn btn-default">"""
        selector += _('Show')
        selector += """</button>
        </form>
        """

        flash(Markup(selector), "alert-info")
        return redirect(url_for('show_main'))

@app.route('/showgraph')
def showgraph():
    app.config['SHOWGRAPH'] = not app.config['SHOWGRAPH']
    return redirect(url_for('show_main'))

@app.route('/showlasthour')
def showlasthour():
    app.config['SHOWLASTHOUR'] = not app.config['SHOWLASTHOUR']
    return redirect(url_for('show_main'))

@app.route('/editdatabase')
@login_required
def editdatabase():
    db = get_db()
    curs = db.cursor()
    query = "SELECT id, name, baudrate, porta, active FROM sensors"
    curs.execute(query)
    rows = curs.fetchall()
    return render_template('show_database.html', data = rows)

@app.route('/editdatabase/edit/<string:id>')
@login_required
def editdatabase_edit(id):
    session['editdatabase'] = True
    session['databaserow'] = id

    return redirect(url_for('editdatabase'))

@app.route('/editdatabase/saveeditdatabase/<string:id>', methods=['GET', 'POST'])
@login_required
def saveeditdatabase(id):
    session['editdatabase'] = False

    if request.method == 'POST':
        sensid = request.form['id']
        sensname = request.form['name']
        sensbaud = request.form['baud']
        sensport = request.form['port']
        sensactive = request.form['active']

        if id not in ['AA', 'WU', 'WA', '--']:
            db = get_db()
            curs = db.cursor()
            try:
                query = "UPDATE sensors SET id='{0}', name='{1}', baudrate='{2}', porta='{3}', active='{4}' where id='{5}';".\
                    format(sensid, sensname, sensbaud, sensport, sensactive, id)
                curs.execute(query)
                db.commit()
            except sqlite3.OperationalError as e:
                flash(e.message, 'alert-info')
        else:
            flash(_('First sensors of the database are not editable.'), 'alert-warning')

    return redirect(url_for('editdatabase'))

@app.route('/editdatabase/savenewdatabase', methods=['GET', 'POST'])
@login_required
def savenewdatabase():
    session['editdatabase'] = False

    if request.method == 'POST':
        sensid = request.form['id']
        sensname = request.form['name']
        sensbaud = request.form['baud']
        sensport = request.form['port']
        sensactive = request.form['active']

        if len(sensid)>=2:
            try:
                db = get_db()
                curs = db.cursor()
                query = "insert into sensors(id, name, baudrate, porta, active) values ('{0}', '{1}', '{2}', '{3}', '{4}');".\
                    format(sensid, sensname, sensbaud, sensport, sensactive)
                curs.execute(query)
                db.commit()
            except sqlite3.OperationalError as e:
                flash(e.message, 'alert-info')
        else:
            flash(_('Invalid sensor id'), 'alert-warning')

    return redirect(url_for('editdatabase'))

@app.route('/editdatabase/delete/<string:id>')
@login_required
def editdatabase_delete(id):
    if id not in ['AA', 'WU', 'WA', '--']:
        try:
            db = get_db()
            curs = db.cursor()
            query = "delete from sensors where id='{0}';".format(id)
            curs.execute(query)
            db.commit()
        except sqlite3.OperationalError as e:
            flash(e.message, 'alert-info')
    else:
        flash(_('First sensors of the database are not editable.'), 'alert-warning')

    return redirect(url_for('editdatabase'))

@app.route('/editdatabase/canceleditdatabase')
@login_required
def canceleditdatabase():
    session['editdatabase'] = False
    return redirect(url_for('editdatabase'))


@app.route('/en')
def english():
    app.config['LANGUAGE'] = 'en'
    return redirect(url_for('show_main'))


@app.route('/pt')
def portugues():
    app.config['LANGUAGE'] = 'pt'
    return redirect(url_for('show_main'))

@app.route('/login')
def login():
    session['user_id'] = 'FL'
    session['logged_in'] = True
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('used_id', None)
    session['logged_in'] = False
    return render_template('logout.html')

def get_data(interval, function, output):
    db = get_db()
    curs = db.cursor()
    query = "SELECT %s FROM temps" % function

    # Create query limited to the sensors to show
    st = ''
    if app.config['SENSORESAVER']:
        for sens in app.config['SENSORESAVER']:
            st += "'{0}',".format(sens)
        st = st[:-1]

    if interval is not None:
        if interval == "6" or interval == "12" or interval == "24":
            query += " WHERE timestamp>datetime('now','-%s hours')" % interval
        else:
            datas = interval.split('|')
            query += " WHERE (timestamp>='%s') AND (timestamp<='%s 23:59:59')" % (datas[0], datas[1])
        if app.config['SENSORESAVER']:
            query += " AND id in ({0})".format(st)
    elif app.config['SENSORESAVER']:
        query += " WHERE id in ({0})".format(st)

    #flash(query, 'alert-info')
    curs.execute(query)
    if output == "oneasfloat":
        rows = curs.fetchone()

        if not rows[0]:
            return None
        else:
            return float(rows[0])
    elif output == "one[0]":
        rows = curs.fetchone()

        if not rows:
            return None
        else:
            return rows
    else:
        rows = curs.fetchall()

        if not rows:
            return None
        else:
            return rows

def get_sensors(interval):
    global dictsensores

    db = get_db()
    curs = db.cursor()
    query = "SELECT DISTINCT sensors.id, sensors.name FROM sensors,temps"

    if interval is None:
        query += " WHERE sensors.id=temps.id"
    elif interval == "6" or interval == "12" or interval == "24":
        query += " WHERE (sensors.id=temps.id) AND (temps.timestamp>datetime('now','-%s hours'))" % interval
    else:
        datas = interval.split('|')
        query += " WHERE (sensors.id=temps.id) AND (timestamp>='%s') AND (timestamp<='%s 23:59:59')" % (
            datas[0], datas[1])

    curs.execute(query)
    rows = curs.fetchall()

    dictsensores = {}
    for row in rows[:]:
        dictsensores[row[0]] = row[1]
        #flash("Nome: {0}; Id: {1}".format(dictsensores[row[0]], row[0]), 'alert-info')

    return rows

# print the javascript to generate the chart
# pass the table generated from the database info
def print_graph_script(records, minimo, maximo, sens):
    chart_code = """
    <script type="text/javascript" src="https://www.google.com/jsapi"></script>
    <script type="text/javascript">
      google.load("visualization", "1", {packages:["corechart"]});
      google.setOnLoadCallback(drawChart);
      function drawChart() {
        var data = new google.visualization.DataTable();
        data.addColumn('datetime', 'Data');
    """

    for sensor in sens[:]:
        chart_code += "data.addColumn('number', '{0} {1}');\n".format(_('Temperature'), str(sensor[1]))
        #chart_code += "data.addColumn({type:'string', role:'annotation'});\n"
        #chart_code += "data.addColumn({type:'string', role:'annotationText'});\n"

    umsominimo = True
    umsomaximo = True

    for row in records[:]:
        rowstr = "data.addRow([new Date('{0}'), ".format(str(row[0]).replace(' ', 'T'))

        for sensor in sens[:]:
            if str(row[2]) == str(sensor[0]):
                rowstr += "{0},".format(str(round(row[1], 1)))

                #if row[1] == minimo and umsominimo:
                #    rowstr += "'MIN','{0} C -> {1}',".format(str(round(row[1], 1)), row[0])
                #    umsominimo = False
                #elif row[1] == maximo and umsomaximo:
                #    rowstr += "'MAX','{0} C -> {1}',".format(str(round(row[1], 1)), row[0])
                #    umsomaximo = False
                #else:
                #    rowstr += 'null,null,'
            else:
                rowstr += "null," #null,null,"
        rowstr = rowstr[:-1]

        rowstr += "]);\n"
        chart_code += rowstr

    chart_code += """
        var options = {
            title: '%s',
            lineWidth:3,
            curveType: 'function',
            interpolateNulls: true,
            vAxis: {maxValue: %d, minValue: %d, gridlines: {count: %d}},
            hAxis: {title: '%s', format:'(dd) HH:mm', gridLines: {count:-1}}
        };

        var chart = new google.visualization.LineChart(document.getElementById('chart_div'));
        chart.draw(data, options);
      }
    </script>""" % (_('Temperature (C)'), int(maximo) + 1, int(minimo), int(maximo) + 1 - int(minimo) + 1, _('(day) Hour'))

    return chart_code

if __name__ == '__main__':
    #init_db()
    app.run()
