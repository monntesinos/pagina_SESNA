import os
import io
import json
import uuid
import re
import traceback
import difflib
import datetime
import zipfile
import tempfile
import shutil
import unicodedata
import numpy as np
import pandas as pd
import pickle

from flask import Flask, jsonify, request, render_template, make_response
from dotenv import load_dotenv
from supabase import create_client, Client

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# ============================================================
# 1. INICIALIZACIÓN Y CONFIGURACIÓN
# ============================================================
load_dotenv()  # Carga las variables de tu archivo .env

app = Flask(__name__)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("⚠️ Faltan las credenciales de Supabase en el archivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Cliente de Supabase inicializado.")

# Configuración de Modelos ML
MODEL_PROCESO_PATH = os.path.join('models', 'modelo_proceso.pkl')
MODEL_EJE_PATH = os.path.join('models', 'modelo_eje.pkl')
MODEL_TEMA_PATH = os.path.join('models', 'modelo_tema.pkl')
UMBRAL_CONFIANZA = 0.92

_models_loaded = False
_model_proceso = None
_model_eje = None
_model_tema = None

# ============================================================
# 2. CONSTANTES
# ============================================================
COLUMN_DISPLAY_NAMES = [
    "ID", "Versión", "Proceso", "Eje", "Tema", "Nombre",
    "Institución", "Cobertura", "Periodicidad", "Liga Web", "Tipo de dato",
    "Fuente", "Año", "Valor"
]

DYNAMIC_OPTIONS_COLUMNS = [
    "version", "proceso", "eje", "tema",
    "institucion", "cobertura", "periodicidad", "tipo_de_dato"
]

EXPECTED_COLUMNS = [
    'id', 'version', 'proceso', 'eje', 'tema', 'nombre',
    'institucion', 'cobertura', 'periodicidad', 'liga_web', 'tipo_de_dato',
    'fuente', 'año', 'valor'
]

