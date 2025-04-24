import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO
import dropbox  # <-- Nuevo import

app = Flask(__name__)
app.secret_key = os.urandom(24)

dropbox_url_usuarios = "https://www.dropbox.com/scl/fi/ir9gxg87lgd5szujpz7z3/lista-de-usuarios-nacional.xlsx?rlkey=htg0izh11vu2w6oib6l9fv45h&st=641g0w53&dl=1"
dropbox_url_base = "https://www.dropbox.com/scl/fi/fcg3lxj7smpdswr2hur0i/Parte-2-nacional.xlsx?rlkey=qmg0fz7xjmt9jwjx35maon6zl&st=wtxegeyg&dl=1"

def download_excel_from_dropbox(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            file_content = response.content
            if file_content[:4] == b'PK\x03\x04':
                file_stream = BytesIO(file_content)
                data = pd.read_excel(file_stream, engine='openpyxl')
                return data
        return None
    except Exception as e:
        print(f"Error al descargar el archivo: {e}")
        return None

def download_users_from_dropbox():
    return download_excel_from_dropbox(dropbox_url_usuarios)

def download_data_from_dropbox():
    return download_excel_from_dropbox(dropbox_url_base)

users_data = download_users_from_dropbox()
data = download_data_from_dropbox()
sent_records = []

save_path = r"C:\Users\jeraldi.rosas\OneDrive - Instituto Nacional Electoral\Escritorio\ruta nacional"

def load_processed_folios():
    try:
        with open('processed_folios.txt', 'r') as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return []

def save_processed_folios(processed_folios):
    with open('processed_folios.txt', 'w') as f:
        for folio in processed_folios:
            f.write(folio + '\n')

processed_folios = load_processed_folios()

def load_saved_records():
    try:
        file_path = os.path.join(save_path, 'registros_guardados.xlsx')
        if os.path.exists(file_path):
            df = pd.read_excel(file_path, engine='openpyxl')
            return df.to_dict(orient='records')
        return []
    except Exception as e:
        print(f"Error al cargar los registros guardados: {e}")
        return []

sent_records = load_saved_records()

usuarios_pel = [
    "DUR1", "DUR2", "DUR3", "DUR4", 
    "VER1", "VER2", "VER3", "VER4", "VER5", "VER6", "VER7", "VER8", "VER9", "VER10", "VER11", "VER12", 
    "VER13", "VER14", "VER15", "VER16", "VER17", "VER18", "VER19"
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    usuario = request.form['usuario']
    contrasena = request.form['contrasena']
    user_row = users_data.loc[(users_data['Usuario'] == usuario) & (users_data['Contraseña'] == contrasena)]

    if not user_row.empty:
        session['usuario'] = usuario
        user_folios = data[data['USUARIO'] == usuario]
        session['user_folios'] = user_folios['Folio SIILNEVA'].tolist()

        if usuario.endswith('JL'):
            return redirect(url_for('registros_pva'))

        return redirect(url_for('search'))
    else:
        return render_template('index.html', error="Usuario o contraseña incorrectos.")

@app.route('/registros_pva')
def registros_pva():
    return render_template('registros_pva.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    user_folios = session.get('user_folios', [])
    available_folios = [folio for folio in user_folios if folio not in processed_folios]
    processed_user_folios = [folio for folio in processed_folios if folio in user_folios]

    if request.method == 'POST':
        folio = request.form['folio']
        if folio in available_folios:
            row = data.loc[data['Folio SIILNEVA'] == folio].iloc[0]
            result = {
                'Folio': folio,
                'Numero de Envio': row['Número de Envio'],
                'Id_Entidad': row['Id_Entidad'],
                'Entidad': row['Entidad'],
                'Id_Distrito Electoral Federal': row['Id_Distrito Electoral Federal'],
                'Cabecera D.E.F': row['Cabecera D.E.F'],
            }
            if session['usuario'] in usuarios_pel:
                return render_template('questions_pel.html', result=result, folio=folio)
            else:
                return render_template('questions.html', result=result, folio=folio)

    return render_template('search.html', folios=available_folios, processed_user_folios=processed_user_folios)

@app.route('/questions/<folio>', methods=['GET', 'POST'])
def questions(folio):
    if 'usuario' not in session:
        return redirect(url_for('index'))

    row = data.loc[data['Folio SIILNEVA'] == folio]
    if row.empty:
        return render_template('search.html', error="Folio no encontrado.")

    result = {
        'Folio': folio,
        'Número de Envio': row['Número de Envio'].iloc[0],
        'Id_Entidad': row['Id_Entidad'].iloc[0],
        'Entidad': row['Entidad'].iloc[0],
        'Id_Distrito Electoral Federal': row['Id_Distrito Electoral Federal'].iloc[0],
        'Cabecera D.E.F': row['Cabecera D.E.F'].iloc[0],
    }

    if request.method == 'POST':
        siilneva = request.form['siilneva']
        numero_visita = request.form['numero_visita']
        fecha_entrega = request.form['fecha_entrega']
        tipo_eleccion = request.form.get('tipo_eleccion') if session['usuario'] in usuarios_pel else None
        causal_siilneva = request.form['causal_siilneva'] if siilneva == 'No' else None

        if folio not in processed_folios:
            processed_folios.append(folio)

        if siilneva and numero_visita and fecha_entrega:
            record = {
                'Folio SIILNEVA': folio,
                'Id_Entidad': int(row['Id_Entidad'].iloc[0]),
                'Entidad': row['Entidad'].iloc[0],
                'Id_Distrito Electoral Federal': int(row['Id_Distrito Electoral Federal'].iloc[0]),
                'Cabecera D.E.F': int(row['Cabecera D.E.F'].iloc[0]),
                '¿Se recopiló voto?': siilneva,
                'Número de Visita': numero_visita,
                'Fecha de Entrega': fecha_entrega,
                'Causal_SIILNEVA': causal_siilneva,
            }

            if tipo_eleccion:
                record['Tipo de Elección'] = tipo_eleccion

            sent_records.append(record)
            save_to_excel()
            save_processed_folios(processed_folios)

            return render_template('save.html', folio=folio)
        else:
            return render_template('questions.html', result=result, error="Todos los campos son obligatorios.")

    return render_template('questions.html', result=result)

def save_to_excel():
    df = pd.DataFrame(sent_records)
    file_path = os.path.join(save_path, 'registros_guardados.xlsx')
    df.to_excel(file_path, index=False)

    # Subir a Dropbox
    try:
        access_token = "sl.u.AFrE8rrMf56wIkEQd0wvg91mDmZmmbenJHbzwPMSrOJW-9_th3c2u4QXkGDb1wmqeG24Z7SeJYCTpvwfJEOp0mjPCwLj0D8C7-zqNUsK0IcVgvkpu2lVFCJvJiE36rOwIL0_vy0yTmGa8T-h3s3Rvaoc0qJZoFzNlqp8CfcCYviSbogZYNVduj8ExzycsyOki3OU0fmMyXjp6ZHLse37XbQ-x1LT2dpPCJpXiHMdfPjlK5jzlh-NxzHuCCckvT4xAS0zMhSy3PnvImQBF4IuDo_rCFpX_LrZrD7X2PutbLTHAd3_JQ3-RrqUFCRwVda-BMYK91l9VRttt4vdzMgZFRDm6vMV9Z-CUspcheMTO8agvMXHRjDYK7uEnvCGVSjL6iXaZgr4198mgZq51I4Fsm9GFf1VAFUfcL1g4fdJzFIpeMaNk7sjPL32dT2nazmB9xNSmNpbIRF1B6u8aaczVkQ5Rl9UFAK7GDqAzhZEMVYl3845GLxoERAE0LlpHplfhlAESP7wdp_Jqokyloi-ICLwGGEW0m-BOfb8BllrzW3YanYXquKW62neUMhz_sZBUmu7BQd3N0GCIj5tlqiVvuiA3boDapMOo2TN8OCaeBthsycE_Pb2wcElUBJB_AwcyYfmMKDPGHnIQpQTG-j5k2hgre99tKPzQxK87Whl2hfu3HZpfLSaIkOG327wVb8gh_Hs-I52oI0TZ6iGY8UAvVWmbPhO2KZRGiF68EsjR7WjY-wgRuKZgM1YaIeEgePDr6fPbpeQZgklGlmuvKGJQr6gwhnwP24E4kobPZ-l1zZsfaPo3HISciKGn_UToTZuFhtYX9P4ZsrcXEF610Jixg64BHs6lDKKivtRGA8UQdidVe4WkfN9qo5r9RnrGDCJLS6jrLoOmV69suduV03wlyhihRzm0V4_6ohynFhp9_WabPx9DRU6MsaHRe6wGWuYZDsIfgiRz25F-Tm3sxXo6EZ1l8IkL5H1IUon2EtKurUZU-ImgZquzmnuiV2UYNQgaleRm1Nn-Mw8jBEfbYzVTXjJ1oMs_tYmHjtWwfGEENS1w1SeyNJy6RlK4zDPxU0r6WLyNC5TLImKdWHMYZGPSgnl3SxmTAklrfdzRyXjhq0yCKzLAKbeqlF4iJ5dK0uAvd_eNKAU7zUk-o9fHZWUuNeRaXTMCxY7bocDYhk2cp37-Xa3UjzbtQdnLsMrke7cSsnVOpHn4T7Eas3FPEyMzzku8DL-sEzajvxhkmSJZY47A-ZaJgG0QPvPqC9kp0qx5CMcwTFbBX07sDxTnhwdMZD6"  # <-- Reemplaza con tu token de Dropbox
        dbx = dropbox.Dropbox(access_token)
        with open(file_path, 'rb') as f:
            dbx.files_upload(f.read(), '/registros_guardados.xlsx', mode=dropbox.files.WriteMode.overwrite)
        print("Archivo subido a Dropbox exitosamente.")
    except Exception as e:
        print(f"Error al subir a Dropbox: {e}")

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    session.pop('user_folios', None)
    return redirect(url_for('index'))

@app.route('/view_records')
def view_records():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    usuario = session['usuario']
    user_records = [record for record in sent_records if record['Folio SIILNEVA'] in session.get('user_folios', [])]
    df = pd.DataFrame(user_records) if user_records else pd.DataFrame()
    has_records = len(user_records) > 0

    return render_template('view_records.html', records=df, has_records=has_records)

@app.route('/download_excel')
def download_excel():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    usuario = session['usuario']
    entidad_usuario = usuario[:3]

    entidades_permitidas = {
        "AGS": "AGUASCALIENTES", "BAJ": "BAJA CALIFORNIA", "BJS": "BAJA CALIFORNIA SUR",
        "CAM": "CAMPECHE", "CHS": "CHIAPAS", "CHJ": "CHIHUAHUA", "CDM": "CIUDAD DE MEXICO",
        "COA": "COAHUILA", "COL": "COLIMA", "DUR": "DURANGO", "GUA": "GUANAJUATO",
        "GUE": "GUERRERO", "HID": "HIDALGO", "JAL": "JALISCO", "MEX": "MEXICO",
        "MIC": "MICHOACAN", "MOR": "MORELOS", "NAY": "NAYARIT", "NUE": "NUEVO LEON",
        "OAX": "OAXACA", "PUE": "PUEBLA", "QUE": "QUERETARO", "QUI": "QUINTANA ROO",
        "SLP": "SAN LUIS POTOSI", "SIN": "SINALOA", "SON": "SONORA", "TAB": "TABASCO",
        "TLA": "TLAXCALA", "VER": "VERACRUZ", "YUC": "YUCATAN", "ZAC": "ZACATECAS"
    }

    if usuario.endswith('JL'):
        if entidad_usuario in entidades_permitidas:
            entidad = entidades_permitidas[entidad_usuario]
            user_records = [r for r in sent_records if r['Entidad'] == entidad]
        else:
            return "Entidad no reconocida para este usuario."
    else:
        user_records = [r for r in sent_records if r['Folio SIILNEVA'] in session.get('user_folios', [])]

    if not user_records:
        return "No hay registros disponibles para descarga."

    df = pd.DataFrame(user_records)
    temp_filename = f"reporte_{usuario}.xlsx"
    temp_path = os.path.join(save_path, temp_filename)
    df.to_excel(temp_path, index=False)

    return send_file(temp_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

