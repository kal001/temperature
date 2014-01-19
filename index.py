# -*- coding: utf-8 -*-

from sqlite3 import dbapi2 as sqlite3
from time import strftime
import os

from flask import Flask, Markup, request, session, g, redirect, url_for, render_template, flash, send_from_directory
import xlwt



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
    SERVER_NAME='',
    APPVERSION = '0.65',
    ULTIMODIA = True,
    PORDATAS = False,
    PERIODO = '24',
    DATAINICIO = '2013-12-01',
    DATAFIM = '2013-12-31',
    SENSORESAVER = [],
    SHOWGRAPH = True,
    SHOWLASTHOUR = True
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
            flash('No data to show! Please change Filter options on the above menu.', 'alert-warning')
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
        <td><strong>Date/Hour</strong></td>
        <td><strong>Temperature&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp</strong></td>
        <td><strong>Sensor</strong></td>
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
            flash('No last hour data to show!', 'alert-warning')
            lasthour = ""

    #todo permitir caracteres unicode em graph
    return render_template('show_main.html', graph = Markup(graph), lasthour = Markup(lasthour))

@app.route('/uploads/<path:filename>')
def download_file(filename):
    option = app.config['PERIODO']
    records = get_data(option, "*", "all")

    if records:
        #create excel file with data
        book = xlwt.Workbook(encoding="utf-8")

        sheet1 = book.add_sheet("Sheet 1")

        #todo save sensor name instead of id
        sheet1.write(0, 0, "DateTime stamp")
        sheet1.write(0, 1, "Temperature")
        sheet1.write(0, 2, "Sensor ID")

        linha = 1
        for row in records[:]:
            sheet1.write(linha, 0, row[0])
            sheet1.write(linha, 1, row[1])
            sheet1.write(linha, 2, row[2])
            linha += 1
        # book.save(os.path.join(app.config['APPLICATION_ROOT'],'uploads', 'excelfile.xls'))
        return send_from_directory(os.path.join(app.config['APPLICATION_ROOT'],'uploads'), filename, as_attachment=True)
    else:
        return redirect(url_for('show_main'))

@app.route('/about')
def about():
    flash(u"This is a program to show temperature logs. Version: {0}".format(app.config['APPVERSION']), 'alert-info')
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
        <button type="submit" class="btn btn-default">Show</button>
        </form>
        """ % (app.config['SUBFOLDER'], app.config['DATAINICIO'], app.config['DATAFIM'])

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
        <form method="post" action="/lastday">
        <select name="timeinterval">
        <option value="6" %s> last 6 hours</option>
        <option value="12" %s> last 12 hours</option>
        <option value="24" %s> last 24 hours</option>
        </select>
        <button type="submit" class="btn btn-default">Show</button>
        </form>
        """ % (s1,s2,s3)
        flash(Markup(selector), 'alert-info')
        return redirect(url_for('show_main'))

@app.route('/allsensors')
def allsensors():
    app.config['SENSORESAVER'] = []
    return redirect(url_for('show_main'))

@app.route('/sensorstoshow', methods=['GET', 'POST'])
def sensorstoshow():
    #todo colocar filtro de sensores a funcionar
    if request.method == 'POST':
        app.config['SENSORESAVER'] = request.form['sensores']
        flash(app.config['SENSORESAVER'], 'alert-info')
        return redirect(url_for('show_main'))
    else:
        selector = """
        <form method="post" action="%s/sensorstoshow">
        <select multiple="multiple" name="sensores">
        """ % app.config['SUBFOLDER']

        for sensid in dictsensores:
            if (sensid in app.config['SENSORESAVER']) or (app.config['SENSORESAVER'] == []):
                seleccionado = 'selected="selected"'
            else:
                seleccionado = ''

            selector += '<option %s value="%s">%s</option>' % (seleccionado, sensid, dictsensores[sensid])

        selector += """
        </select>
        <button type="submit" class="btn btn-default">Show</button>
        </form>
        """

        flash(Markup(selector), 'alert-info')
        return redirect(url_for('show_main'))

@app.route('/showgraph')
def showgraph():
    app.config['SHOWGRAPH'] = not app.config['SHOWGRAPH']
    return redirect(url_for('show_main'))

@app.route('/showlasthour')
def showlasthour():
    #todo colocar estaisticas da ultima hora
    app.config['SHOWLASTHOUR'] = not app.config['SHOWLASTHOUR']
    return redirect(url_for('show_main'))

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

    #flash(dictsensores, 'alert-info')
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
        chart_code += "data.addColumn('number', '{0} {1}');\n".format('Temperature', str(sensor[1]))
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
        'Temperature (C)', int(maximo) + 1, int(minimo), int(maximo) + 1 - int(minimo) + 1, '(day) Hour')

    return chart_code

if __name__ == '__main__':
    #init_db()
    app.run()