KEYWORDS = {
    'proceso': {
        'A. Prevención': ['existencia', 'mecanismos', 'cobertura', 'plan', 'programa', 'profesionalización', 'capacitación', 'servicio civil', 'reglas', 'lineamientos', 'diseño', 'atributos', 'calidad', 'indicadores', 'objetivos', 'metas', 'participación ciudadana', 'contraloría social', 'educación', 'campañas', 'comunicaciones', 'código de ética', 'declaración patrimonial', 'evaluación de control y confianza', 'personal', 'recursos humanos'],
        'B. Detección': ['percibe', 'percepción', 'frecuencia', 'prevalencia', 'incidencia', 'experimentaron', 'usuarios', 'unidades económicas', 'denuncias recibidas', 'carpetas de investigación', 'averiguaciones previas', 'quejas recibidas', 'actos de corrupción reportados', 'conocimiento por terceros', 'inconformidades', 'observaciones', 'investigación iniciada', 'víctimas', 'imputados', 'inculpados', 'causas penales ingresadas'],
        'C. Sanción': ['sanciones', 'condenatorias', 'absolutorias', 'multas', 'inhabilitación', 'destitución', 'amonestación', 'resarcitoria', 'pliego de observaciones', 'procedimientos de responsabilidad', 'sentencias', 'fincamiento', 'sanciones económicas', 'revocación', 'castigo', 'ejecución de sentencia', 'cumplimiento de órdenes'],
        'D. Fiscalización y control de recursos': ['auditoría', 'fiscalización', 'control interno', 'observaciones', 'presupuesto', 'recursos', 'contratos', 'monto', 'donativos', 'compras', 'obra pública', 'licitaciones', 'convocatorias', 'adjudicaciones', 'proveedores', 'contratistas', 'cuenta pública', 'armonización contable', 'estado de situación financiera', 'ingresos', 'egresos', 'fideicomisos']
    },
    'eje': {
        '1. Combatir la corrupción y la impunidad': ['quejas', 'denuncias', 'faltas administrativas', 'justicia', 'delitos', 'cohecho', 'peculado', 'enriquecimiento', 'abuso de autoridad', 'ejercicio indebido', 'procuración', 'impartición', 'ministerio público', 'causas penales', 'sentencias', 'sanciones', 'responsabilidad administrativa', 'investigación de servidores', 'tribunales', 'jueces', 'magistrados', 'fiscalía', 'averiguación previa', 'carpeta de investigación'],
        '2. Combatir la arbitrariedad y el abuso de poder': ['profesionalización', 'servicio civil', 'carrera', 'capacitación', 'evaluación de desempeño', 'declaración patrimonial', 'planes anticorrupción', 'programas sociales', 'procesos institucionales', 'indicadores', 'reglas de operación', 'riesgos', 'auditoría', 'fiscalización', 'control interno', 'obra pública', 'contrataciones', 'adquisiciones', 'arrendamientos', 'proveedores', 'contratistas', 'testigos sociales', 'planeación', 'programación', 'presupuestación', 'seguimiento', 'evaluación', 'marco jurídico', 'transparencia', 'datos abiertos', 'rendición de cuentas'],
        '3. Promover la mejora de la gestión y los puntos de contacto gobierno-sociedad': ['trámites', 'servicios públicos', 'puntos de contacto', 'ciudadanía', 'iniciativa privada', 'licitaciones', 'convocatorias', 'permisos', 'pagos', 'predial', 'tenencia', 'atención ciudadana', 'solicitudes de información', 'oficina de transparencia', 'módulos de orientación', 'infracciones', 'licencias de conducir', 'registro civil', 'afiliación', 'consulta médica', 'inscripción escolar', 'compras del gobierno', 'contratación pública', 'MIPYMES', 'competencia económica', 'prácticas monopólicas'],
        '4. Involucrar a la sociedad y el sector privado': ['participación ciudadana', 'contraloría social', 'vigilancia', 'colaboración', 'cocreación', 'educación', 'campañas anticorrupción', 'comunicación', 'integridad empresarial', 'código de ética', 'compliance', 'denuncias corporativas', 'testigos sociales', 'observadores', 'organizaciones civiles', 'ONG', 'sindicatos', 'medios de comunicación', 'redes sociales', 'parlamento abierto', 'gobierno abierto', 'consulta ciudadana', 'presupuesto participativo']
    },
    'tema': {
        '1.1. Prevención, detección, denuncia, investigación, substanciación y sanción de faltas administrativas': ['quejas', 'denuncias', 'oficina de contraloría', 'procedimientos de responsabilidad', 'declaración patrimonial', 'conflictos de interés', 'sistema informático para quejas', 'buzón de quejas', 'atención ciudadana', 'faltas administrativas', 'sanciones administrativas', 'amonestación', 'suspensión', 'destitución', 'inhabilitación', 'responsabilidad resarcitoria'],
        '1.2. Procuración e impartición de justicia en materia de delitos por hechos de corrupción': ['delitos', 'cohecho', 'peculado', 'enriquecimiento ilícito', 'tráfico de influencias', 'abuso de autoridad', 'ejercicio indebido', 'carpetas de investigación', 'averiguaciones previas', 'causas penales', 'sentencias condenatorias', 'sentencias absolutorias', 'jueces', 'magistrados', 'ministerio público', 'fiscalía', 'imputados', 'víctimas'],
        '2.1. Profesionalización e integridad en el servicio público': ['servicio civil', 'carrera', 'capacitación', 'evaluación de control y confianza', 'desempeño', 'competencias', 'personal', 'licenciatura', 'recursos humanos', 'profesionalización', 'integridad', 'código de ética', 'declaración patrimonial', 'evaluación de desempeño'],
        '2.2. Procesos institucionales': ['plan anticorrupción', 'programas sociales', 'riesgos', 'indicadores', 'metas', 'cobertura', 'desempeño', 'presupuesto', 'reglas de operación', 'lineamientos', 'diseño', 'calidad', 'cumplimiento de metas', 'cuadrante', 'targeting', 'instrumentos de medición', 'panel de control', 'seguimiento', 'evaluación de diseño', 'consistencia y resultados'],
        '2.3. Auditoría y fiscalización': ['auditoría', 'fiscalización', 'control interno', 'observaciones', 'revisión', 'órgano de control', 'visitaduría', 'entidad de fiscalización', 'armonización contable', 'ejercicio y control', 'seguimiento', 'evaluación', 'indicadores de resultados', 'marco jurídico', 'planeación', 'programación', 'presupuestación'],
        '3.1. Puntos de contacto gobierno-ciudadanía: trámites, servicios y programas públicos': ['trámites', 'servicios', 'solicitudes de información', 'atención ciudadana', 'pagos', 'predial', 'tenencia', 'permisos', 'construcción', 'licencias', 'usuarios', 'confianza en información', 'módulos de orientación', 'oficina de transparencia', 'solicitudes de acceso a la información', 'datos abiertos', 'quejas de servicios', 'contacto con autoridades'],
        '3.2. Puntos de contacto gobierno-iniciativa privada': ['contrataciones', 'licitaciones', 'obra pública', 'proveedores', 'contratistas', 'MIPYMES', 'testigos sociales', 'convocatorias', 'adquisiciones', 'arrendamientos', 'servicios relacionados', 'prácticas monopólicas', 'competencia', 'registro de contratistas', 'sistema electrónico de contrataciones', 'invitación restringida', 'adjudicación directa'],
        '4.1. Participación ciudadana: vigilancia, colaboración y cocreación': ['contraloría social', 'órganos de participación', 'consulta ciudadana', 'vigilancia', 'presupuesto participativo', 'parlamento abierto', 'gobierno abierto', 'mecanismos de participación', 'comités de contraloría', 'consejos ciudadanos', 'rendición de cuentas', 'espacios de participación'],
        '4.2. Corresponsabilidad e integridad empresarial': ['empresa', 'integridad', 'código de ética', 'compliance', 'proveedores', 'denuncias corporativas', 'programa de integridad', 'anticorrupción', 'políticas de sobornos', 'conflicto de intereses', 'transparencia corporativa'],
        '4.3. Educación y comunicación para el control de la corrupción': ['educación', 'campañas', 'conocimiento cívico', 'estudiantes', 'comunicación', 'redes sociales', 'medios de comunicación', 'divulgación', 'sensibilización', 'normalización de la corrupción', 'cultura de la legalidad', 'formación']
    }
}

