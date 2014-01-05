#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import sys
import cgi
import time
import cgitb
import os
import i18n

# global variables
APPVERSION = "0.50"
dbname = '/var/www/templog.db'

form = cgi.FieldStorage()

# Set the language to use on the user interface
lang = "en"
if 'language' in form:
    lang = form.getfirst("language")
if lang == "pt":
    _ = i18n.pt_language.gettext
elif lang == "en":
    _ = i18n.uk_language.gettext

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

# print the HTTP header
def printHTTPheader():
    print "Content-type: text/html\n\n"
    print '<meta http-equiv="Content-Type" content="text/html;charset=UTF-8">'


# print the HTML head section
# arguments are the page title and the table for the chart
def printHTMLHead(title, records, minimo, maximo, sens):
    s1=""
    s2=""
    if lang == "pt":
        s1 = 'selected="selected"'
    if lang == "en":
        s2 = 'selected="selected"'

    print "<head>"
    print """
    <script language="javascript" type="text/javascript">
    /* Collect all forms in document to one and post it */
    function submitAllDocumentForms()
    {
        var arrDocForms = document.getElementsByTagName('form');
        var formCollector = document.createElement("form");
        with(formCollector)
        {
            method = "post";
            action = "%s";
            name = "formCollector";
            id = "formCollector";
        }
        for(var ix=0;ix<arrDocForms.length;ix++)
        {
            appendFormVals2Form(arrDocForms[ix], formCollector);
        }
        document.body.appendChild(formCollector);
        formCollector.submit();

    }

    function appendFormVals2Form(frmCollectFrom, frmCollector)
    {
        var currentEl;
        var frm = frmCollectFrom.elements;
        var nElems = frm.length;
        for(var ix = nElems - 1; ix >= 0 ; ix--)
        {
            currentEl = frm[ix];
            // currentEl.name = frmCollectFrom.name + ':' + currentEl.name;
            frmCollector.appendChild(currentEl);
        }
        return frmCollector;
    }

    </script>
    <form id="changelanguage">
    <div style="float:right;">
      <select name="language" onchange="submitAllDocumentForms()">
        <option %s value="pt">Português</option>
        <option %s value="en">English</option>
      </select>
    </div>
    </form>
    """ % (os.path.basename(sys.argv[0]), s1,s2)
    print "<title>"
    print title
    print "</title>"

    if records:
        print_graph_script(records, minimo, maximo, sens)

    print "</head>"


# get data from the database
# if an interval is passed,
# return a list of records from the database
# interval can be on th form 6, 12, 24 or yyyy-mm-dd|yyy-mm-dd
# function is the select part of the query to perform
# output defines whether all records that match the criteria should be returned, or only one as a float, or only one
def get_data(interval, function, output):
    conn = sqlite3.connect(dbname)
    curs = conn.cursor()
    query = "SELECT %s FROM temps" % function

    # Create query limited to the sensors to show
    if defaults['sensoresaver'] != []:
        st = ''
        for sens in defaults['sensoresaver']:
            st += "'{0}',".format(sens)
        st = st[:-1]

    if interval != None:
        if interval == "6" or interval == "12" or interval == "24":
            query += " WHERE timestamp>datetime('now','-%s hours')" % interval
        else:
            datas = interval.split('|')
            query += " WHERE (timestamp>='%s') AND (timestamp<='%s 23:59:59')" % (datas[0], datas[1])
        if defaults['sensoresaver'] != []:
            query += " AND id in ({0})".format(st)
    elif defaults['sensoresaver'] != []:
        query += " WHERE id in ({0})".format(st)

    curs.execute(query)
    if output == "oneasfloat":
        rows = curs.fetchone()
        conn.close()
        if not rows[0]:
            return None
        else:
            return float(rows[0])
    elif output == "one[0]":
        rows = curs.fetchone()
        conn.close()
        if not rows:
            return None
        else:
            return rows
    else:
        rows = curs.fetchall()
        conn.close()
        if not rows:
            return None
        else:
            return rows


