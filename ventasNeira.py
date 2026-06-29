# ==========================================
# ventasNeira.py - Sistema Integrado Completo
# ==========================================

import streamlit as st
import psycopg2
import pandas as pd# ==========================================
# ventasNeira.py - Sistema Integrado Completo
# ==========================================

import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import time
import io

# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="Neira Store - Inventario", layout="wide", page_icon="📦")
DB_URL = st.secrets["DB_URL"]

# --- CONTROL ESTRICTO DE VENTANAS DUPLICADAS ---
if 'sesion_activa' not in st.session_state:
    st.session_state['sesion_activa'] = True
elif not st.session_state.get('sesion_activa', False):
    st.error("⚠️ Ya hay una ventana o sesión abierta. Cierre las ventanas repetidas para evitar conflictos.")
    st.stop()

# --- FUNCIONES DE BASE DE DATOS ---
def conectar_db():
    return psycopg2.connect(DB_URL)

def inicializar_tablas():
    conn = conectar_db()
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute('''CREATE TABLE IF NOT EXISTS productos (
        id SERIAL PRIMARY KEY, codigo TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL, 
        categoria TEXT, precio_compra NUMERIC DEFAULT 0.0, precio_venta NUMERIC DEFAULT 0.0, 
        stock_actual INTEGER DEFAULT 0, stock_minimo INTEGER DEFAULT 5,
        proveedor TEXT, ubicacion TEXT, fecha_registro DATE DEFAULT CURRENT_DATE
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS ventas (
        id SERIAL PRIMARY KEY, producto_id INTEGER REFERENCES productos(id), 
        cantidad INTEGER NOT NULL, precio_unitario NUMERIC, total_venta NUMERIC, 
        fecha DATE DEFAULT CURRENT_DATE, metodo_pago TEXT DEFAULT 'Efectivo',
        cliente TEXT, vendedor TEXT, estado TEXT DEFAULT 'Completada',
        factura TEXT, observaciones TEXT, tipo_venta TEXT DEFAULT 'Contado',
        fecha_vencimiento DATE
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS compras (
        id SERIAL PRIMARY KEY, producto_id INTEGER REFERENCES productos(id), 
        cantidad INTEGER NOT NULL, costo_unitario NUMERIC, total_compra NUMERIC, 
        fecha DATE DEFAULT CURRENT_DATE, proveedor TEXT, factura_compra TEXT,
        estado TEXT DEFAULT 'Recibida', observaciones TEXT
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, nombre TEXT, usuario TEXT UNIQUE, 
        clave TEXT, rol TEXT DEFAULT 'vendedor'
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS configuracion (
        id SERIAL PRIMARY KEY, nombre_negocio TEXT DEFAULT 'Neira Store',
        direccion TEXT, telefono TEXT, email TEXT,
        iva NUMERIC DEFAULT 0.0, moneda TEXT DEFAULT '$'
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS categorias (
        id SERIAL PRIMARY KEY, nombre TEXT UNIQUE NOT NULL
    )''')
    
    # Datos iniciales por defecto
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Administrador', 'admin', 'admin2026', 'admin') ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Vendedor', 'vendedor', 'vende2026', 'vendedor') ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO configuracion (id, nombre_negocio, moneda) VALUES (1, 'Neira Store', '$') ON CONFLICT (id) DO NOTHING")
    
    categorias_base = ["Electrónica", "Ropa", "Alimentos", "Hogar", "Juguetes", "Herramientas", "Libros", "Deportes"]
    for cat in categorias_base:
        cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (cat,))
        
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN cliente TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN tipo_venta TEXT DEFAULT 'Contado'")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN fecha_vencimiento DATE")
    except Exception:
        pass
        
    conn.close()

# --- FUNCIONES DE EXPORTACIÓN A EXCEL ---
def exportar_excel(df, nombre_hoja='Reporte'):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=nombre_hoja)
    return output.getvalue()

# --- VISTAS DE LA APLICACIÓN (MÓDULOS) ---

def mostrar_dashboard(conn):
    st.subheader("📊 Dashboard General")
    total_productos = pd.read_sql("SELECT COUNT(*) FROM productos", conn).iloc[0,0]
    ventas_total = pd.read_sql("SELECT SUM(total_venta) FROM ventas", conn).iloc[0,0] or 0
    ventas_hoy = pd.read_sql("SELECT SUM(total_venta) FROM ventas WHERE fecha = CURRENT_DATE", conn).iloc[0,0] or 0
    stock_bajo = pd.read_sql("SELECT COUNT(*) FROM productos WHERE stock_actual <= stock_minimo", conn).iloc[0,0] or 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Total Productos", total_productos)
    c2.metric("💰 Ventas Totales", f"$ {ventas_total:,.0f}")
    c3.metric("📈 Ventas Hoy", f"$ {ventas_hoy:,.0f}")
    c4.metric("⚠️ Stock Bajo", stock_bajo, delta="Revisar" if stock_bajo > 0 else "OK", delta_color="inverse")
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Ventas por Producto (Top 5)")
        top_productos = pd.read_sql("SELECT p.nombre, SUM(v.cantidad) as total_vendido FROM ventas v JOIN productos p ON v.producto_id = p.id GROUP BY p.nombre ORDER BY total_vendido DESC LIMIT 5", conn)
        if not top_productos.empty: 
            st.bar_chart(data=top_productos.set_index('nombre'))
        else: 
            st.info("No hay datos de ventas aún.")
        
    with col2:
        st.subheader("📈 Ventas por Categoría")
        ventas_categoria = pd.read_sql("SELECT p.categoria, SUM(v.total_venta) as total FROM ventas v JOIN productos p ON v.producto_id = p.id GROUP BY p.categoria ORDER BY total DESC", conn)
        if not ventas_categoria.empty: 
            st.dataframe(ventas_categoria, use_container_width=True)
        else: 
            st.info("No hay datos de ventas aún.")