# ============================================================
# 3. FUNCIONES AUXILIARES (Texto y Limpieza)
# ============================================================
def remover_acentos(s):
    if not s: return ""
    return "".join(c for c in unicodedata.normalize('NFKD', str(s)) if not unicodedata.combining(c))

def safe_clean(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    s = str(v).replace('\n', ' ').replace('\r', ' ').strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def normalizar_texto(texto):
    if not texto: return ""
    return remover_acentos(str(texto).lower().strip())

def _clean_data_for_json(data):
    if isinstance(data, dict):
        return {k: _clean_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_clean_data_for_json(elem) for elem in data]
    elif pd.isna(data):
        return None
    return data

def normalizar_numero_texto(valor, columna=None):
    if valor is None: return ""
    try:
        if isinstance(valor, (int, float)) and not pd.isna(valor):
            if columna == 'año' or columna == 'version': return str(int(valor))
            elif columna == 'valor': return f"{float(valor):.1f}"
            else: return str(valor)
        if isinstance(valor, str):
            try:
                num = float(valor.replace(',', ''))
                if columna == 'año' or columna == 'version': return str(int(num))
                elif columna == 'valor': return f"{num:.1f}"
                else: return str(valor)
            except ValueError:
                return str(valor)
        return valor
    except (ValueError, TypeError):
        return valor

# ============================================================
# 4. FUNCIONES DE BASE DE DATOS Y CATÁLOGOS
# ============================================================
def _get_all_existing_ids():
    try:
        res = supabase.from_('variables').select('id').execute()
        return {str(item['id']) for item in res.data} if res.data else set()
    except Exception as e:
        print(f"Error al obtener IDs existentes: {e}")
        return set()

def _get_all_variables_data():
    try:
        res = supabase.from_('variables').select('*').order('id', desc=True).execute()
        if not res.data: return []
        data = []
        for item in res.data:
            row = {}
            for k, v in item.items():
                if k in ['version', 'año', 'valor']:
                    v = normalizar_numero_texto(v, k)
                row[k] = safe_clean(v)
            data.append(row)
        return data
    except Exception as e:
        print(f"Error al obtener datos: {e}")
        return []

def _get_catalog_options(column_key):
    try:
        res = supabase.from_(column_key).select('name').execute()
        return sorted({r['name'] for r in res.data if r.get('name')}) if res.data else []
    except Exception as e:
        print(f"Error al obtener opciones para '{column_key}': {e}")
        return []

def _find_best_value_match(input_value, available_options, threshold=0.8):
    if not input_value or not available_options: return None, 0.0
    input_norm = remover_acentos(str(input_value).lower())
    best_match_val, highest_score = None, 0.0
    for option_original in available_options:
        option_norm = remover_acentos(str(option_original).lower())
        score = difflib.SequenceMatcher(None, input_norm, option_norm).ratio()
        if score > highest_score:
            highest_score, best_match_val = score, option_original
    return (best_match_val, highest_score) if highest_score >= threshold else (None, highest_score)

def normalizar_valor_con_catalogo(valor, tabla, threshold=0.5):
    if not valor or not isinstance(valor, str): return valor
    valor_limpio = safe_clean(valor)
    if not valor_limpio: return valor

    sinonimos = {
        'institucion': {
            'inegi': 'Instituto Nacional de Estadística y Geografía',
            'sep': 'Secretaría de Educación Pública',
        }
    }
    if tabla in sinonimos:
        valor_lower = valor_limpio.lower()
        for clave, canonico in sinonimos[tabla].items():
            if clave in valor_lower: return canonico

    opciones = _get_catalog_options(tabla)
    valor_norm = remover_acentos(valor_limpio.lower().strip())
    for opt in opciones:
        if remover_acentos(opt.lower().strip()) == valor_norm:
            return opt

    match, score = _find_best_value_match(valor_limpio, opciones, threshold)
    if match: return match

    try:
        res = supabase.from_(tabla).insert({"name": valor_limpio}).execute()
        return valor_limpio if res.data else valor
    except Exception:
        return valor

def normalizar_categoria(valor, tipo, debug=False):
    if not valor: return valor
    valor_limpio = safe_clean(valor)
    if not valor_limpio: return valor

    if tipo == 'proceso':
        opciones, palabras_por_opcion = list(KEYWORDS['proceso'].keys()), KEYWORDS['proceso']
    elif tipo == 'eje':
        opciones, palabras_por_opcion = list(KEYWORDS['eje'].keys()), KEYWORDS['eje']
    elif tipo == 'tema':
        opciones, palabras_por_opcion = list(KEYWORDS['tema'].keys()), KEYWORDS['tema']
    else:
        return valor

    valor_norm = remover_acentos(valor_limpio.lower().strip())
    for opt in opciones:
        if remover_acentos(opt.lower().strip()) == valor_norm: return opt

    def texto_contiene_palabra_clave(texto, lista_palabras):
        texto_norm = remover_acentos(texto.lower())
        for palabra in lista_palabras:
            if remover_acentos(palabra.lower()) in texto_norm: return True
        return False

    for categoria, palabras in palabras_por_opcion.items():
        if texto_contiene_palabra_clave(valor_limpio, palabras): return categoria

    if tipo == 'eje' and valor_limpio.startswith('Eje '):
        num_match = re.search(r'Eje\s*(\d+)', valor_limpio, re.IGNORECASE)
        if num_match:
            num = num_match.group(1)
            for opt in opciones:
                if opt.startswith(f'Eje {num}.'): return opt

    if tipo == 'tema' and re.match(r'^\d+\.', valor_limpio):
        num_match = re.match(r'^(\d+)\.', valor_limpio)
        if num_match:
            num = num_match.group(1)
            for opt in opciones:
                if opt.startswith(f'{num}.'): return opt

    for opt in opciones:
        ratio = difflib.SequenceMatcher(None, remover_acentos(valor_limpio.lower()), remover_acentos(opt.lower())).ratio()
        if ratio > 0.5: return opt

    return valor

def _get_non_id_hash(row_dict):
    relevant_keys = sorted([k for k in EXPECTED_COLUMNS if k != 'id'])
    values = []
    for key in relevant_keys:
        val = row_dict.get(key, '')
        if key in ['version', 'año', 'valor']:
            val = normalizar_numero_texto(val, key)
        val = safe_clean(val)
        values.append(val)
    return tuple(values)

def generar_siguiente_id(existing_ids, used_ids_in_batch):
    try:
        nums = []
        for id_str in existing_ids.union(used_ids_in_batch):
            match = re.search(r'A-(\d+)', id_str)
            if match: nums.append(int(match.group(1)))
        proximo_num = max(nums) + 1 if nums else 1
        new_id = f"A-{proximo_num:05d}"
        while new_id in existing_ids or new_id in used_ids_in_batch:
            proximo_num += 1
            new_id = f"A-{proximo_num:05d}"
        return new_id
    except Exception:
        new_id_uuid = f"A-{uuid.uuid4().hex[:5].upper()}"
        return new_id_uuid

# ============================================================
# 5. FUNCIONES DE MACHINE LEARNING Y PREDICCIÓN
# ============================================================
def clean_text(text):
    if not text: return ""
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text.lower().strip()

def load_models():
    global _models_loaded, _model_proceso, _model_eje, _model_tema
    try:
        if os.path.exists(MODEL_PROCESO_PATH) and os.path.exists(MODEL_EJE_PATH) and os.path.exists(MODEL_TEMA_PATH):
            with open(MODEL_PROCESO_PATH, 'rb') as f: _model_proceso = pickle.load(f)
            with open(MODEL_EJE_PATH, 'rb') as f: _model_eje = pickle.load(f)
            with open(MODEL_TEMA_PATH, 'rb') as f: _model_tema = pickle.load(f)
            _models_loaded = True
            print("✅ Modelos ML cargados correctamente.")
        else:
            _models_loaded = False
            print("⚠️ Modelos ML no encontrados en 'models/'. Usando fallback por palabras clave.")
    except Exception as e:
        _models_loaded = False
        print(f"❌ Error al cargar modelos: {e}. Usando fallback.")

def train_models():
    try:
        if not os.path.exists('models'):
            os.makedirs('models')

        for path in [MODEL_PROCESO_PATH, MODEL_EJE_PATH, MODEL_TEMA_PATH]:
            if os.path.exists(path):
                shutil.copy2(path, path + '.bak')

        res = supabase.from_('variables').select('nombre, proceso, eje, tema').execute()
        if not res.data: return {"status": "error", "message": "No hay datos etiquetados para entrenar."}

        df = pd.DataFrame(res.data)
        df = df.dropna(subset=['nombre', 'proceso', 'eje', 'tema'])
        df = df[df['nombre'].str.strip() != '']

        if len(df) < 10: return {"status": "error", "message": f"Solo hay {len(df)} filas. Se necesitan al menos 10."}

        def is_consistent(row):
            eje_num = re.search(r'Eje\s*(\d+)', str(row['eje']))
            tema_num = re.search(r'^(\d+)\.', str(row['tema']))
            if eje_num and tema_num:
                return eje_num.group(1) == tema_num.group(1)
            return False

        df_consistent = df[df.apply(is_consistent, axis=1)]
        if len(df_consistent) == 0:
            return {"status": "error", "message": "No hay filas con coherencia entre Eje y Tema."}

        df = df_consistent
        df['nombre_limpio'] = df['nombre'].apply(clean_text)
        X = df['nombre_limpio']

        modelos = {
            'proceso': (df['proceso'], MODEL_PROCESO_PATH),
            'eje': (df['eje'], MODEL_EJE_PATH),
            'tema': (df['tema'], MODEL_TEMA_PATH)
        }
        resultados = {}

        for nombre_col, (y, path) in modelos.items():
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            pipeline = Pipeline([
                ('tfidf', TfidfVectorizer(max_features=5000, ngram_range=(1, 2), stop_words='english')),
                ('clf', MultinomialNB())
            ])
            pipeline.fit(X_train, y_train)
            y_pred = pipeline.predict(X_test)
            report = classification_report(y_test, y_pred, output_dict=True)
            with open(path, 'wb') as f:
                pickle.dump(pipeline, f)
            resultados[nombre_col] = {'accuracy': report['accuracy'], 'samples': len(y_test)}

        load_models()
        return {"status": "success", "message": f"Modelos reentrenados ({len(df)} filas).", "report": resultados}
    except Exception as e:
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}

