import os
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import psycopg2 as pg
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Config — reuse historian.config (hostname, dbName, user, password)
# ---------------------------------------------------------------------------
_cfg = os.path.join(os.path.dirname(__file__), '..', 'historian.config')
with open(_cfg) as f:
    _lines = f.readlines()

DB = {
    'host':     _lines[1].split(' = ')[1].strip(),
    'dbname':   _lines[3].split(' = ')[1].strip(),
    'user':     _lines[4].split(' = ')[1].strip(),
    'password': _lines[5].split(' = ')[1].strip(),
}

MACHINES = ['VF-2_1', 'VF-2_2']
REFRESH_MS = 5_000

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def _conn():
    return pg.connect(**DB)


def get_latest(machine: str) -> dict:
    try:
        conn = _conn()
        df = pd.read_sql_query(
            f'SELECT * FROM "AML"."{machine}" ORDER BY "timestamp" DESC LIMIT 1',
            conn,
        )
        conn.close()
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception as exc:
        print(f"[DB] {machine}: {exc}")
    return {}


# ---------------------------------------------------------------------------
# Gauge factory
# ---------------------------------------------------------------------------
def gauge(title: str, value, max_val: float, unit: str = '') -> go.Figure:
    try:
        val = float(value) if value not in (None, '', 'nan', float('nan')) else 0.0
    except (TypeError, ValueError):
        val = 0.0
    val = max(0.0, min(val, max_val))

    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=val,
        title={'text': f'<b>{title}</b>', 'font': {'size': 12}},
        number={'suffix': unit, 'font': {'size': 15}},
        gauge={
            'axis': {'range': [0, max_val]},
            'bar': {'color': '#2980b9'},
            'steps': [
                {'range': [0, max_val * 0.6], 'color': '#d5f5e3'},
                {'range': [max_val * 0.6, max_val * 0.85], 'color': '#fdebd0'},
                {'range': [max_val * 0.85, max_val], 'color': '#fadbd8'},
            ],
            'threshold': {
                'line': {'color': 'red', 'width': 2},
                'thickness': 0.75,
                'value': max_val * 0.85,
            },
        },
    ))
    fig.update_layout(margin=dict(l=8, r=8, t=44, b=8), height=165,
                      paper_bgcolor='white', plot_bgcolor='white')
    return fig


# ---------------------------------------------------------------------------
# Status colour
# ---------------------------------------------------------------------------
def status_color(row: dict) -> str:
    val = str(row.get('Three-in-one (PROGRAM, Oxxxxx, STATUS, PARTS, xxxxx)', '')).upper()
    if 'ALARM' in val:
        return '#c0392b'
    if any(k in val for k in ('IDLE', 'SLEEP', 'DDEATH', 'STALE')):
        return '#e67e22'
    if any(k in val for k in ('RUN', 'PROGRAM', 'DBIRTH')):
        return '#27ae60'
    return '#7f8c8d'


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _s(val, fallback='—') -> str:
    if val is None or (isinstance(val, float) and val != val):
        return fallback
    return str(val)


def kv(label: str, value, bold: bool = False) -> html.Tr:
    return html.Tr([
        html.Td(label, style={'color': '#7f8c8d', 'paddingRight': '12px',
                               'fontSize': '13px', 'paddingBottom': '3px'}),
        html.Td(_s(value), style={'fontSize': '13px', 'fontWeight': 'bold' if bold else 'normal'}),
    ])


