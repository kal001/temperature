# -*- coding: utf-8 -*-

from sqlite3 import dbapi2 as sqlite3
from flask import Flask, Markup, request, session, g, redirect, url_for, abort, render_template, flash

# Stores the current filter options on the data to be displayed
defaults = {
    'ultimodia': True,
    'periodo': '24',
    'pordatas': False,
    'datainicio': '2013-12-01',
    'datafim': '2013-12-31',
    'sensoresaver': []
}

# Dictionary with the available sensors on the current graph
dictsensores = {}

# create application
app = Flask(__name__)

# Load default config and override config from a local file
app.config.update(dict(
    DATABASE='/Users/FernandoLourenco/Dropbox/Raspberry Pi/temperatura/templog.db',
    DEBUG=True,
    SECRET_KEY='development key',
    APPVERSION = '0.61'
))
app.config.from_pyfile('settings.cfg', silent=True)


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


@app.route('/')
def show_main():
    option = None

    #todo actualizar com parâmetros do menú
    #todo corrigir datas fixas
    if option is None:
        option = "2013-12-01|2014-01-31"

    # get data from the database
    records = get_data(option, "*", "all")
    minimo = get_data(option, "min(temp)", "oneasfloat")
    if not minimo:
        minimo = 0
    maximo = get_data(option, "max(temp)", "oneasfloat")
    if not maximo:
        maximo = 0
    sensores = get_sensors(option)

    session['showgraph'] = True

    if records:
        graph = print_graph_script(records, minimo, maximo, sensores)
    else:
        graph = ""

    #todo permitir caracteres unicode em graph
    return render_template('show_main.html', graph = Markup(graph))

@app.route('/add', methods=['POST'])
def add_entry():
    if not session.get('logged_in'):
        abort(401)
    db = get_db()
    db.execute('insert into entries (title, text) values (?, ?)',
                 [request.form['title'], request.form['text']])
    db.commit()
    flash('New entry was successfully posted')
    return redirect(url_for('show_entries'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash('You were logged in')
            return redirect(url_for('show_entries'))
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('show_entries'))

@app.route('/about')
def about():
    flash(u"Isto é um programa de visualização de temperatura. Versão: {0}".format(app.config['APPVERSION']))
    return render_template('show_main.html')

def get_data(interval, function, output):
    db = get_db()
    curs = db.cursor()
    query = "SELECT %s FROM temps" % function

    # Create query limited to the sensors to show
    st = ''
    if defaults['sensoresaver']:
        for sens in defaults['sensoresaver']:
            st += "'{0}',".format(sens)
        st = st[:-1]

    if interval is not None:
        if interval == "6" or interval == "12" or interval == "24":
            query += " WHERE timestamp>datetime('now','-%s hours')" % interval
        else:
            datas = interval.split('|')
            query += " WHERE (timestamp>='%s') AND (timestamp<='%s 23:59:59')" % (datas[0], datas[1])
        if defaults['sensoresaver']:
            query += " AND id in ({0})".format(st)
    elif defaults['sensoresaver']:
        query += " WHERE id in ({0})".format(st)

    curs.execute(query)
    if output == "oneasfloat":
        rows = curs.fetchone()
        #conn.close()
        if not rows[0]:
            return None
        else:
            return float(rows[0])
    elif output == "one[0]":
        rows = curs.fetchone()
        #conn.close()
        if not rows:
            return None
        else:
            return rows
    else:
        rows = curs.fetchall()
        #conn.close()
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

    #conn.close()

    dictsensores = {}
    for row in rows[:]:
        dictsensores[row[0]] = row[1]

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
        chart_code += "data.addColumn('number', '{0} {1}');\n".format('Temperatura', str(sensor[1]))
        chart_code += "data.addColumn({type:'string', role:'annotation'});\n"
        chart_code += "data.addColumn({type:'string', role:'annotationText'});\n"

    umsominimo = True
    umsomaximo = True

    for row in records[:]:
        rowstr = "data.addRow([new Date('{0}'), ".format(str(row[0]).replace(' ', 'T'))

        for sensor in sens[:]:
            if str(row[2]) == str(sensor[0]):
                rowstr += "{0},".format(str(round(row[1], 1)))

                if row[1] == minimo and umsominimo:
                    rowstr += "'MIN','{0} C -> {1}',".format(str(round(row[1], 1)), row[0])
                    umsominimo = False
                elif row[1] == maximo and umsomaximo:
                    rowstr += "'MAX','{0} C -> {1}',".format(str(round(row[1], 1)), row[0])
                    umsomaximo = False
                else:
                    rowstr += 'null,null,'
            else:
                rowstr += "null,null,null,"
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
    </script>""" % (
        'Temperatura (C)', int(maximo) + 1, int(minimo), int(maximo) + 1 - int(minimo) + 1, '(dia) Hora')

    return chart_code

if __name__ == '__main__':
    #init_db()
    app.run()