def predecir_por_palabras_clave(texto):
    if not texto: return None, None, None
    mejor_proceso, mejor_puntaje_proceso = list(KEYWORDS['proceso'].keys())[0], 0
    for cat, pal in KEYWORDS['proceso'].items():
        score = sum(1 for p in pal if normalizar_texto(p) in normalizar_texto(texto))
        if score > mejor_puntaje_proceso: mejor_puntaje_proceso, mejor_proceso = score, cat

    mejor_eje, mejor_puntaje_eje = list(KEYWORDS['eje'].keys())[0], 0
    for cat, pal in KEYWORDS['eje'].items():
        score = sum(1 for p in pal if normalizar_texto(p) in normalizar_texto(texto))
        if score > mejor_puntaje_eje: mejor_puntaje_eje, mejor_eje = score, cat

    mejor_tema, mejor_puntaje_tema = list(KEYWORDS['tema'].keys())[0], 0
    for cat, pal in KEYWORDS['tema'].items():
        score = sum(1 for p in pal if normalizar_texto(p) in normalizar_texto(texto))
        if score > mejor_puntaje_tema: mejor_puntaje_tema, mejor_tema = score, cat

    return mejor_proceso, mejor_eje, mejor_tema

def predict_categories(texto):
    if not texto: return None, None, None
    if _models_loaded:
        texto_limpio = clean_text(texto)
        if texto_limpio:
            prob_proc = _model_proceso.predict_proba([texto_limpio])[0]
            proc_pred = _model_proceso.classes_[prob_proc.argmax()] if max(prob_proc) >= UMBRAL_CONFIANZA else None

            prob_eje = _model_eje.predict_proba([texto_limpio])[0]
            eje_pred = _model_eje.classes_[prob_eje.argmax()] if max(prob_eje) >= UMBRAL_CONFIANZA else None

            prob_tema = _model_tema.predict_proba([texto_limpio])[0]
            tema_pred = _model_tema.classes_[prob_tema.argmax()] if max(prob_tema) >= UMBRAL_CONFIANZA else None

            if eje_pred and tema_pred:
                eje_num, tema_num = re.search(r'Eje\s*(\d+)', eje_pred), re.search(r'^(\d+)\.', tema_pred)
                if eje_num and tema_num and eje_num.group(1) != tema_num.group(1):
                    tema_pred = None
            if proc_pred and eje_pred and tema_pred: return proc_pred, eje_pred, tema_pred

    return predecir_por_palabras_clave(texto)