def mostrar_productos(conn):
    tabs = st.tabs(["➕ Nuevo Producto", "🔍 Ver Inventario", "⬆️ Importar Masivamente"])
    categorias_lista = pd.read_sql("SELECT nombre FROM categorias ORDER BY nombre", conn)['nombre'].tolist()
    
    with tabs[0]:
        with st.form("form_nuevo_producto"):
            st.subheader("Registrar Nuevo Producto")
            c1, c2 = st.columns(2)
            with c1:
                codigo = st.text_input("Código *")
                nombre = st.text_input("Nombre *")
                categoria = st.selectbox("Categoría", categorias_lista + ["Nueva..."])
                cat_nueva = st.text_input("Nombre de nueva categoría") if categoria == "Nueva..." else None
            with c2:
                p_compra = st.number_input("Precio Compra ($)", min_value=0.0)
                p_venta = st.number_input("Precio Venta ($)", min_value=0.0)
                s_inicial = st.number_input("Stock Inicial", min_value=0)
                s_minimo = st.number_input("Stock Mínimo", value=5)
            
            if st.form_submit_button("💾 Guardar Producto"):
                if not codigo or not nombre: 
                    st.error("El código y el nombre son obligatorios")
                else:
                    cur = conn.cursor()
                    cat_final = cat_nueva if categoria == "Nueva..." and cat_nueva else categoria
                    try:
                        cur.execute("INSERT INTO productos (codigo, nombre, categoria, precio_compra, precio_venta, stock_actual, stock_minimo) VALUES (%s, %s, %s, %s, %s, %s, %s)", (codigo.upper(), nombre, cat_final, p_compra, p_venta, s_inicial, s_minimo))
                        if categoria == "Nueva..." and cat_nueva:
                            cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (cat_nueva,))
                        conn.commit()
                        st.success("✅ Producto registrado exitosamente")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error: El código '{codigo}' ya podría estar registrado.")
                        
    with tabs[1]:
        st.subheader("📋 Inventario Actual")
        df = pd.read_sql("SELECT codigo, nombre, categoria, precio_compra, precio_venta, stock_actual, stock_minimo FROM productos ORDER BY nombre", conn)
        st.dataframe(df, use_container_width=True)
        if not df.empty:
            st.download_button(
                label="📥 Exportar Inventario a Excel",
                data=exportar_excel(df, "Inventario"),
                file_name=f"Inventario_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    with tabs[2]:
        st.subheader("⬆️ Importar Productos desde Excel")
        st.info("💡 Tu archivo debe contener exactamente las siguientes columnas en la primera fila (en minúsculas): \n `codigo`, `nombre`, `categoria`, `precio_compra`, `precio_venta`, `stock_actual`, `stock_minimo`")
        
        archivo_subido = st.file_uploader("Selecciona tu archivo de inventario", type=['xlsx', 'xls', 'csv'])
        
        if archivo_subido is not None:
            try:
                if archivo_subido.name.endswith('.csv'):
                    df_import = pd.read_csv(archivo_subido)
                else:
                    df_import = pd.read_excel(archivo_subido)
                
                st.write("👀 Vista previa de los datos encontrados:")
                st.dataframe(df_import.head())
                
                if st.button("✅ Procesar e Importar", type="primary"):
                    with st.spinner("Importando datos..."):
                        cur = conn.cursor()
                        productos_procesados = 0
                        
                        for index, row in df_import.iterrows():
                            codigo = str(row.get('codigo', '')).strip().upper()
                            if not codigo or codigo == 'NAN': continue
                                
                            nombre = str(row.get('nombre', 'Sin nombre')).strip()
                            categoria = str(row.get('categoria', 'General')).strip()
                            p_compra = float(row.get('precio_compra', 0.0) or 0.0)
                            p_venta = float(row.get('precio_venta', 0.0) or 0.0)
                            stock = int(row.get('stock_actual', 0) or 0)
                            s_minimo = int(row.get('stock_minimo', 5) or 5)
                            
                            cur.execute("""
                                INSERT INTO productos (codigo, nombre, categoria, precio_compra, precio_venta, stock_actual, stock_minimo)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (codigo) DO UPDATE SET
                                    nombre = EXCLUDED.nombre,
                                    categoria = EXCLUDED.categoria,
                                    precio_compra = EXCLUDED.precio_compra,
                                    precio_venta = EXCLUDED.precio_venta,
                                    stock_actual = EXCLUDED.stock_actual,
                                    stock_minimo = EXCLUDED.stock_minimo
                            """, (codigo, nombre, categoria, p_compra, p_venta, stock, s_minimo))
                            
                            cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (categoria,))
                            productos_procesados += 1
                            
                        conn.commit()
                        st.success(f"🎉 Importación exitosa. Se procesaron {productos_procesados} productos.")
                        time.sleep(2)
                        st.rerun()
                        
            except Exception as e:
                conn.rollback()
                st.error(f"⚠️ Error al procesar el archivo: {e}")

def mostrar_control_producto(conn):
    st.subheader("📦 Control Individual por Producto (Kardex)")
    st.write("Consulta el historial completo de entradas y salidas de un artículo específico.")
    
    df_p = pd.read_sql("SELECT id, codigo, nombre, stock_actual, stock_minimo FROM productos ORDER BY nombre", conn)
    
    if not df_p.empty:
        col_busqueda, col_vacia = st.columns([2, 1])
        with col_busqueda:
            p_sel = st.selectbox("🔍 Buscar Producto", df_p['codigo'] + " - " + df_p['nombre'])
        
        p_id = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['id'].iloc[0])
        stock_act = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['stock_actual'].iloc[0])
        stock_min = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['stock_minimo'].iloc[0])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Stock Actual", stock_act, delta="Bajo Mínimo" if stock_act <= stock_min else "Óptimo", delta_color="inverse" if stock_act <= stock_min else "normal")
        c2.metric("Stock Mínimo Permitido", stock_min)
        
        query_kardex = """
            SELECT fecha, 'ENTRADA (Compra)' as tipo_movimiento, cantidad, costo_unitario as precio_unidad, 
                   total_compra as total, proveedor as responsable_o_cliente
            FROM compras 
            WHERE producto_id = %s
            UNION ALL
            SELECT fecha, 'SALIDA (Venta)' as tipo_movimiento, cantidad, precio_unitario as precio_unidad, 
                   total_venta as total, cliente as responsable_o_cliente
            FROM ventas 
            WHERE producto_id = %s
            ORDER BY fecha DESC
        """
        
        df_kardex = pd.read_sql(query_kardex, conn, params=(p_id, p_id))
        
        st.markdown("### 📋 Historial de Movimientos")
        if not df_kardex.empty:
            def color_movimiento(val):
                if 'ENTRADA' in str(val): return 'color: green; font-weight: bold'
                elif 'SALIDA' in str(val): return 'color: red; font-weight: bold'
                return ''
                
            st.dataframe(df_kardex.style.map(color_movimiento, subset=['tipo_movimiento']), use_container_width=True)
            
            st.download_button(
                label="📥 Descargar Kardex en Excel",
                data=exportar_excel(df_kardex, "Kardex"),
                file_name=f"Kardex_{p_sel.split(' - ')[0]}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay registros de entradas ni salidas para este producto.")
    else:
        st.warning("No hay productos registrados en el inventario.")