# Returns list of available sensors on the selected interval, as a table with ID,name
# also updates the dictionary dictsensores with the same information
def get_sensors(interval):
    global dictsensores

    conn = sqlite3.connect(dbname)
    curs = conn.cursor()
    query = "SELECT DISTINCT sensors.id, sensors.name FROM sensors,temps"

    if interval == None:
        query += " WHERE sensors.id=temps.id"
    elif interval == "6" or interval == "12" or interval == "24":
        query += " WHERE (sensors.id=temps.id) AND (temps.timestamp>datetime('now','-%s hours'))" % interval
    else:
        datas = interval.split('|')
        query += " WHERE (sensors.id=temps.id) AND (timestamp>='%s') AND (timestamp<='%s 23:59:59')" % (
            datas[0], datas[1])

    curs.execute(query)
    rows = curs.fetchall()

    conn.close()

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
        chart_code += "data.addColumn('number', '{0} {1}');\n".format(_('Temperatura'), str(sensor[1]))
        chart_code += "data.addColumn({type:'string', role:'annotation'});\n"
        chart_code += "data.addColumn({type:'string', role:'annotationText'});\n"

    umsominimo = True
    umsomaximo = True

    for row in records[:]:
        rowstr = "data.addRow([new Date('{0}'), ".format(str(row[0]).replace(' ', 'T'))

        for sensor in sens[:]:
            if (str(row[2]) == str(sensor[0])):
                rowstr += "{0},".format(str(round(row[1], 1)))

                if row[1] == minimo and umsominimo:
                    rowstr += "'MIN','{0} ºC -> {1}',".format(str(round(row[1], 1)), row[0])
                    umsominimo = False
                elif row[1] == maximo and umsomaximo:
                    rowstr += "'MAX','{0} ºC -> {1}',".format(str(round(row[1], 1)), row[0])
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
        _('Temperatura (C)'), int(maximo) + 1, int(minimo), int(maximo) + 1 - int(minimo) + 1, _('(dia) Hora'))

    print chart_code


# print the div that contains the graph
def show_graph():
    #print "<h2>Gráfico de Temperatura</h2>"
    print '<div id="chart_div" style="width: 900px; height: 500px;"></div>'


# connect to the db and show some stats
# argument option is the number of hours
def show_stats(option):
    #rowmax = get_data(option, "timestamp,max(temp),ID", "one")
    #rowstrmax = "{0}&nbsp&nbsp&nbsp{1:.1f} ºC&nbsp&nbsp&nbsp{2}".format(str(rowmax[0]), float(rowmax[1]),dictsensores[rowmax[2]])

    #rowmin = get_data(option, "timestamp,min(temp),ID", "one")
    #rowstrmin = "{0}&nbsp&nbsp&nbsp{1:.1f} ºC&nbsp&nbsp&nbsp{2}".format(str(rowmin[0]), float(rowmin[1]),dictsensores[rowmin[2]])

    #rowavg = get_data(option, "avg(temp)", "oneasfloat")

    #print "<hr>"

    #print '<p style="text-align: justify;" width:450px;">'
    #print _("<strong>Temperatura minima</strong>")
    #print '%s<br>' % rowstrmin
    #print _("<strong>Temperatura maxima</strong>")
    #print '%s<br>' % rowstrmax
    #print _("<strong>Temperatura media</strong>")
    #print "%.1f" % rowavg + " ºC<br>"

    #print "</p>"
    print "<hr>"

    print "<h2>" + _("Na ultima hora (todos os sensores)") + "</h2>"
    print "<table>"
    print _(
        "<tr><td><strong>Data/Hora</strong></td><td><strong>Temperatura&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp</strong></td><td><strong>Local</strong></td></tr>")

    conn=sqlite3.connect(dbname)
    curs=conn.cursor()
    rows = curs.execute("SELECT * FROM temps WHERE timestamp>datetime('now','-1 hour') ORDER BY timestamp DESC")

    for row in rows:
        rowstr = "<tr><td>{0}&emsp;&emsp;</td><td>{1:.1f} ºC</td><td>{2}</td></tr>".format(str(row[0]), float(row[1]),
                                                                                           dictsensores[row[2]])
        print rowstr
    conn.close()
    print "</table><hr>"