load_models()

def rellenar_categorias(row_data, debug_log=None):
    if debug_log is None: debug_log = []
    for col in ['version', 'año', 'valor']:
        if col in row_data and row_data[col] is not None and row_data[col] != '':
            row_data[col] = normalizar_numero_texto(row_data[col], col)

    nombre = row_data.get('nombre')
    if not nombre: return row_data

    for key in ['proceso', 'eje', 'tema']:
        if key in row_data and row_data[key] is not None:
            row_data[key] = str(row_data[key]).strip()

    if not row_data.get('proceso') or not row_data.get('eje') or not row_data.get('tema'):
        proc, eje, tema = predict_categories(nombre)
        if proc and not row_data.get('proceso'): row_data['proceso'] = proc
        if eje and not row_data.get('eje'): row_data['eje'] = eje
        if tema and not row_data.get('tema'): row_data['tema'] = tema

    if not row_data.get('proceso'): row_data['proceso'] = list(KEYWORDS['proceso'].keys())[0]
    if not row_data.get('eje'): row_data['eje'] = list(KEYWORDS['eje'].keys())[0]
    if not row_data.get('tema'): row_data['tema'] = list(KEYWORDS['tema'].keys())[0]

    for col in ['proceso', 'eje', 'tema']:
        if row_data.get(col):
            row_data[col] = normalizar_categoria(row_data[col], col, debug=True)
    return row_data