def mostrar_categorias(conn):
    st.subheader("🏷️ Configuración de Categorías")
    tabs = st.tabs(["📋 Editar y Borrar", "➕ Crear Nueva"])
    
    df_cat = pd.read_sql("SELECT nombre FROM categorias ORDER BY nombre", conn)
    
    with tabs[0]:
        st.write("Selecciona una categoría para cambiar su nombre o eliminarla permanentemente.")
        if not df_cat.empty:
            cat_sel = st.selectbox("Seleccionar Categoría", df_cat['nombre'])
            
            col1, col2 = st.columns(2)
            with col1:
                with st.form("form_editar_cat"):
                    st.write("✏️ **Cambiar Nombre**")
                    nuevo_nombre = st.text_input("Nuevo nombre:", value=cat_sel)
                    if st.form_submit_button("Actualizar", type="primary"):
                        if nuevo_nombre.strip() and nuevo_nombre != cat_sel:
                            try:
                                cur = conn.cursor()
                                cur.execute("UPDATE categorias SET nombre = %s WHERE nombre = %s", (nuevo_nombre.strip(), cat_sel))
                                cur.execute("UPDATE productos SET categoria = %s WHERE categoria = %s", (nuevo_nombre.strip(), cat_sel))
                                conn.commit()
                                st.success(f"Categoría cambiada a '{nuevo_nombre.strip()}' con éxito.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error: {e}")
                        else:
                            st.warning("Escribe un nombre distinto y que no esté vacío.")
                            
            with col2:
                with st.form("form_borrar_cat"):
                    st.write("🗑️ **Eliminar Categoría**")
                    st.warning("Asegúrate de que ningún producto use esta categoría.")
                    if st.form_submit_button("Borrar Permanentemente"):
                        try:
                            cur = conn.cursor()
                            cur.execute("SELECT COUNT(*) FROM productos WHERE categoria = %s", (cat_sel,))
                            cant_productos = cur.fetchone()[0]
                            
                            if cant_productos > 0:
                                st.error(f"❌ Imposible borrar: Hay {cant_productos} producto(s) usando esta categoría. Asígnales otra primero.")
                            else:
                                cur.execute("DELETE FROM categorias WHERE nombre = %s", (cat_sel,))
                                conn.commit()
                                st.success("Categoría borrada.")
                                time.sleep(1)
                                st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")
        else:
            st.info("No hay categorías creadas aún.")

    with tabs[1]:
        with st.form("form_nueva_cat"):
            nueva_cat = st.text_input("Nombre de la Nueva Categoría")
            if st.form_submit_button("Crear Categoría"):
                if nueva_cat.strip():
                    try:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO categorias (nombre) VALUES (%s)", (nueva_cat.strip(),))
                        conn.commit()
                        st.success("✅ Categoría creada correctamente.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error("Error: Posiblemente la categoría ya exista.")
                else:
                    st.error("El nombre no puede estar en blanco.")

def mostrar_compras(conn):
    tabs = st.tabs(["➕ Registrar Compra", "📋 Historial de Compras"])
    
    with tabs[0]:
        st.subheader("📥 Registrar Entrada de Mercancía")
        df_p = pd.read_sql("SELECT id, codigo, nombre, precio_compra FROM productos", conn)
        
        if not df_p.empty:
            with st.form("form_compra"):
                c1, c2 = st.columns(2)
                with c1:
                    p_sel = st.selectbox("Producto", df_p['codigo'] + " - " + df_p['nombre'])
                    p_id = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['id'].iloc[0])
                    cant = st.number_input("Cantidad", min_value=1)
                with c2:
                    c_actual = float(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['precio_compra'].iloc[0] or 0)
                    costo = st.number_input("Costo Unitario ($)", value=c_actual, min_value=0.0)
                
                st.info(f"Total Compra: $ {cant * costo:,.0f}")
                if st.form_submit_button("✅ Registrar Compra"):
                    try:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO compras (producto_id, cantidad, costo_unitario, total_compra) VALUES (%s, %s, %s, %s)", (p_id, cant, costo, cant*costo))
                        cur.execute("UPDATE productos SET stock_actual = stock_actual + %s, precio_compra = %s WHERE id = %s", (cant, costo, p_id))
                        conn.commit()
                        st.success("Compra registrada correctamente.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error al registrar: {e}")
        else:
            st.warning("Debe registrar productos en el inventario primero.")
            
    with tabs[1]:
        st.subheader("📋 Historial de Compras")
        df_c = pd.read_sql("SELECT c.fecha, p.codigo, p.nombre, c.cantidad, c.costo_unitario, c.total_compra FROM compras c JOIN productos p ON c.producto_id = p.id ORDER BY c.fecha DESC", conn)
        st.dataframe(df_c, use_container_width=True)
        if not df_c.empty:
            st.download_button("📥 Exportar Compras a Excel", data=exportar_excel(df_c, "Compras"), file_name="Compras.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def mostrar_ventas(conn, vendedor_actual):
    tabs = st.tabs(["➕ Registrar Venta", "📋 Historial de Ventas"])
    
    with tabs[0]:
        st.subheader("💳 Registrar Salida de Mercancía")
        df_p = pd.read_sql("SELECT id, codigo, nombre, precio_venta, stock_actual FROM productos WHERE stock_actual > 0", conn)
        
        if not df_p.empty:
            with st.form("form_venta"):
                c1, c2 = st.columns(2)
                with c1:
                    p_sel = st.selectbox("Producto", df_p['codigo'] + " - " + df_p['nombre'] + " (Stock: " + df_p['stock_actual'].astype(str) + ")")
                    p_id = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['id'].iloc[0])
                    stock = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['stock_actual'].iloc[0])
                    cant = st.number_input("Cantidad", min_value=1, max_value=stock)
                    cliente = st.text_input("Cliente *", placeholder="Nombre del cliente")
                with c2:
                    pv_actual = float(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['precio_venta'].iloc[0] or 0)
                    precio = st.number_input("Precio Venta ($)", value=pv_actual, min_value=0.0)
                    tipo_venta = st.selectbox("Tipo de Venta", ["Contado", "Crédito"])
                    if tipo_venta == "Crédito":
                        fecha_vencimiento = st.date_input("Fecha de Vencimiento")
                    else:
                        fecha_vencimiento = None
                    metodo = st.selectbox("Método de Pago", ["Efectivo", "Tarjeta", "Transferencia"])
                
                st.info(f"Total a cobrar: $ {cant * precio:,.0f}")
                if st.form_submit_button("✅ Confirmar Venta"):
                    if not cliente.strip():
                        st.error("⚠️ El nombre del cliente es obligatorio.")
                    else:
                        try:
                            cur = conn.cursor()
                            cur.execute("INSERT INTO ventas (producto_id, cantidad, precio_unitario, total_venta, metodo_pago, vendedor, cliente, tipo_venta, fecha_vencimiento) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (p_id, cant, precio, cant*precio, metodo, vendedor_actual, cliente, tipo_venta, fecha_vencimiento))
                            cur.execute("UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s", (cant, p_id))
                            conn.commit()
                            st.success("Venta registrada correctamente.")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error al registrar: {e}")
        else:
            st.warning("No hay productos con stock disponible.")
            
    with tabs[1]:
        st.subheader("📋 Historial de Ventas")
        df_v = pd.read_sql("SELECT v.fecha, p.nombre, v.cantidad, v.precio_unitario, v.total_venta, v.cliente, v.tipo_venta, v.fecha_vencimiento FROM ventas v JOIN productos p ON v.producto_id = p.id ORDER BY v.fecha DESC", conn)
        st.dataframe(df_v, use_container_width=True)
        if not df_v.empty:
            st.download_button("📥 Exportar Ventas a Excel", data=exportar_excel(df_v, "Ventas"), file_name="Ventas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def mostrar_balance(conn):
    st.subheader("📊 Balance General del Negocio")
    
    inventario_df = pd.read_sql("""
        SELECT 
            COUNT(*) as total_productos,
            SUM(stock_actual) as total_unidades,
            SUM(stock_actual * precio_compra) as valor_costo,
            SUM(stock_actual * precio_venta) as valor_venta
        FROM productos
    """, conn)
    
    st.markdown("### 📦 Resumen de Inventario Físico")
    if not inventario_df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Productos Únicos", inventario_df['total_productos'].iloc[0])
        c2.metric("Unidades Totales", int(inventario_df['total_unidades'].iloc[0] or 0))
        c3.metric("Inversión (Costo)", f"$ {inventario_df['valor_costo'].iloc[0] or 0:,.0f}")
        c4.metric("Valor de Venta Proyectado", f"$ {inventario_df['valor_venta'].iloc[0] or 0:,.0f}")
        
    st.markdown("### 💵 Flujo de Caja y Utilidad Real")
    
    ingresos = pd.read_sql("SELECT COALESCE(SUM(total_venta), 0) FROM ventas", conn).iloc[0,0]
    egresos = pd.read_sql("SELECT COALESCE(SUM(total_compra), 0) FROM compras", conn).iloc[0,0]
    flujo_caja = ingresos - egresos
    
    query_utilidad = """
        SELECT COALESCE(SUM(v.cantidad * (v.precio_unitario - p.precio_compra)), 0) as utilidad_real
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
    """
    utilidad_real = pd.read_sql(query_utilidad, conn).iloc[0,0]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Ingresos Históricos", f"$ {ingresos:,.0f}")
    col2.metric("Total Egresos Históricos", f"$ {egresos:,.0f}")
    col3.metric("Flujo de Caja Libre", f"$ {flujo_caja:,.0f}")
    col4.metric("Utilidad (Ganancia Neta)", f"$ {utilidad_real:,.0f}")
    
    st.info("💡 **Nota de cálculo:** El *Flujo de Caja* es el dinero líquido que te queda tras las compras. La *Utilidad* es la ganancia real obtenida exclusivamente de los productos que ya lograste vender (Precio Venta - Precio Costo).")

# --- CONTROLADOR PRINCIPAL DE LA APLICACIÓN ---
def main():
    if 'db_ready' not in st.session_state:
        try:
            inicializar_tablas()
            st.session_state['db_ready'] = True
        except Exception as e:
            st.error(f"Error conectando a la base de datos: {e}")
            st.stop()

    if not st.session_state.get('logged_in', False):
        st.sidebar.title("🔐 Acceso al Sistema")
        u = st.sidebar.text_input("Usuario")
        p = st.sidebar.text_input("Contraseña", type="password")
        
        if st.sidebar.button("Ingresar"):
            conn = conectar_db()
            cur = conn.cursor()
            cur.execute("SELECT rol FROM usuarios WHERE usuario=%s AND clave=%s", (u, p))
            res = cur.fetchone()
            if res:
                st.session_state['logged_in'] = True
                st.session_state['u_rol'] = res[0]
                st.rerun()
            else:
                st.sidebar.error("Usuario o contraseña incorrectos")
            conn.close()
            
        st.title("📦 Neira Store - Sistema de Inventario")
        st.info("👋 Bienvenido. Por favor ingresa tus credenciales en el panel izquierdo para comenzar.")
        st.stop()

    st.sidebar.title("📦 Panel de Control")
    opciones = ["🏠 Inicio", "📦 Productos", "📋 Control por Producto", "📥 Compras (Entradas)", "💳 Ventas (Salidas)", "📊 Balance General"]
    
    if st.session_state.get('u_rol') == "admin": 
        opciones.extend(["🏷️ Categorías"])
        
    menu = st.sidebar.radio("Navegación", opciones)

    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

    conn = conectar_db()
    
    if menu == "🏠 Inicio":
        mostrar_dashboard(conn)
    elif menu == "📦 Productos":
        mostrar_productos(conn)
    elif menu == "📋 Control por Producto":
        mostrar_control_producto(conn)
    elif menu == "📥 Compras (Entradas)":
        mostrar_compras(conn)
    elif menu == "💳 Ventas (Salidas)":
        mostrar_ventas(conn, st.session_state.get('u_rol'))
    elif menu == "📊 Balance General":
        mostrar_balance(conn)
    elif menu == "🏷️ Categorías":
        mostrar_categorias(conn)
        
    conn.close()

if __name__ == "__main__":
    main()
from datetime import datetime
import time
import io

# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="Neira Store - Inventario", layout="wide", page_icon="📦")
DB_URL = st.secrets["DB_URL"]

# --- CONTROL ESTRICTO DE VENTANAS DUPLICADAS ---
if 'sesion_activa' not in st.session_state:
    st.session_state['sesion_activa'] = True
elif not st.session_state.get('sesion_activa', False):
    st.error("⚠️ Ya hay una ventana o sesión abierta. Cierre las ventanas repetidas para evitar conflictos.")
    st.stop()

# --- FUNCIONES DE BASE DE DATOS ---
def conectar_db():
    return psycopg2.connect(DB_URL)

def inicializar_tablas():
    conn = conectar_db()
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute('''CREATE TABLE IF NOT EXISTS productos (
        id SERIAL PRIMARY KEY, codigo TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL, 
        categoria TEXT, precio_compra NUMERIC DEFAULT 0.0, precio_venta NUMERIC DEFAULT 0.0, 
        stock_actual INTEGER DEFAULT 0, stock_minimo INTEGER DEFAULT 5,
        proveedor TEXT, ubicacion TEXT, fecha_registro DATE DEFAULT CURRENT_DATE
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS ventas (
        id SERIAL PRIMARY KEY, producto_id INTEGER REFERENCES productos(id), 
        cantidad INTEGER NOT NULL, precio_unitario NUMERIC, total_venta NUMERIC, 
        fecha DATE DEFAULT CURRENT_DATE, metodo_pago TEXT DEFAULT 'Efectivo',
        cliente TEXT, vendedor TEXT, estado TEXT DEFAULT 'Completada',
        factura TEXT, observaciones TEXT, tipo_venta TEXT DEFAULT 'Contado',
        fecha_vencimiento DATE
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS compras (
        id SERIAL PRIMARY KEY, producto_id INTEGER REFERENCES productos(id), 
        cantidad INTEGER NOT NULL, costo_unitario NUMERIC, total_compra NUMERIC, 
        fecha DATE DEFAULT CURRENT_DATE, proveedor TEXT, factura_compra TEXT,
        estado TEXT DEFAULT 'Recibida', observaciones TEXT
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, nombre TEXT, usuario TEXT UNIQUE, 
        clave TEXT, rol TEXT DEFAULT 'vendedor'
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS configuracion (
        id SERIAL PRIMARY KEY, nombre_negocio TEXT DEFAULT 'Neira Store',
        direccion TEXT, telefono TEXT, email TEXT,
        iva NUMERIC DEFAULT 0.0, moneda TEXT DEFAULT '$'
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS categorias (
        id SERIAL PRIMARY KEY, nombre TEXT UNIQUE NOT NULL
    )''')
    
    # Datos iniciales por defecto
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Administrador', 'admin', 'admin2026', 'admin') ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Vendedor', 'vendedor', 'vende2026', 'vendedor') ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO configuracion (id, nombre_negocio, moneda) VALUES (1, 'Neira Store', '$') ON CONFLICT (id) DO NOTHING")
    
    categorias_base = ["Electrónica", "Ropa", "Alimentos", "Hogar", "Juguetes", "Herramientas", "Libros", "Deportes"]
    for cat in categorias_base:
        cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (cat,))
        
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN cliente TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN tipo_venta TEXT DEFAULT 'Contado'")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN fecha_vencimiento DATE")
    except Exception:
        pass
        
    conn.close()