def print_time_selector(option):
    print """
    <script>
    function showSelector() {document.getElementById('selector').style.visibility='visible';}
    function hideSelector() {document.getElementById('selector').style.visibility='hidden';}
    </script>
    <div id="selector">
    <form name="escolhedatas">
      <script language="javascript" type="text/javascript">
      function handleClick(cb)
      {
        switch (cb.name)
            {
              case "pordatas":
                  document.forms['escolhedatas'].elements['ultimodia'].checked = false;
                  break;
              case "ultimodia":
                  document.forms['escolhedatas'].elements['pordatas'].checked = false;
                  break;
              case "timeinterval":
                  document.forms['escolhedatas'].elements['ultimodia'].checked = true;
                  document.forms['escolhedatas'].elements['pordatas'].checked = false;
                  break;
            }
      }
      </script>
    """

    print "<fieldset><legend><b>" + _("Seleccionar por datas") + "</b></legend>"
    print '<input value="Ultimo Dia"'

    if defaults['ultimodia']:
        print 'checked="checked"'

    s1 = ""
    s2 = ""
    s3 = ""
    if defaults['periodo'] == "24":
        s3 = 'selected="selected"'
    if defaults['periodo'] == "12":
        s2 = 'selected="selected"'
    if defaults['periodo'] == "6":
        s1 = 'selected="selected"'

    print """
        name="ultimodia"
        onclick='handleClick(this);'
        type="checkbox">
    """
    print _("Mostrar registos das")
    print"""
      <select name="timeinterval" onclick='handleClick(this);'>
        <option value="6" %s>
    """ % s1
    print _("ultimas 6 horas")
    print """
    </option>
        <option value="12" %s>
    """ % s2
    print _("ultimas 12 horas")
    print """
    </option>
        <option value="24" %s>
    """ % s3
    print _("ultimas 24 horas")
    print """
    </option>
      </select>
      <br>

      <input name="pordatas"
    """

    if defaults['pordatas']:
        print 'checked="checked"'
    print """
        onclick='handleClick(this);'
        type="checkbox">
    """
    print _("Por Datas")
    print """
      &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;&nbsp;
      &nbsp;&nbsp;
    """
    print _("Desde:")
    print """
    <input value=%s name="datainicio" type="date" 'handleClick(this);'>
    """ % defaults['datainicio']
    print _(" ate")
    print """
     <input value=%s name="datafim" type="date" 'handleClick(this);'><br>
    """ % defaults['datafim']

    print _('<strong>Seleccionar sensores</strong>')
    print '<br><select multiple="multiple" name="sensores">'
    for sensid in dictsensores:
        if (sensid in defaults['sensoresaver']) or (defaults['sensoresaver'] == []):
            seleccionado = 'selected="selected"'
        else:
            seleccionado = ''
        print '<option %s value="%s">%s</option>' % (seleccionado, sensid, dictsensores[sensid])
    print "</select>"

    print """
      </fieldset>
      <input value=
    """
    print _('"Mostrar"')
    print """
    type="button" onClick="submitAllDocumentForms()">
    </form>
    </div>
    <!--<script>document.getElementById('selector').style.visibility='hidden';</script>-->
    """


#return the option passed to the script
def get_option():
    global form

    defaults['pordatas'] = False
    defaults['ultimodia'] = True
    defaults['datainicio'] = time.strftime("%Y-%m-%d")
    defaults['datafim'] = time.strftime("%Y-%m-%d")

    if 'sensores' in form:
        defaults['sensoresaver'] = form.getlist("sensores")

    if 'ultimodia' in form:
        defaults['ultimodia'] = True

        if "timeinterval" in form:
            option = form["timeinterval"].value
            defaults['periodo'] = option
            return (option)
        else:
            defaults['periodo'] = '24'
            return None

    if 'pordatas' in form:
        defaults['pordatas'] = True
        defaults['ultimodia'] = False

        inicio = form.getfirst("datainicio", time.strftime("%Y-%m-%d"))
        fim = form.getfirst("datafim", time.strftime("%Y-%m-%d"))

        if inicio > fim:
            fim = inicio

        defaults['datainicio'] = inicio
        defaults['datafim'] = fim

        return inicio + "|" + fim
    else:
        return None


# main function
# This is where the program starts
def main():
    # ToDo Criar forma de editar BD de sensores
    # ToDo Criar função termostato com mais que um piso

    cgitb.enable()

    # get options that may have been passed to this script
    option = get_option()

    if option is None:
        option = str(24)

    # get data from the database
    records = get_data(option, "*", "all")
    minimo = get_data(option, "min(temp)", "oneasfloat")
    if not minimo:
        minimo = 0
    maximo = get_data(option, "max(temp)", "oneasfloat")
    if not maximo:
        maximo = 0
    sensores = get_sensors(option)

    # print the HTTP header
    printHTTPheader()
    # start printing the page
    print '<html lang="%s">' % lang
    # print the head section including the table
    # used by the javascript for the chart
    printHTMLHead(_("Temperatura ambiente"), records, minimo, maximo, sensores)

    # print the page body
    print "<body>"
    print "<h1>"+ _("Temperatura ambiente em Casa vs ") + "%s</h1>" % APPVERSION

    print_time_selector(option)
    print "<hr>"

    if records:
        show_graph()
        show_stats(option)
    else:
        print "<strong>" + _("Nao ha dados nas datas seleccionadas!") + "</strong>"

    print "</body>"
    print "</html>"

    sys.stdout.flush()

if __name__ == "__main__":
    main()