# ============================================================
# 6. LÓGICA DE PROCESAMIENTO DE CSV / CARPETAS
# ============================================================
def _normalize_col_for_matching(col_name):
    return remover_acentos(str(col_name).lower().replace(" ", "_")).replace("-", "_")

def _find_best_column_match(uploaded_col_normalized, available_expected_cols_normalized, threshold=0.8):
    best_match, highest_score = None, threshold
    for expected_col_norm in available_expected_cols_normalized:
        score = difflib.SequenceMatcher(None, uploaded_col_normalized, expected_col_norm).ratio()
        if score > highest_score:
            highest_score, best_match = score, expected_col_norm
    return best_match

def _process_csv_data(df_input, existing_supabase_data_full, debug=False):
    messages = []
    df = df_input.copy()
    all_known_normalized_keys = set(EXPECTED_COLUMNS)
    for display_name in COLUMN_DISPLAY_NAMES:
        all_known_normalized_keys.add(_normalize_col_for_matching(display_name))

    column_rename_map = {}
    processed_target_cols = set()
    for original_col in df.columns:
        normalized_original_col = _normalize_col_for_matching(original_col)
        target_col_name = None
        if normalized_original_col in EXPECTED_COLUMNS:
            target_col_name = normalized_original_col
        else:
            fuzzy_match = _find_best_column_match(normalized_original_col, all_known_normalized_keys)
            if fuzzy_match and fuzzy_match in EXPECTED_COLUMNS:
                target_col_name = fuzzy_match
        
        if target_col_name:
            if target_col_name not in processed_target_cols:
                column_rename_map[original_col] = target_col_name
                processed_target_cols.add(target_col_name)
        else:
            column_rename_map[original_col] = original_col

    df.rename(columns=column_rename_map, inplace=True)
    extra_cols = [col for col in df.columns if col not in EXPECTED_COLUMNS and col != 'id']
    if extra_cols: df.drop(columns=extra_cols, inplace=True)

    for col in EXPECTED_COLUMNS:
        if col not in df.columns: df[col] = pd.NA

    df = df[EXPECTED_COLUMNS]

    for col in ['version', 'año', 'valor']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: normalizar_numero_texto(x, col) if not pd.isna(x) else x)

    normalized_existing_data = []
    for db_row in existing_supabase_data_full:
        norm_row = db_row.copy()
        for col in ['version', 'año', 'valor']:
            if col in norm_row and norm_row[col]:
                norm_row[col] = normalizar_numero_texto(norm_row[col], col)
        normalized_existing_data.append(norm_row)

    existing_hashes = {}
    for db_row in normalized_existing_data:
        h = _get_non_id_hash(db_row)
        if h not in existing_hashes:
            existing_hashes[h] = db_row

    all_rows = []
    duplicate_count = 0
    for idx, row_series in df.iterrows():
        csv_row = row_series.to_dict()
        csv_hash = _get_non_id_hash(csv_row)
        row_status = {
            'original_csv_index': idx, 'data': csv_row, '_is_duplicate': False,
            '_supabase_matching_id': None, '_hash': csv_hash
        }
        if csv_hash in existing_hashes:
            matching = existing_hashes[csv_hash]
            row_status['_is_duplicate'] = True
            row_status['_supabase_matching_id'] = matching.get('id')
            duplicate_count += 1
        all_rows.append(row_status)

    if duplicate_count > 0: messages.append(f"Se encontraron {duplicate_count} filas duplicadas.")
    else: messages.append("No se encontraron duplicados.")

    existing_ids_from_db = _get_all_existing_ids()
    temp_ids = set(existing_ids_from_db)
    for row in all_rows:
        if not row['_is_duplicate']:
            new_id = generar_siguiente_id(temp_ids, set())
            temp_ids.add(new_id)
            row['data']['id'] = new_id

    return all_rows, messages