# --- FUNCIONES DE EXPORTACIÓN A EXCEL ---
def exportar_excel(df, nombre_hoja='Reporte'):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=nombre_hoja)
    return output.getvalue()

# --- VISTAS DE LA APLICACIÓN (MÓDULOS) ---

def mostrar_dashboard(conn):
    st.subheader("📊 Dashboard General")
    total_productos = pd.read_sql("SELECT COUNT(*) FROM productos", conn).iloc[0,0]
    ventas_total = pd.read_sql("SELECT SUM(total_venta) FROM ventas", conn).iloc[0,0] or 0
    ventas_hoy = pd.read_sql("SELECT SUM(total_venta) FROM ventas WHERE fecha = CURRENT_DATE", conn).iloc[0,0] or 0
    stock_bajo = pd.read_sql("SELECT COUNT(*) FROM productos WHERE stock_actual <= stock_minimo", conn).iloc[0,0] or 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Total Productos", total_productos)
    c2.metric("💰 Ventas Totales", f"$ {ventas_total:,.0f}")
    c3.metric("📈 Ventas Hoy", f"$ {ventas_hoy:,.0f}")
    c4.metric("⚠️ Stock Bajo", stock_bajo, delta="Revisar" if stock_bajo > 0 else "OK", delta_color="inverse")
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Ventas por Producto (Top 5)")
        top_productos = pd.read_sql("SELECT p.nombre, SUM(v.cantidad) as total_vendido FROM ventas v JOIN productos p ON v.producto_id = p.id GROUP BY p.nombre ORDER BY total_vendido DESC LIMIT 5", conn)
        if not top_productos.empty: 
            st.bar_chart(data=top_productos.set_index('nombre'))
        else: 
            st.info("No hay datos de ventas aún.")
        
    with col2:
        st.subheader("📈 Ventas por Categoría")
        ventas_categoria = pd.read_sql("SELECT p.categoria, SUM(v.total_venta) as total FROM ventas v JOIN productos p ON v.producto_id = p.id GROUP BY p.categoria ORDER BY total DESC", conn)
        if not ventas_categoria.empty: 
            st.dataframe(ventas_categoria, use_container_width=True)
        else: 
            st.info("No hay datos de ventas aún.")