# ---------------------------------------------------------------------------
# Machine card
# ---------------------------------------------------------------------------
def machine_card(machine: str, row: dict) -> html.Div:
    sc = status_color(row)
    three_in_one = _s(row.get('Three-in-one (PROGRAM, Oxxxxx, STATUS, PARTS, xxxxx)'))

    # Status banner
    banner = html.Div(
        three_in_one,
        style={
            'backgroundColor': sc, 'color': 'white', 'padding': '10px 14px',
            'borderRadius': '6px', 'fontWeight': 'bold', 'fontSize': '13px',
            'marginBottom': '14px', 'wordBreak': 'break-all', 'letterSpacing': '0.5px',
        },
    )

    # Gauges
    gauge_specs = [
        ('Spindle\nRPM',    'Spindle RPM (read only)',                           15000, ' RPM'),
        ('Spindle\nLoad',   'Spindle load with Haas vector drive (read only)',   100,   '%'),
        ('X\nLoad',         'Max axis load for X',                               100,   '%'),
        ('Y\nLoad',         'Max axis load for Y',                               100,   '%'),
        ('Z\nLoad',         'Max axis load for Z',                               100,   '%'),
    ]
    gauges_row = html.Div(
        [
            dcc.Graph(
                figure=gauge(t, row.get(c), m, u),
                style={'flex': '1', 'minWidth': '100px'},
                config={'displayModeBar': False},
            )
            for t, c, m, u in gauge_specs
        ],
        style={'display': 'flex', 'gap': '4px', 'marginBottom': '14px'},
    )

    # Info table
    info_table = html.Table(
        html.Tbody([
            kv('Date',          row.get('Year, month, day')),
            kv('Time',          row.get('Hour, minute, second')),
            kv('Mode',          row.get('Mode (LIST PROG, MDI, etc.)')),
            kv('Tool in use',   row.get('Tool Number in use'), bold=True),
            kv('Tool changes',  row.get('Tool Changes (total)')),
            kv('Parts #1',      row.get('M30 Parts Counter #1 (resettable at control)'), bold=True),
            kv('Parts #2',      row.get('M30 Parts Counter #2 (resettable at control)'), bold=True),
            kv('Coolant level', row.get('Coolant level')),
            kv('Last cycle',    row.get('Last Cycle Time')),
            kv('Prev cycle',    row.get('Previous Cycle Time')),
            kv('Power-on',      row.get('Power-on Time (total)')),
        ]),
        style={'width': '100%', 'borderCollapse': 'collapse', 'marginBottom': '14px'},
    )

    # Coordinate table
    def coord_td(col):
        return html.Td(_s(row.get(col)), style={'textAlign': 'right', 'fontSize': '13px',
                                                 'fontFamily': 'monospace'})

    coord_table = html.Div([
        html.H4('Coordinates', style={'margin': '0 0 6px', 'fontSize': '13px',
                                       'color': '#2c3e50', 'textTransform': 'uppercase',
                                       'letterSpacing': '1px'}),
        html.Table([
            html.Thead(html.Tr([
                html.Th('', style={'width': '70px'}),
                html.Th('X', style={'textAlign': 'right', 'fontSize': '13px'}),
                html.Th('Y', style={'textAlign': 'right', 'fontSize': '13px'}),
                html.Th('Z', style={'textAlign': 'right', 'fontSize': '13px'}),
            ])),
            html.Tbody([
                html.Tr([
                    html.Td('Machine', style={'color': '#7f8c8d', 'fontSize': '13px'}),
                    coord_td('Present machine coordinate position X'),
                    coord_td('Present machine coordinate position Y'),
                    coord_td('Present machine coordinate position Z'),
                ]),
                html.Tr([
                    html.Td('Work', style={'color': '#7f8c8d', 'fontSize': '13px'}),
                    coord_td('Present work coordinate position X'),
                    coord_td('Present work coordinate position Y'),
                    coord_td('Present work coordinate position Z'),
                ]),
            ]),
        ], style={'width': '100%', 'borderCollapse': 'collapse', 'marginBottom': '14px'}),
    ])

    # Tool vibrations bar chart
    vib_vals = []
    for i in range(1, 21):
        try:
            vib_vals.append(float(row.get(f'Max recorded vibrations of tool {i}') or 0))
        except (TypeError, ValueError):
            vib_vals.append(0.0)

    max_v = max(vib_vals) if any(v > 0 for v in vib_vals) else 1
    bar_colors = ['#e74c3c' if v == max_v and v > 0 else '#3498db' for v in vib_vals]

    vib_fig = go.Figure(go.Bar(
        x=[f'T{i}' for i in range(1, 21)],
        y=vib_vals,
        marker_color=bar_colors,
        hovertemplate='Tool %{x}: %{y:.2f}<extra></extra>',
    ))
    vib_fig.update_layout(
        title={'text': '<b>Tool Vibrations</b>', 'font': {'size': 13}, 'x': 0},
        margin=dict(l=30, r=10, t=40, b=30),
        height=180,
        paper_bgcolor='white',
        plot_bgcolor='#f8f9fa',
        xaxis={'gridcolor': 'white'},
        yaxis={'gridcolor': 'white', 'zeroline': False},
    )

    vib_chart = dcc.Graph(figure=vib_fig, config={'displayModeBar': False})

    return html.Div([
        html.H2(machine, style={
            'margin': '0 0 12px', 'fontSize': '20px', 'color': '#2c3e50',
            'borderBottom': '3px solid #3498db', 'paddingBottom': '8px',
        }),
        banner,
        gauges_row,
        info_table,
        coord_table,
        vib_chart,
    ], style={
        'flex': '1', 'backgroundColor': 'white', 'borderRadius': '10px',
        'padding': '18px', 'boxShadow': '0 2px 10px rgba(0,0,0,0.08)',
        'minWidth': '0',
    })


def offline_card(machine: str) -> html.Div:
    return html.Div([
        html.H2(machine, style={'fontSize': '20px', 'color': '#2c3e50',
                                 'borderBottom': '3px solid #e74c3c', 'paddingBottom': '8px'}),
        html.Div('NO DATA', style={
            'backgroundColor': '#c0392b', 'color': 'white',
            'padding': '10px 14px', 'borderRadius': '6px',
            'fontWeight': 'bold', 'fontSize': '13px',
        }),
        html.P('Cannot reach database or table is empty.',
               style={'color': '#7f8c8d', 'fontSize': '13px', 'marginTop': '10px'}),
    ], style={
        'flex': '1', 'backgroundColor': 'white', 'borderRadius': '10px',
        'padding': '18px', 'boxShadow': '0 2px 10px rgba(0,0,0,0.08)',
    })


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------
app = dash.Dash(__name__, title='Haas CNC Dashboard')

app.layout = html.Div([
    # Header
    html.Div([
        html.H1('Haas CNC Dashboard',
                style={'margin': 0, 'fontSize': '24px', 'color': 'white'}),
        html.Span(id='last-update', style={'color': '#bdc3c7', 'fontSize': '13px'}),
    ], style={
        'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        'backgroundColor': '#2c3e50', 'padding': '14px 24px',
    }),

    dcc.Interval(id='tick', interval=REFRESH_MS, n_intervals=0),

    # Machine cards
    html.Div(id='cards', style={
        'display': 'flex', 'gap': '20px', 'padding': '20px',
        'alignItems': 'flex-start',
    }),
], style={'backgroundColor': '#ecf0f1', 'minHeight': '100vh',
          'fontFamily': 'Arial, sans-serif'})


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------
@app.callback(
    Output('cards', 'children'),
    Output('last-update', 'children'),
    Input('tick', 'n_intervals'),
)
def refresh(_n):
    import datetime
    cards = []
    for m in MACHINES:
        row = get_latest(m)
        cards.append(machine_card(m, row) if row else offline_card(m))
    ts = datetime.datetime.now().strftime('Last update: %H:%M:%S')
    return cards, ts


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)