# ============================================================
# 7. RUTAS DE LA APLICACIÓN FLASK
# ============================================================
@app.route('/')
def indice():
    try:
        js_col_defs = []
        for name in COLUMN_DISPLAY_NAMES:
            key = remover_acentos(name.lower().replace(" ", "_"))
            if name == "ID": key = "id"
            elif name == "Versión": key = "version"
            elif name == "Tipo de dato": key = "tipo_de_dato"
            elif name == "Liga Web": key = "liga_web"
            elif name == "Año": key = "año"
            elif name == "Valor": key = "valor"

            info = {"displayName": name, "keyName": key, "type": "input", "readonly": (key == 'id')}
            if key in DYNAMIC_OPTIONS_COLUMNS:
                info["type"] = "select"
                try:
                    opts_res = supabase.from_(key).select('name').execute()
                    info["options"] = sorted({r['name'] for r in opts_res.data if r.get('name')}) if opts_res.data else []
                except:
                    info["options"] = []
            js_col_defs.append(info)

        headers_html = "".join(f"<th><div class='th-content'>{name}</div></th>" for name in COLUMN_DISPLAY_NAMES)
        headers_html = "<th style='width:40px;'></th>" + headers_html

        script_block = f"<script>window.COLUMN_DEFINITIONS = {json.dumps(js_col_defs).replace('</script>', '<\\/script>')};</script>"
        
        # OJO AQUÍ: Renderiza usando templates/index.html y pasa las variables
        return render_template('index.html', headers_html=headers_html, script_block=script_block)
    except Exception as e:
        traceback.print_exc()
        return f"Error al renderizar el índice: {str(e)}", 500

@app.route('/api/variables', methods=['GET', 'POST'])
def api_vars():
    if request.method == 'GET':
        try:
            return jsonify(_get_all_variables_data())
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    elif request.method == 'POST':
        try:
            new_id = generar_siguiente_id(_get_all_existing_ids(), set())
            data = request.json or {}
            new_row = {"id": new_id, "version": data.get('version', '-')}
            for col in EXPECTED_COLUMNS:
                if col not in ['id', 'version']: new_row[col] = data.get(col, '')
            
            if new_row['nombre']:
                proc, eje, tema = predict_categories(new_row['nombre'])
                if proc and not new_row['proceso']: new_row['proceso'] = proc
                if eje and not new_row['eje']: new_row['eje'] = eje
                if tema and not new_row['tema']: new_row['tema'] = tema
            
            res = supabase.from_('variables').insert(new_row).execute()
            return jsonify(res.data[0]) if res.data else jsonify({"error": "Error al crear"}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/variables/<id_val>', methods=['PUT', 'DELETE'])
def api_item(id_val):
    if request.method == 'PUT':
        try:
            cleaned_data = {k: str(v) if not pd.isna(v) else None for k, v in request.json.items() if k in EXPECTED_COLUMNS}
            res = supabase.from_('variables').update(cleaned_data).eq('id', id_val).execute()
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    elif request.method == 'DELETE':
        try:
            supabase.from_('variables').delete().eq('id', id_val).execute()
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/variables/<id_val>/duplicate', methods=['POST'])
def duplicate_var(id_val):
    try:
        res = supabase.from_('variables').select('*').eq('id', id_val).execute()
        if not res.data: return jsonify({"error": "No encontrada"}), 404
        dup_row = res.data[0].copy()
        dup_row['id'] = generar_siguiente_id(_get_all_existing_ids(), set())
        ins_res = supabase.from_('variables').insert(dup_row).execute()
        return jsonify(ins_res.data[0]), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        # 1. CASO DE CONFIRMACIÓN: El frontend solo envía las acciones a guardar (sin archivo)
        actions_str = request.form.get('actions_for_rows')
        if actions_str:
            actions = json.loads(actions_str)
            data_to_insert, data_to_update = [], []
            used_ids = set(_get_all_existing_ids())

            for a in actions:
                row_data = rellenar_categorias(a['data'])
                if a['action'] == 'insert':
                    row_data['id'] = generar_siguiente_id(used_ids, set())
                    used_ids.add(row_data['id'])
                    data_to_insert.append({k: str(v) if not pd.isna(v) else None for k, v in row_data.items()})
                elif a['action'] == 'overwrite':
                    row_data['id'] = a.get('_supabase_matching_id')
                    data_to_update.append({k: str(v) if not pd.isna(v) else None for k, v in row_data.items() if k in EXPECTED_COLUMNS})

            inserted, updated = 0, 0
            if data_to_insert:
                ins_res = supabase.from_('variables').insert(data_to_insert).execute()
                inserted = len(ins_res.data) if ins_res.data else 0
            if data_to_update:
                for row in data_to_update:
                    supabase.from_('variables').update(row).eq('id', row.pop('id')).execute()
                    updated += 1

            file_name = request.form.get('zip_filename', 'carga_web')
            supabase.from_('cargas').insert({
                'fecha': datetime.datetime.now().isoformat(), 'archivo': file_name,
                'filas_agregadas': inserted, 'estado': 'completado' if inserted > 0 else 'error'
            }).execute()

            return jsonify({"status": "ok", "message": f"Insertadas: {inserted}. Actualizadas: {updated}."}), 200

        # 2. CASO DE VISTA PREVIA: El frontend envía un archivo (CSV o ZIP) para analizar
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "No se recibió ningún archivo ni acciones de carga."}), 400

        df = None
        filename = file.filename

        if filename.endswith('.csv'):
            # Si es CSV normal, lo leemos directamente
            df = pd.read_csv(io.BytesIO(file.read()), encoding='utf-8-sig')
        
        elif filename.endswith('.zip'):
            # Si es ZIP, lo abrimos en la memoria sin extraerlo al disco duro
            with zipfile.ZipFile(file, 'r') as z:
                # Buscamos todos los archivos que terminen en .csv adentro del ZIP
                csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                
                if not csv_files:
                    return jsonify({"error": "No se encontraron archivos CSV dentro de la carpeta ZIP"}), 400
                
                # Leemos el primer archivo CSV que encontró dentro del ZIP
                with z.open(csv_files[0]) as f:
                    df = pd.read_csv(f, encoding='utf-8-sig')
        else:
            return jsonify({"error": "El archivo debe tener formato .csv o .zip"}), 400
        
        # Procesamiento y limpieza de datos (reutilizando tu lógica)
        extracted_year = re.search(r'(19|20)\d{2}', filename)
        if extracted_year and ('año' not in df.columns or df['año'].isna().all()):
            df['año'] = extracted_year.group(0)

        processed_rows, messages = _process_csv_data(df, _get_all_variables_data(), debug=True)

        return jsonify({
            "status": "preview", 
            "messages": messages, 
            "preview_data": _clean_data_for_json(processed_rows),
            "zip_filename": filename
        }), 200

    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/api/upload', methods=['POST'])