def mostrar_productos(conn):
    tabs = st.tabs(["➕ Nuevo Producto", "🔍 Ver Inventario", "⬆️ Importar Masivamente"])
    categorias_lista = pd.read_sql("SELECT nombre FROM categorias ORDER BY nombre", conn)['nombre'].tolist()
    
    with tabs[0]:
        with st.form("form_nuevo_producto"):
            st.subheader("Registrar Nuevo Producto")
            c1, c2 = st.columns(2)
            with c1:
                codigo = st.text_input("Código *")
                nombre = st.text_input("Nombre *")
                categoria = st.selectbox("Categoría", categorias_lista + ["Nueva..."])
                cat_nueva = st.text_input("Nombre de nueva categoría") if categoria == "Nueva..." else None
            with c2:
                p_compra = st.number_input("Precio Compra ($)", min_value=0.0)
                p_venta = st.number_input("Precio Venta ($)", min_value=0.0)
                s_inicial = st.number_input("Stock Inicial", min_value=0)
                s_minimo = st.number_input("Stock Mínimo", value=5)
            
            if st.form_submit_button("💾 Guardar Producto"):
                if not codigo or not nombre: 
                    st.error("El código y el nombre son obligatorios")
                else:
                    cur = conn.cursor()
                    cat_final = cat_nueva if categoria == "Nueva..." and cat_nueva else categoria
                    try:
                        cur.execute("INSERT INTO productos (codigo, nombre, categoria, precio_compra, precio_venta, stock_actual, stock_minimo) VALUES (%s, %s, %s, %s, %s, %s, %s)", (codigo.upper(), nombre, cat_final, p_compra, p_venta, s_inicial, s_minimo))
                        if categoria == "Nueva..." and cat_nueva:
                            cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (cat_nueva,))
                        conn.commit()
                        st.success("✅ Producto registrado exitosamente")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error: El código '{codigo}' ya podría estar registrado.")
                        
    with tabs[1]:
        st.subheader("📋 Inventario Actual")
        df = pd.read_sql("SELECT codigo, nombre, categoria, precio_compra, precio_venta, stock_actual, stock_minimo FROM productos ORDER BY nombre", conn)
        st.dataframe(df, use_container_width=True)
        if not df.empty:
            st.download_button(
                label="📥 Exportar Inventario a Excel",
                data=exportar_excel(df, "Inventario"),
                file_name=f"Inventario_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    with tabs[2]:
        st.subheader("⬆️ Importar Productos desde Excel")
        st.info("💡 Tu archivo debe contener exactamente las siguientes columnas en la primera fila (en minúsculas): \n `codigo`, `nombre`, `categoria`, `precio_compra`, `precio_venta`, `stock_actual`, `stock_minimo`")
        
        archivo_subido = st.file_uploader("Selecciona tu archivo de inventario", type=['xlsx', 'xls', 'csv'])
        
        if archivo_subido is not None:
            try:
                if archivo_subido.name.endswith('.csv'):
                    df_import = pd.read_csv(archivo_subido)
                else:
                    df_import = pd.read_excel(archivo_subido)
                
                st.write("👀 Vista previa de los datos encontrados:")
                st.dataframe(df_import.head())
                
                if st.button("✅ Procesar e Importar", type="primary"):
                    with st.spinner("Importando datos..."):
                        cur = conn.cursor()
                        productos_procesados = 0
                        
                        for index, row in df_import.iterrows():
                            codigo = str(row.get('codigo', '')).strip().upper()
                            if not codigo or codigo == 'NAN': continue
                                
                            nombre = str(row.get('nombre', 'Sin nombre')).strip()
                            categoria = str(row.get('categoria', 'General')).strip()
                            p_compra = float(row.get('precio_compra', 0.0) or 0.0)
                            p_venta = float(row.get('precio_venta', 0.0) or 0.0)
                            stock = int(row.get('stock_actual', 0) or 0)
                            s_minimo = int(row.get('stock_minimo', 5) or 5)
                            
                            cur.execute("""
                                INSERT INTO productos (codigo, nombre, categoria, precio_compra, precio_venta, stock_actual, stock_minimo)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (codigo) DO UPDATE SET
                                    nombre = EXCLUDED.nombre,
                                    categoria = EXCLUDED.categoria,
                                    precio_compra = EXCLUDED.precio_compra,
                                    precio_venta = EXCLUDED.precio_venta,
                                    stock_actual = EXCLUDED.stock_actual,
                                    stock_minimo = EXCLUDED.stock_minimo
                            """, (codigo, nombre, categoria, p_compra, p_venta, stock, s_minimo))
                            
                            cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (categoria,))
                            productos_procesados += 1
                            
                        conn.commit()
                        st.success(f"🎉 Importación exitosa. Se procesaron {productos_procesados} productos.")
                        time.sleep(2)
                        st.rerun()
                        
            except Exception as e:
                conn.rollback()
                st.error(f"⚠️ Error al procesar el archivo: {e}")

