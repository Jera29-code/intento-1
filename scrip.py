
from flask import Flask, render_template, request, redirect, url_for, session, make_response
import pandas as pd
from io import BytesIO
import os
from datetime import datetime
import requests

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Para sesiones seguras

# URL de descarga directa del archivo con los usuarios y contraseñas
dropbox_url_usuarios = "https://www.dropbox.com/scl/fi/0yh46fj1wkvy96fyuupog/lista-de-usuarios.xlsx?rlkey=pihdtj5gxf2k5p022l8x2rtol&dl=1"
# URL de descarga directa de la base de datos
dropbox_url_base = "https://www.dropbox.com/scl/fi/zbxqemymj0wdtwib4eg8o/Archivo_SIILNEVA_Recopiladas.xlsx?rlkey=h879uzv57i3evv651owf4xuku&dl=1"

# Cargar datos desde Dropbox y verificar si es un archivo Excel
def download_excel_from_dropbox(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            file_content = response.content
            if file_content[:4] == b'PK\x03\x04':  # Verificar encabezado ZIP para archivos XLSX
                file_stream = BytesIO(file_content)
                data = pd.read_excel(file_stream, engine='openpyxl')
                print("Archivo descargado y cargado exitosamente desde Dropbox.")
                return data
            else:
                print("El archivo descargado no es un archivo de Excel válido.")
                return None
        else:
            print(f"Error al descargar el archivo: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error al descargar el archivo: {e}")
        return None

# Cargar datos de usuarios y contraseñas desde el archivo Excel
def download_users_from_dropbox():
    try:
        return download_excel_from_dropbox(dropbox_url_usuarios)
    except Exception as e:
        print(f"Error al descargar la lista de usuarios: {e}")
        return None

# Cargar datos de la base de datos desde Dropbox
def download_data_from_dropbox():
    try:
        return download_excel_from_dropbox(dropbox_url_base)
    except Exception as e:
        print(f"Error al descargar el archivo de base de datos: {e}")
        return None

# Cargar los datos
users_data = download_users_from_dropbox()
data = download_data_from_dropbox()

# Lista para almacenar los registros enviados (simulando base de datos en memoria)
sent_records = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    usuario = request.form['usuario']
    contrasena = request.form['contrasena']

    # Buscar el usuario y la contraseña en el DataFrame
    user_row = users_data.loc[(users_data['Usuario'] == usuario) & (users_data['Contraseña'] == contrasena)]

    if not user_row.empty:
        # Guardar el usuario en la sesión para verificar más tarde
        session['usuario'] = usuario
        # Filtrar los folios que pertenecen a ese usuario
        user_folios = data[data['USUARIO'] == usuario]
        session['user_folios'] = user_folios['Folio SIILNEVA'].tolist()
        return redirect(url_for('search'))
    else:
        return render_template('index.html', error="Usuario o contraseña incorrectos.")

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    # Obtener los folios disponibles para el usuario
    user_folios = session.get('user_folios', [])

    if request.method == 'POST':
        folio = request.form['folio']
        
        if folio in user_folios:
            row = data.loc[data['Folio SIILNEVA'] == folio].iloc[0]
            result = {
                'Folio': folio,
                'Numero de Envio': row['Número de Envio'],
                'Id_Entidad': row['Id_Entidad'],
                'Entidad': row['Entidad'],
                'Id_Distrito Electoral Federal': row['Id_Distrito Electoral Federal'],
                'Cabecera D.E.F': row['Cabecera D.E.F'],
            }
            return render_template('questions.html', result=result, folio=folio)
        else:
            return render_template('search.html', error="Folio no encontrado o no permitido para tu usuario.")

    return render_template('search.html', folios=user_folios)

@app.route('/questions/<folio>', methods=['GET', 'POST'])
def questions(folio):
    if 'usuario' not in session:
        return redirect(url_for('index'))

    # Buscar el folio en la base de datos
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

    # Si el método es POST, procesamos los datos del formulario
    if request.method == 'POST':
        número_de_visita = request.form['numero_visita']
        siilneva = request.form['siilneva']  # Esta es la respuesta a SIILNEVA
        causal = request.form['causal_siilneva'] if siilneva == 'No' else None
        interes_voto = request.form['interes_voto']  # Respuesta sobre el interés en votar
        causal_interes = request.form['causal_interes'] if interes_voto == 'No' else None
        fecha_entrega = request.form['fecha_entrega']

        # Si "¿Se_recopiló_SIILNEVA?" es "No", vaciar el campo de "¿Manifestó_estar_interesado_en_votar?"
        if siilneva == 'No':
            interes_voto = ''

        # Obtener los datos adicionales del folio
        additional_data = {
            'Id_Entidad': row['Id_Entidad'].iloc[0],
            'Entidad': row['Entidad'].iloc[0],
            'Id_Distrito Electoral Federal': row['Id_Distrito Electoral Federal'].iloc[0],
            'Cabecera D.E.F': row['Cabecera D.E.F'].iloc[0]
        }

        # Almacenar los registros en la lista "sent_records"
        sent_records.append({
            'Folio SIILNEVA': folio,
            'Número_de_visita': número_de_visita,
            '¿Se_recopiló_SIILNEVA?': siilneva,
            '¿Manifestó_estar_interesado_en_votar?': interes_voto,
            'Causal': causal if causal else causal_interes,
            'Fecha de Entrega': fecha_entrega,
            'Id_Entidad': additional_data['Id_Entidad'],
            'Entidad': additional_data['Entidad'],
            'Id_Distrito Electoral Federal': additional_data['Id_Distrito Electoral Federal'],
            'Cabecera D.E.F': additional_data['Cabecera D.E.F'],
        })

        # Generar archivo Excel con los datos adicionales
        # Obtener la fecha actual para el nombre del archivo
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        nombre_archivo = f"SEGUIMIENTO_VA_{fecha_actual}.xlsx"

        # Especificar la ruta de guardado
        export_path = os.path.join(r"C:\Users\jeraldi.rosas\OneDrive - Instituto Nacional Electoral\Escritorio\seguimiento VA IN", nombre_archivo)
        
        # Convertir los registros a un DataFrame con las columnas en el orden solicitado
        export_data = pd.DataFrame(sent_records, columns=[  
            'Folio SIILNEVA', 'Id_Entidad', 'Entidad', 'Id_Distrito Electoral Federal', 'Cabecera D.E.F',
            '¿Se_recopiló_SIILNEVA?', 'Número_de_visita','¿Manifestó_estar_interesado_en_votar?', 'Causal', 'Fecha de Entrega'
        ])
        
        # Guardar el archivo Excel
        export_data.to_excel(export_path, index=False)
        
        return render_template('save.html', folio=folio)

    return render_template('questions.html', result=result, folio=folio)

@app.route('/view_records')
def view_records():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    # Obtener los registros enviados por el usuario
    user_folios = session.get('user_folios', [])
    
    # Filtrar los registros enviados por el folio del usuario
    user_sent_records = [record for record in sent_records if record['Folio SIILNEVA'] in user_folios]
    
    return render_template('view_records.html', records=user_sent_records)

@app.route('/descargar_csv')
def descargar_csv():
    if 'usuario' not in session:
        return redirect(url_for('index'))

    user_folios = session.get('user_folios', [])
    user_sent_records = [record for record in sent_records if record['Folio SIILNEVA'] in user_folios]
    
    # Convertir los registros a un DataFrame
    df = pd.DataFrame(user_sent_records)
    
    # Convertir el DataFrame a CSV
    csv = df.to_csv(index=False)
    
    # Crear un archivo CSV para descargar
    response = make_response(csv)
    response.headers["Content-Disposition"] = "attachment; filename=registros.csv"
    response.headers["Content-Type"] = "text/csv"
    
    return response

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('usuario', None)  # Elimina la sesión del usuario
    session.pop('user_folios', None)  # Elimina los folios del usuario
    return redirect(url_for('index'))  # Redirige al inicio (pantalla de login)

if __name__ == '__main__':
    app.run(debug=True)