def upload_csv():
    try:
        file = request.files.get('file')
        if not file or not file.filename.endswith('.csv'): return jsonify({"error": "Debe ser CSV"}), 400
        df = pd.read_csv(io.BytesIO(file.read()), encoding='utf-8-sig')
        
        extracted_year = re.search(r'(19|20)\d{2}', file.filename)
        if extracted_year and ('año' not in df.columns or df['año'].isna().all()):
            df['año'] = extracted_year.group(0)

        processed_rows, messages = _process_csv_data(df, _get_all_variables_data(), debug=True)

        if request.args.get('preview') == 'true':
            return jsonify({"status": "preview", "messages": messages, "preview_data": _clean_data_for_json(processed_rows)}), 200

        actions = json.loads(request.form.get('actions_for_rows', '[]'))
        data_to_insert, data_to_update, used_ids = [], [], set(_get_all_existing_ids())

        for a in actions:
            row_data = rellenar_categorias(a['data'])
            if a['action'] == 'insert':
                row_data['id'] = generar_siguiente_id(used_ids, set())
                used_ids.add(row_data['id'])
                data_to_insert.append({k: str(v) if not pd.isna(v) else None for k, v in row_data.items()})
            elif a['action'] == 'overwrite':
                row_data['id'] = a.get('_supabase_matching_id')
                data_to_update.append({k: str(v) if not pd.isna(v) else None for k, v in row_data.items() if k in EXPECTED_COLUMNS})

        inserted, updated = 0, 0
        if data_to_insert:
            ins_res = supabase.from_('variables').insert(data_to_insert).execute()
            inserted = len(ins_res.data) if ins_res.data else 0
        if data_to_update:
            for row in data_to_update:
                supabase.from_('variables').update(row).eq('id', row.pop('id')).execute()
                updated += 1

        supabase.from_('cargas').insert({
            'fecha': datetime.datetime.now().isoformat(), 'archivo': file.filename,
            'filas_agregadas': inserted, 'estado': 'completado' if inserted > 0 else 'error'
        }).execute()

        return jsonify({"status": "ok", "message": f"Insertadas: {inserted}. Actualizadas: {updated}."}), 200
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/api/retrain-models', methods=['POST'])
def retrain_models_endpoint():
    try:
        result = train_models()
        if result.get('status') == 'success':
            return jsonify({"status": "ok", "message": result['message'], "report": result.get('report')}), 200
        return jsonify({"error": result.get('message', 'Error al entrenar')}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload-history', methods=['GET'])
def upload_history():
    try:
        res = supabase.from_('cargas').select('*').order('fecha', desc=True).limit(50).execute()
        return jsonify(res.data if res.data else [])
    except:
        return jsonify([])

# ============================================================
# INICIO DE LA APLICACIÓN
# ============================================================
if __name__ == '__main__':
    # Flask levantará el servidor en el puerto 5000 por defecto
    print("🚀 Levantando servidor Flask...")
    app.run(debug=True, port=5000)