def mostrar_control_producto(conn):
    st.subheader("📦 Control Individual por Producto (Kardex)")
    st.write("Consulta el historial completo de entradas y salidas de un artículo específico.")
    
    df_p = pd.read_sql("SELECT id, codigo, nombre, stock_actual, stock_minimo FROM productos ORDER BY nombre", conn)
    
    if not df_p.empty:
        col_busqueda, col_vacia = st.columns([2, 1])
        with col_busqueda:
            p_sel = st.selectbox("🔍 Buscar Producto", df_p['codigo'] + " - " + df_p['nombre'])
        
        p_id = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['id'].iloc[0])
        stock_act = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['stock_actual'].iloc[0])
        stock_min = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['stock_minimo'].iloc[0])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Stock Actual", stock_act, delta="Bajo Mínimo" if stock_act <= stock_min else "Óptimo", delta_color="inverse" if stock_act <= stock_min else "normal")
        c2.metric("Stock Mínimo Permitido", stock_min)
        
        query_kardex = """
            SELECT fecha, 'ENTRADA (Compra)' as tipo_movimiento, cantidad, costo_unitario as precio_unidad, 
                   total_compra as total, proveedor as responsable_o_cliente
            FROM compras 
            WHERE producto_id = %s
            UNION ALL
            SELECT fecha, 'SALIDA (Venta)' as tipo_movimiento, cantidad, precio_unitario as precio_unidad, 
                   total_venta as total, cliente as responsable_o_cliente
            FROM ventas 
            WHERE producto_id = %s
            ORDER BY fecha DESC
        """
        
        df_kardex = pd.read_sql(query_kardex, conn, params=(p_id, p_id))
        
        st.markdown("### 📋 Historial de Movimientos")
        if not df_kardex.empty:
            def color_movimiento(val):
                if 'ENTRADA' in str(val): return 'color: green; font-weight: bold'
                elif 'SALIDA' in str(val): return 'color: red; font-weight: bold'
                return ''
                
            st.dataframe(df_kardex.style.map(color_movimiento, subset=['tipo_movimiento']), use_container_width=True)
            
            st.download_button(
                label="📥 Descargar Kardex en Excel",
                data=exportar_excel(df_kardex, "Kardex"),
                file_name=f"Kardex_{p_sel.split(' - ')[0]}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay registros de entradas ni salidas para este producto.")
    else:
        st.warning("No hay productos registrados en el inventario.")

