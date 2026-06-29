# ==========================================
# inventory_system.py
# Sistema de Inventario y Ventas - Jacobo Store
# ==========================================

import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import hashlib
import time

# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="Jacobo Store - Inventario", layout="wide", page_icon="📦")
DB_URL = st.secrets["DB_URL"]

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
        factura TEXT, observaciones TEXT
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
        id SERIAL PRIMARY KEY, nombre_negocio TEXT DEFAULT 'Mi Tienda',
        direccion TEXT, telefono TEXT, email TEXT,
        iva NUMERIC DEFAULT 0.0, moneda TEXT DEFAULT '€'
    )''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS categorias (
        id SERIAL PRIMARY KEY, nombre TEXT UNIQUE NOT NULL
    )''')
    
    # Datos iniciales por defecto
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Administrador', 'admin', 'admin2026', 'admin') ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Vendedor', 'vendedor', 'vende2026', 'vendedor') ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO configuracion (id, nombre_negocio, moneda) VALUES (1, 'Mi Tienda', '€') ON CONFLICT (id) DO NOTHING")
    
    categorias_base = ["Electrónica", "Ropa", "Alimentos", "Hogar", "Juguetes", "Herramientas", "Libros", "Deportes"]
    for cat in categorias_base:
        cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (cat,))
        
    conn.close()

# --- VISTAS DE LA APLICACIÓN (MÓDULOS) ---

def mostrar_dashboard(conn):
    st.subheader("📊 Dashboard General")
    total_productos = pd.read_sql("SELECT COUNT(*) FROM productos", conn).iloc[0,0]
    ventas_total = pd.read_sql("SELECT SUM(total_venta) FROM ventas", conn).iloc[0,0] or 0
    ventas_hoy = pd.read_sql("SELECT SUM(total_venta) FROM ventas WHERE fecha = CURRENT_DATE", conn).iloc[0,0] or 0
    stock_bajo = pd.read_sql("SELECT COUNT(*) FROM productos WHERE stock_actual <= stock_minimo", conn).iloc[0,0] or 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Total Productos", total_productos)
    c2.metric("💰 Ventas Totales", f"{ventas_total:,.2f} €")
    c3.metric("📈 Ventas Hoy", f"{ventas_hoy:,.2f} €")
    c4.metric("⚠️ Stock Bajo", stock_bajo, delta="Revisar" if stock_bajo > 0 else "OK")
    
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
    tabs = st.tabs(["➕ Nuevo Producto", "🔍 Ver Inventario"])
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
                p_compra = st.number_input("Precio Compra (€)", min_value=0.0, step=0.01)
                p_venta = st.number_input("Precio Venta (€)", min_value=0.0, step=0.01)
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

def mostrar_compras(conn):
    st.subheader("📥 Registrar Entrada de Mercancía")
    df_p = pd.read_sql("SELECT id, codigo, nombre, precio_compra FROM productos", conn)
    
    if not df_p.empty:
        with st.form("form_compra"):
            c1, c2 = st.columns(2)
            with c1:
                p_sel = st.selectbox("Producto", df_p['codigo'] + " - " + df_p['nombre'])
                p_id = df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['id'].values[0]
                cant = st.number_input("Cantidad", min_value=1)
            with c2:
                c_actual = float(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['precio_compra'].values[0] or 0)
                costo = st.number_input("Costo Unitario (€)", value=c_actual, min_value=0.0, step=0.01)
            
            if st.form_submit_button("✅ Registrar Compra"):
                cur = conn.cursor()
                cur.execute("INSERT INTO compras (producto_id, cantidad, costo_unitario, total_compra) VALUES (%s, %s, %s, %s)", (p_id, cant, costo, cant*costo))
                cur.execute("UPDATE productos SET stock_actual = stock_actual + %s, precio_compra = %s WHERE id = %s", (cant, costo, p_id))
                conn.commit()
                st.success("Compra registrada correctamente.")
                time.sleep(1)
                st.rerun()
    else:
        st.warning("Debe registrar productos en el inventario primero.")

def mostrar_ventas(conn, vendedor_actual):
    st.subheader("💳 Registrar Salida de Mercancía")
    df_p = pd.read_sql("SELECT id, codigo, nombre, precio_venta, stock_actual FROM productos WHERE stock_actual > 0", conn)
    
    if not df_p.empty:
        with st.form("form_venta"):
            c1, c2 = st.columns(2)
            with c1:
                p_sel = st.selectbox("Producto", df_p['codigo'] + " - " + df_p['nombre'] + " (Stock: " + df_p['stock_actual'].astype(str) + ")")
                p_id = df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['id'].values[0]
                stock = int(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['stock_actual'].values[0])
                cant = st.number_input("Cantidad", min_value=1, max_value=stock)
            with c2:
                pv_actual = float(df_p[df_p['codigo'] == p_sel.split(" - ")[0]]['precio_venta'].values[0] or 0)
                precio = st.number_input("Precio Venta (€)", value=pv_actual, min_value=0.0, step=0.01)
                metodo = st.selectbox("Método de Pago", ["Efectivo", "Tarjeta", "Transferencia"])
            
            st.info(f"Total a cobrar: {cant * precio:,.2f} €")
            if st.form_submit_button("✅ Confirmar Venta"):
                cur = conn.cursor()
                cur.execute("INSERT INTO ventas (producto_id, cantidad, precio_unitario, total_venta, metodo_pago, vendedor) VALUES (%s, %s, %s, %s, %s, %s)", (p_id, cant, precio, cant*precio, metodo, vendedor_actual))
                cur.execute("UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s", (cant, p_id))
                conn.commit()
                st.success("Venta registrada correctamente.")
                time.sleep(1)
                st.rerun()
    else:
        st.warning("No hay productos con stock disponible.")

def mostrar_balance(conn):
    st.subheader("📊 Balance General del Negocio")
    
    # Esta sección estaba cortada en tu archivo original. Aquí está completada:
    inventario_df = pd.read_sql("""
        SELECT 
            COUNT(*) as total_productos,
            SUM(stock_actual) as total_unidades,
            SUM(stock_actual * precio_compra) as valor_costo,
            SUM(stock_actual * precio_venta) as valor_venta
        FROM productos
    """, conn)
    
    st.markdown("### 📦 Resumen de Inventario")
    if not inventario_df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Productos Únicos", inventario_df['total_productos'].iloc[0])
        c2.metric("Unidades Totales", inventario_df['total_unidades'].iloc[0] or 0)
        c3.metric("Inversión (Costo)", f"{inventario_df['valor_costo'].iloc[0] or 0:,.2f} €")
        c4.metric("Valor de Venta Proyectado", f"{inventario_df['valor_venta'].iloc[0] or 0:,.2f} €")
        
    st.markdown("### 💵 Flujo de Caja")
    ingresos = pd.read_sql("SELECT COALESCE(SUM(total_venta), 0) FROM ventas", conn).iloc[0,0]
    egresos = pd.read_sql("SELECT COALESCE(SUM(total_compra), 0) FROM compras", conn).iloc[0,0]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos Históricos", f"{ingresos:,.2f} €")
    col2.metric("Egresos Históricos", f"{egresos:,.2f} €")
    col3.metric("Balance Neto", f"{ingresos - egresos:,.2f} €")

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
            
        st.title("📦 Jacobo Store - Sistema de Inventario")
        st.info("👋 Bienvenido. Por favor ingresa tus credenciales en el panel izquierdo para comenzar.")
        st.stop()

    # Configuración del Menú Lateral
    st.sidebar.title("📦 Panel de Control")
    opciones = ["🏠 Inicio", "📦 Productos", "📥 Compras (Entradas)", "💳 Ventas (Salidas)", "📊 Balance General"]
    
    if st.session_state.get('u_rol') == "admin": 
        opciones.extend(["🏷️ Categorías", "👥 Usuarios"])
        
    menu = st.sidebar.radio("Navegación", opciones)

    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

    # Enrutador de Vistas
    conn = conectar_db()
    
    if menu == "🏠 Inicio":
        mostrar_dashboard(conn)
    elif menu == "📦 Productos":
        mostrar_productos(conn)
    elif menu == "📥 Compras (Entradas)":
        mostrar_compras(conn)
    elif menu == "💳 Ventas (Salidas)":
        mostrar_ventas(conn, st.session_state.get('u_rol'))
    elif menu == "📊 Balance General":
        mostrar_balance(conn)
        
    conn.close()

if __name__ == "__main__":
    main()