def mostrar_categorias(conn):
    st.subheader("🏷️ Configuración de Categorías")
    tabs = st.tabs(["📋 Editar y Borrar", "➕ Crear Nueva"])
    
    df_cat = pd.read_sql("SELECT nombre FROM categorias ORDER BY nombre", conn)
    
    with tabs[0]:
        st.write("Selecciona una categoría para cambiar su nombre o eliminarla permanentemente.")
        if not df_cat.empty:
            cat_sel = st.selectbox("Seleccionar Categoría", df_cat['nombre'])
            
            col1, col2 = st.columns(2)
            with col1:
                with st.form("form_editar_cat"):
                    st.write("✏️ **Cambiar Nombre**")
                    nuevo_nombre = st.text_input("Nuevo nombre:", value=cat_sel)
                    if st.form_submit_button("Actualizar", type="primary"):
                        if nuevo_nombre.strip() and nuevo_nombre != cat_sel:
                            try:
                                cur = conn.cursor()
                                cur.execute("UPDATE categorias SET nombre = %s WHERE nombre = %s", (nuevo_nombre.strip(), cat_sel))
                                cur.execute("UPDATE productos SET categoria = %s WHERE categoria = %s", (nuevo_nombre.strip(), cat_sel))
                                conn.commit()
                                st.success(f"Categoría cambiada a '{nuevo_nombre.strip()}' con éxito.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Error: {e}")
                        else:
                            st.warning("Escribe un nombre distinto y que no esté vacío.")
                            
            with col2:
                with st.form("form_borrar_cat"):
                    st.write("🗑️ **Eliminar Categoría**")
                    st.warning("Asegúrate de que ningún producto use esta categoría.")
                    if st.form_submit_button("Borrar Permanentemente"):
                        try:
                            cur = conn.cursor()
                            cur.execute("SELECT COUNT(*) FROM productos WHERE categoria = %s", (cat_sel,))
                            cant_productos = cur.fetchone()[0]
                            
                            if cant_productos > 0:
                                st.error(f"❌ Imposible borrar: Hay {cant_productos} producto(s) usando esta categoría. Asígnales otra primero.")
                            else:
                                cur.execute("DELETE FROM categorias WHERE nombre = %s", (cat_sel,))
                                conn.commit()
                                st.success("Categoría borrada.")
                                time.sleep(1)
                                st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error: {e}")
        else:
            st.info("No hay categorías creadas aún.")

    with tabs[1]:
        with st.form("form_nueva_cat"):
            nueva_cat = st.text_input("Nombre de la Nueva Categoría")
            if st.form_submit_button("Crear Categoría"):
                if nueva_cat.strip():
                    try:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO categorias (nombre) VALUES (%s)", (nueva_cat.strip(),))
                        conn.commit()
                        st.success("✅ Categoría creada correctamente.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error("Error: Posiblemente la categoría ya exista.")
                else:
                    st.error("El nombre no puede estar en blanco.")

def mostrar_compras(conn):
    tabs = st.tabs(["➕ Registrar Compra", "📋 Historial de Compras"])
    
    with tabs[0]:
        st.subheader("📥 Registrar Entrada de Mercancía")
        df_p = pd.read_sql("SELECT id, codigo, nombre, precio_compra FROM productos", conn)
        
        if not df_p.empty:
            with st.form("form_compra"):
                c1, c2 = st.columns(2)
                with c1:
                    p_sel = st.selectbox("Producto", df_p['codigo'] + " - " + df_p['nombre'])
                    p_id = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['id'].iloc[0])
                    cant = st.number_input("Cantidad", min_value=1)
                with c2:
                    c_actual = float(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['precio_compra'].iloc[0] or 0)
                    costo = st.number_input("Costo Unitario ($)", value=c_actual, min_value=0.0)
                
                st.info(f"Total Compra: $ {cant * costo:,.0f}")
                if st.form_submit_button("✅ Registrar Compra"):
                    try:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO compras (producto_id, cantidad, costo_unitario, total_compra) VALUES (%s, %s, %s, %s)", (p_id, cant, costo, cant*costo))
                        cur.execute("UPDATE productos SET stock_actual = stock_actual + %s, precio_compra = %s WHERE id = %s", (cant, costo, p_id))
                        conn.commit()
                        st.success("Compra registrada correctamente.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error al registrar: {e}")
        else:
            st.warning("Debe registrar productos en el inventario primero.")
            
    with tabs[1]:
        st.subheader("📋 Historial de Compras")
        df_c = pd.read_sql("SELECT c.fecha, p.codigo, p.nombre, c.cantidad, c.costo_unitario, c.total_compra FROM compras c JOIN productos p ON c.producto_id = p.id ORDER BY c.fecha DESC", conn)
        st.dataframe(df_c, use_container_width=True)
        if not df_c.empty:
            st.download_button("📥 Exportar Compras a Excel", data=exportar_excel(df_c, "Compras"), file_name="Compras.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def mostrar_ventas(conn, vendedor_actual):
    tabs = st.tabs(["➕ Registrar Venta", "📋 Historial de Ventas"])
    
    with tabs[0]:
        st.subheader("💳 Registrar Salida de Mercancía")
        df_p = pd.read_sql("SELECT id, codigo, nombre, precio_venta, stock_actual FROM productos WHERE stock_actual > 0", conn)
        
        if not df_p.empty:
            with st.form("form_venta"):
                c1, c2 = st.columns(2)
                with c1:
                    p_sel = st.selectbox("Producto", df_p['codigo'] + " - " + df_p['nombre'] + " (Stock: " + df_p['stock_actual'].astype(str) + ")")
                    p_id = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['id'].iloc[0])
                    stock = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['stock_actual'].iloc[0])
                    cant = st.number_input("Cantidad", min_value=1, max_value=stock)
                    cliente = st.text_input("Cliente *", placeholder="Nombre del cliente")
                with c2:
                    pv_actual = float(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['precio_venta'].iloc[0] or 0)
                    precio = st.number_input("Precio Venta ($)", value=pv_actual, min_value=0.0)
                    tipo_venta = st.selectbox("Tipo de Venta", ["Contado", "Crédito"])
                    if tipo_venta == "Crédito":
                        fecha_vencimiento = st.date_input("Fecha de Vencimiento")
                    else:
                        fecha_vencimiento = None
                    metodo = st.selectbox("Método de Pago", ["Efectivo", "Tarjeta", "Transferencia"])
                
                st.info(f"Total a cobrar: $ {cant * precio:,.0f}")
                if st.form_submit_button("✅ Confirmar Venta"):
                    if not cliente.strip():
                        st.error("⚠️ El nombre del cliente es obligatorio.")
                    else:
                        try:
                            cur = conn.cursor()
                            cur.execute("INSERT INTO ventas (producto_id, cantidad, precio_unitario, total_venta, metodo_pago, vendedor, cliente, tipo_venta, fecha_vencimiento) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (p_id, cant, precio, cant*precio, metodo, vendedor_actual, cliente, tipo_venta, fecha_vencimiento))
                            cur.execute("UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s", (cant, p_id))
                            conn.commit()
                            st.success("Venta registrada correctamente.")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error al registrar: {e}")
        else:
            st.warning("No hay productos con stock disponible.")
            
    with tabs[1]:
        st.subheader("📋 Historial de Ventas")
        df_v = pd.read_sql("SELECT v.fecha, p.nombre, v.cantidad, v.precio_unitario, v.total_venta, v.cliente, v.tipo_venta, v.fecha_vencimiento FROM ventas v JOIN productos p ON v.producto_id = p.id ORDER BY v.fecha DESC", conn)
        st.dataframe(df_v, use_container_width=True)
        if not df_v.empty:
            st.download_button("📥 Exportar Ventas a Excel", data=exportar_excel(df_v, "Ventas"), file_name="Ventas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def mostrar_balance(conn):
    st.subheader("📊 Balance General del Negocio")
    
    inventario_df = pd.read_sql("""
        SELECT 
            COUNT(*) as total_productos,
            SUM(stock_actual) as total_unidades,
            SUM(stock_actual * precio_compra) as valor_costo,
            SUM(stock_actual * precio_venta) as valor_venta
        FROM productos
    """, conn)
    
    st.markdown("### 📦 Resumen de Inventario Físico")
    if not inventario_df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Productos Únicos", inventario_df['total_productos'].iloc[0])
        c2.metric("Unidades Totales", int(inventario_df['total_unidades'].iloc[0] or 0))
        c3.metric("Inversión (Costo)", f"$ {inventario_df['valor_costo'].iloc[0] or 0:,.0f}")
        c4.metric("Valor de Venta Proyectado", f"$ {inventario_df['valor_venta'].iloc[0] or 0:,.0f}")
        
    st.markdown("### 💵 Flujo de Caja y Utilidad Real")
    
    ingresos = pd.read_sql("SELECT COALESCE(SUM(total_venta), 0) FROM ventas", conn).iloc[0,0]
    egresos = pd.read_sql("SELECT COALESCE(SUM(total_compra), 0) FROM compras", conn).iloc[0,0]
    flujo_caja = ingresos - egresos
    
    query_utilidad = """
        SELECT COALESCE(SUM(v.cantidad * (v.precio_unitario - p.precio_compra)), 0) as utilidad_real
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
    """
    utilidad_real = pd.read_sql(query_utilidad, conn).iloc[0,0]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Ingresos Históricos", f"$ {ingresos:,.0f}")
    col2.metric("Total Egresos Históricos", f"$ {egresos:,.0f}")
    col3.metric("Flujo de Caja Libre", f"$ {flujo_caja:,.0f}")
    col4.metric("Utilidad (Ganancia Neta)", f"$ {utilidad_real:,.0f}")
    
    st.info("💡 **Nota de cálculo:** El *Flujo de Caja* es el dinero líquido que te queda tras las compras. La *Utilidad* es la ganancia real obtenida exclusivamente de los productos que ya lograste vender (Precio Venta - Precio Costo).")

# --- CONTROLADOR PRINCIPAL DE LA APLICACIÓN ---
def main():
    if 'db_ready' not in st.session_state:
        try:
            inicializar_tablas()
            st.session_state['db_ready'] = True
        except Exception as e:
            st.error(f"Error conectando a la base de datos: {e}")
            st.stop()

    if not st.session_state.get('logged_in', False):
        st.sidebar.title("🔐 Acceso al Sistema")
        u = st.sidebar.text_input("Usuario")
        p = st.sidebar.text_input("Contraseña", type="password")
        
        if st.sidebar.button("Ingresar"):
            conn = conectar_db()
            cur = conn.cursor()
            cur.execute("SELECT rol FROM usuarios WHERE usuario=%s AND clave=%s", (u, p))
            res = cur.fetchone()
            if res:
                st.session_state['logged_in'] = True
                st.session_state['u_rol'] = res[0]
                st.rerun()
            else:
                st.sidebar.error("Usuario o contraseña incorrectos")
            conn.close()
            
        st.title("📦 Neira Store - Sistema de Inventario")
        st.info("👋 Bienvenido. Por favor ingresa tus credenciales en el panel izquierdo para comenzar.")
        st.stop()

    st.sidebar.title("📦 Panel de Control")
    opciones = ["🏠 Inicio", "📦 Productos", "📋 Control por Producto", "📥 Compras (Entradas)", "💳 Ventas (Salidas)", "📊 Balance General"]
    
    if st.session_state.get('u_rol') == "admin": 
        opciones.extend(["🏷️ Categorías"])
        
    menu = st.sidebar.radio("Navegación", opciones)

    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

    conn = conectar_db()
    
    if menu == "🏠 Inicio":
        mostrar_dashboard(conn)
    elif menu == "📦 Productos":
        mostrar_productos(conn)
    elif menu == "📋 Control por Producto":
        mostrar_control_producto(conn)
    elif menu == "📥 Compras (Entradas)":
        mostrar_compras(conn)
    elif menu == "💳 Ventas (Salidas)":
        mostrar_ventas(conn, st.session_state.get('u_rol'))
    elif menu == "📊 Balance General":
        mostrar_balance(conn)
    elif menu == "🏷️ Categorías":
        mostrar_categorias(conn)
        
    conn.close()

if __name__ == "__main__":
    main()
